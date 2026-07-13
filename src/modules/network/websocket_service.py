#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket服务处理模块
==================

提供WebSocket服务的核心处理逻辑，包括音频数据处理、消息解析和流程控制。
"""

import json
import websockets
import logging
import base64
import tempfile
import os
import asyncio
import numpy as np
from ..core.server_state import ServerState
from ..network.websocket_manager import ws_reset, clear_websocket
from ..audio.audio_processing import async_vad, async_asr, async_asr_online, async_asr_with_speaker, async_asr_online_with_speaker
from ..speaker.speaker_manager import get_speaker_manager, identify_speaker
from ..audio.audio_format_handler import process_base64_audio, cleanup_temp_file
from ..network.translation_service import get_translation_service
from ..config.arg_parser import build_vad_config
from ..audio.server_audio_capture import ServerAudioCapture, is_server_audio_capture_available


# 16-bit PCM 随机环境噪声 RMS 参考值约 100-500；语音活跃期通常 > 1000
# 阀值设为 300 可有效区分正常语音和卫星底噪
RMS_SILENCE_THRESHOLD = 300


def calculate_rms(audio_data: bytes) -> float:
    """计算PCM 16bit 单声道音频数据的 RMS 能量（numpy 向量化实现，性能優于纯 Python 循环）"""
    if not audio_data:
        return 0.0
    try:
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples ** 2)))
    except Exception:
        return 0.0


async def ws_serve(websocket, path: str, server_state: ServerState) -> None:
    """
    WebSocket服务主处理函数
    
    这是整个语音识别服务的核心函数，负责：
    1. 管理WebSocket连接生命周期
    2. 处理客户端配置消息
    3. 接收和缓存音频数据
    4. 协调VAD、在线ASR、离线ASR的工作流程
    5. 管理音频缓冲区和状态
    
    数据流程：
    客户端音频 -> VAD检测 -> 音频缓存 -> 在线ASR(实时) -> 离线ASR(精确)
    
    Args:
        websocket: WebSocket连接对象
        path: WebSocket路径 (当前未使用)
        server_state: 服务器状态对象
    """
    logger = server_state.logger
    
    # 初始化音频缓冲区
    frames = []              # 原始音频帧缓存
    frames_asr = []          # 用于离线ASR的音频帧
    frames_asr_online = []   # 用于在线ASR的音频帧
    
    # 注册新连接
    try:
        client_address = websocket.remote_address if hasattr(websocket, 'remote_address') else 'unknown'
        logger.info(f"🔗 新WebSocket连接: {client_address}")
        
        server_state.websocket_users.add(websocket)
        logger.info(f"📊 当前连接数: {len(server_state.websocket_users)}")
        
        # 如果存在已保存的字幕设置，发送给新连接的客户端
        if hasattr(server_state, 'subtitle_settings') and server_state.subtitle_settings:
            try:
                settings_message = json.dumps({
                    "type": "settings_update",
                    "data": server_state.subtitle_settings
                }, ensure_ascii=False)
                await websocket.send(settings_message)
                logger.info(f"📤 已向新客户端发送当前字幕设置")
            except Exception as settings_error:
                logger.warning(f"⚠️ 向新客户端发送设置失败: {settings_error}")
        
    except Exception as e:
        logger.error(f"❌ 注册连接失败: {e}")
        return
    
    # 为每个连接创建独立的状态字典，避免连接间的状态污染
    websocket.status_dict_asr = {
        # 基础配置参数
        "batch_size_s": 30,                    # SenseVoice批处理时长 (秒)
        "merge_length_s": 5,                  # SenseVoice音频合并长度 (秒)
        "language": "zh",                    # SenseVoice识别语言
        "use_itn": True,                       # 启用逆文本正则化 (ITN)
        "ban_emo_unk": False,                  # 禁用未知情感 (enable_emotion的反向)
        "enable_event_detection": False,       # 启用音频事件检测
        "enable_speaker_id": False,            # 启用说话人识别
        "output_timestamp": True,              # 输出时间戳信息
        "merge_vad": False,                     # 合并VAD结果

    }  # 离线ASR状态
    websocket.status_dict_asr_online = {
        "cache": {}, 
        "is_final": False,
        "chunk_size": [5, 10, 5],  # 默认chunk_size配置
        "encoder_chunk_look_back": 4,  # 编码器回看块数
        "decoder_chunk_look_back": 1,  # 解码器回看块数
    } 
     # 在线ASR状态
    # VAD状态 - 从配置文件读取VAD参数
    websocket.status_dict_vad = build_vad_config(server_state.args)
    websocket.status_dict_punc = {"cache": {}}                           # 标点恢复状态
    
    # 初始化连接配置 - 每个连接独立配置
    websocket.chunk_interval = 10    # 块处理间隔
    websocket.vad_pre_idx = 0       # 累计音频时间索引
    websocket.wav_name = "microphone"  # 音频源名称
    websocket.mode = "2pass"         # 识别模式
    websocket.is_speaking = False    # 是否正在说话状态
    
    # 基于时间间隔的识别配置
    websocket.last_offline_asr_time = 0  # 上次离线识别时间
    websocket.offline_interval_ms = 5000 # 离线识别间隔：5秒
    websocket.last_online_asr_time = 0   # 上次在线识别时间（新增）
    websocket.online_interval_ms = 600   # 在线识别间隔：600毫秒（新增）
    
    # 说话人识别配置 - 默认启用说话人识别功能
    # 检查是否启用了串口功能或说话人识别功能
    serial_enabled = hasattr(server_state.args, 'enable_serial') and server_state.args.enable_serial
    speaker_verification_enabled = hasattr(server_state.args, 'enable_speaker_verification') and server_state.args.enable_speaker_verification
    speaker_diarization_enabled = hasattr(server_state.args, 'enable_speaker_diarization') and server_state.args.enable_speaker_diarization
    
    # 调试日志
    logger.info(f"[DEBUG] enable_serial={serial_enabled}, enable_speaker_verification={speaker_verification_enabled}, enable_speaker_diarization={speaker_diarization_enabled}")
    
    # 检查串口管理器是否已初始化
    from ..serial import get_serial_manager
    serial_manager = get_serial_manager()
    serial_manager_initialized = serial_manager is not None
    logger.info(f"[DEBUG] serial_manager_initialized={serial_manager_initialized}")
    
    # 如果启用了串口功能或串口管理器已初始化，默认启用说话人识别
    speaker_enabled = serial_enabled or serial_manager_initialized or speaker_verification_enabled or speaker_diarization_enabled
    
    websocket.enable_speaker_identification = speaker_enabled  # 根据服务器配置启用说话人识别
    websocket.enable_speaker_diarization = speaker_enabled     # 默认说话人识别和分离状态，可被客户端覆盖
    websocket.speaker_diarization_client_configured = False
    websocket.speaker_top_k = 3                     # 说话人识别返回前k个结果
    websocket.manual_speaker_name = None           # 当前会话手动指定的参会人
    
    logger.info(f"[DEBUG] speaker_enabled={speaker_enabled}, websocket.enable_speaker_diarization={websocket.enable_speaker_diarization}")
    
    if speaker_enabled:
        logger.info(f"WebSocket speaker enabled: serial={serial_enabled}, serial_mgr={serial_manager_initialized}, verification={speaker_verification_enabled}, diarization={speaker_diarization_enabled}")
    
    # 移除VAD相关的语音状态跟踪变量，改为基于时间间隔的处理
    
    # 服务器音频采集相关
    websocket.audio_capture_mode = "browser"  # 默认浏览器采集模式
    websocket.server_audio_device = None  # 服务器音频设备索引
    websocket.server_audio_capture = None  # 服务器音频采集实例
    
    print("new user connected", flush=True)
    
    try:
        # 主消息处理循环
        async for message in websocket:
            #print(f"Received message of type {type(message)}")
            
            # ==================== 处理JSON配置消息 ====================
            if isinstance(message, str):
                messagejson = json.loads(message)
                
                # ==================== 配置更新消息处理 ====================
                if "type" in messagejson and messagejson["type"] == "update_config":
                    await handle_config_update(websocket, messagejson, logger)
                    continue
                
                # ==================== 说话人相关消息处理 ====================
                if "action" in messagejson and messagejson["action"].startswith("speaker_"):
                    await handle_speaker_message(websocket, messagejson)
                    continue

                if "is_speaking" in messagejson:
                    websocket.is_speaking = messagejson["is_speaking"]
                    websocket.status_dict_asr_online["is_final"] = not websocket.is_speaking
                    
                    # 处理服务器音频采集的启动和停止
                    if websocket.audio_capture_mode == "server" and websocket.server_audio_device is not None:
                        if not websocket.is_speaking:
                            # 停止服务器音频采集
                            if websocket.server_audio_capture:
                                try:
                                    logger.info("🛑 收到停止信号，停止服务器音频采集")
                                    websocket.server_audio_capture.stop()
                                    websocket.server_audio_capture = None
                                except Exception as e:
                                    logger.error(f"❌ 停止服务器音频采集失败: {e}")
                            
                            # 取消音频处理任务
                            if hasattr(websocket, 'audio_processing_task') and websocket.audio_processing_task:
                                try:
                                    logger.info("🛑 取消音频处理任务")
                                    websocket.audio_processing_task.cancel()
                                except Exception as e:
                                    logger.error(f"❌ 取消音频处理任务失败: {e}")
                if "chunk_interval" in messagejson:
                    websocket.chunk_interval = messagejson["chunk_interval"]
                if "wav_name" in messagejson:
                    websocket.wav_name = messagejson.get("wav_name")
                if "chunk_size" in messagejson:
                    chunk_size = messagejson["chunk_size"]
                    if isinstance(chunk_size, str):
                        chunk_size = chunk_size.split(",")
                        websocket.status_dict_asr_online["chunk_size"] = [int(x) for x in chunk_size]
                    elif isinstance(chunk_size, int):
                        websocket.status_dict_asr_online["chunk_size"] = [chunk_size, chunk_size]
                    elif isinstance(chunk_size, list):
                        websocket.status_dict_asr_online["chunk_size"] = [int(x) for x in chunk_size]
                if "encoder_chunk_look_back" in messagejson:
                    websocket.status_dict_asr_online["encoder_chunk_look_back"] = messagejson[
                        "encoder_chunk_look_back"
                    ]
                if "decoder_chunk_look_back" in messagejson:
                    websocket.status_dict_asr_online["decoder_chunk_look_back"] = messagejson[
                        "decoder_chunk_look_back"
                    ]
                if "hotwords" in messagejson:
                    websocket.status_dict_asr["hotword"] = messagejson["hotwords"]
                if "mode" in messagejson:
                     websocket.mode = messagejson["mode"]
                
                # ==================== SenseVoiceSmall参数配置处理 ====================
                if "language" in messagejson:
                    websocket.status_dict_asr["language"] = messagejson["language"]
                    logger.info(f"🌐 设置ASR识别语言: {messagejson['language']}")
                # use_itn默认启用，不需要前端传递
                
                # ==================== 说话人识别配置处理 ====================
                if "enable_speaker_identification" in messagejson:
                    websocket.enable_speaker_identification = messagejson["enable_speaker_identification"]
                if "enable_speaker_diarization" in messagejson:
                    websocket.enable_speaker_diarization = messagejson["enable_speaker_diarization"]
                    # 同时控制说话人识别和分离功能
                    websocket.enable_speaker_identification = websocket.enable_speaker_diarization
                    websocket.speaker_diarization_client_configured = True
                    logger.info(f"🎭 客户端设置说话人识别和分离: {'启用' if websocket.enable_speaker_diarization else '禁用'}")
                if "speaker_top_k" in messagejson:
                    websocket.speaker_top_k = messagejson["speaker_top_k"]

                # ==================== 当前会话手动参会人覆盖 ====================
                if messagejson.get("clear_manual_speaker"):
                    old_manual_speaker = getattr(websocket, "manual_speaker_name", None)
                    websocket.manual_speaker_name = None
                    if old_manual_speaker:
                        logger.info(f"🙋 [手动参会人] 已恢复串口自动判断: {old_manual_speaker} -> 自动")
                elif "manual_speaker_name" in messagejson:
                    manual_speaker_name = str(messagejson.get("manual_speaker_name", "")).strip()
                    if manual_speaker_name:
                        old_manual_speaker = getattr(websocket, "manual_speaker_name", None)
                        websocket.manual_speaker_name = manual_speaker_name
                        logger.info(
                            f"🙋 [手动参会人] 当前会话手动指定参会人: {old_manual_speaker or '自动'} -> {manual_speaker_name}"
                        )
                    else:
                        websocket.manual_speaker_name = None
                        logger.info("🙋 [手动参会人] 收到空姓名，恢复串口自动判断")
                
                # ==================== 音频采集模式配置处理 ====================
                if "audio_capture_mode" in messagejson:
                    websocket.audio_capture_mode = messagejson["audio_capture_mode"]
                    logger.info(f"🎙️ 音频采集模式: {websocket.audio_capture_mode}")
                    
                    # 如果是服务器采集模式，需要获取设备ID
                    if websocket.audio_capture_mode == "server":
                        if "server_audio_device" in messagejson:
                            device_id_str = messagejson["server_audio_device"]
                            try:
                                websocket.server_audio_device = int(device_id_str)
                                logger.info(f"🎤 服务器音频设备ID: {websocket.server_audio_device}")
                                
                                # 检查PyAudio是否可用
                                if not is_server_audio_capture_available():
                                    error_msg = "PyAudio未安装，无法使用服务器音频采集功能"
                                    logger.error(error_msg)
                                    await websocket.send(json.dumps({
                                        "error": error_msg,
                                        "code": "PYAUDIO_NOT_AVAILABLE"
                                    }))
                                    continue
                                
                                # 如果is_speaking为True，立即开始服务器音频采集
                                if websocket.is_speaking:
                                    try:
                                        logger.info(f"🎤 启动服务器音频采集，设备索引: {websocket.server_audio_device}")
                                        
                                        # 创建音频采集实例
                                        websocket.server_audio_capture = ServerAudioCapture(
                                            device_index=websocket.server_audio_device,
                                            sample_rate=16000,
                                            channels=1,
                                            chunk_size=960,  # 与浏览器采集保持一致
                                            logger=logger
                                        )
                                        
                                        # 定义音频数据回调函数
                                        audio_chunk_count = [0]  # 使用列表来支持闭包修改
                                        def audio_callback(audio_data: bytes):
                                            # 将音频数据添加到帧缓冲区
                                            frames.append(audio_data)
                                            frames_asr.append(audio_data)
                                            frames_asr_online.append(audio_data)
                                            
                                            # 更新时间索引（与浏览器模式保持一致）
                                            duration_ms = len(audio_data) // 32  # 16000Hz, 16bit, mono
                                            websocket.vad_pre_idx += duration_ms
                                            
                                            # 每隔10个chunk记录一次日志（避免日志过多）
                                            audio_chunk_count[0] += 1
                                            if audio_chunk_count[0] % 10 == 0:
                                                logger.debug(f"🎙️ [服务器采集] 接收音频数据: 已采集{audio_chunk_count[0]}个chunk, 累计时长={websocket.vad_pre_idx}ms")
                                        
                                        # 启动音频采集
                                        websocket.server_audio_capture.start(audio_callback)
                                        logger.info("✅ 服务器音频采集已启动")
                                        
                                        # 创建异步音频处理任务
                                        websocket.audio_processing_task = asyncio.create_task(
                                            process_server_audio(websocket, frames_asr, frames_asr_online, server_state, logger)
                                        )
                                        
                                    except Exception as e:
                                        error_msg = f"启动服务器音频采集失败: {str(e)}"
                                        logger.error(error_msg)
                                        await websocket.send(json.dumps({
                                            "error": error_msg,
                                            "code": "AUDIO_CAPTURE_START_FAILED"
                                        }))
                                        
                            except ValueError:
                                logger.error(f"❌ 无效的设备ID: {device_id_str}")
                        else:
                            logger.warning("⚠️ 服务器采集模式未提供设备ID")
                
                # ==================== 翻译功能配置处理 ====================
                if "enable_translation" in messagejson:
                    websocket.enable_translation = messagejson["enable_translation"]
                    # 如果启用翻译，确保翻译服务已初始化
                    # 注释：现在使用本地翻译入口，不需要加载ModelScope翻译模型
                    # if websocket.enable_translation:
                    #     translation_service = get_translation_service()
                    #     if not translation_service.is_initialized:
                    #         success = translation_service.initialize()
                    #         if success:
                    #             server_state.logger.info("翻译服务初始化成功")
                    #         else:
                    #             server_state.logger.warning("翻译服务初始化失败，翻译功能将被禁用")

            # 安全检查：确保chunk_size存在
            if "chunk_size" in websocket.status_dict_asr_online:
                websocket.status_dict_vad["chunk_size"] = int(
                    websocket.status_dict_asr_online["chunk_size"][1] * 60 / websocket.chunk_interval
                )
            else:
                # 使用默认值
                websocket.status_dict_vad["chunk_size"] = int(
                    10 * 60 / websocket.chunk_interval
                )
            
            # ==================== 处理音频数据 ====================
            if (len(frames_asr_online) > 0 or len(frames_asr) >= 0 or not isinstance(message, str)):
                
                # 处理二进制音频数据
                if not isinstance(message, str):
                    frames.append(message)
                    duration_ms = len(message) // 32
                    websocket.vad_pre_idx += duration_ms
                    
                    # 记录语音数据接收日志
                    logger.debug(f"🌐 [浏览器采集] 接收到音频数据: 长度={len(message)}字节, 时长={duration_ms}ms, 累计时长={websocket.vad_pre_idx}ms")

                    # 将音频数据添加到缓冲区
                    frames_asr_online.append(message)
                    frames_asr.append(message)
                    
                    # ==================== 在线识别处理（600ms间隔）====================
                    # 每600ms调用一次离线模型，但不加标点，发送时标记为2pass-online
                    time_since_last_online = websocket.vad_pre_idx - websocket.last_online_asr_time
                    
                    if time_since_last_online >= websocket.online_interval_ms:
                        if websocket.mode == "2pass" or websocket.mode == "online":
                            audio_in_online = b"".join(frames_asr_online)
                            if len(audio_in_online) > 0:
                                try:
                                    logger.debug(f"🌊 [浏览器-在线-600ms] 执行在线识别: 时间={websocket.vad_pre_idx}ms, 音频={len(audio_in_online)}字节")
                                    # 使用离线模型，但不加标点（output_mode="2pass-online"）
                                    await async_asr_with_speaker(websocket, audio_in_online, server_state, output_mode="2pass-online")
                                except Exception as e:
                                    logger.error(f"在线识别错误: {e}")
                            frames_asr_online = []  # 清空在线识别缓冲区
                        
                        # 更新在线识别时间戳
                        websocket.last_online_asr_time = websocket.vad_pre_idx
                    
                    # ==================== 离线识别处理（4.5s-7s 智能切分）====================
                    # 在 4.5秒-7.0秒 区间内寻找静音点进行切分，防止单词断在半空。若没有静音，7.0秒强制切分。
                    time_since_last_offline = websocket.vad_pre_idx - websocket.last_offline_asr_time
                    
                    should_slice = False
                    if time_since_last_offline >= 7000:
                        should_slice = True
                        logger.info(f"⏳ [浏览器-离线-智能切分] 达到强制切分上限 7.0s，执行强制切分: time_since_last_offline={time_since_last_offline}ms")
                    elif time_since_last_offline >= 4500:
                        rms = calculate_rms(message)
                        if rms < RMS_SILENCE_THRESHOLD:
                            should_slice = True
                            logger.info(f"🤫 [浏览器-离线-智能切分] 检测到静音点 (RMS={rms:.1f} < 300) 且时长达 {time_since_last_offline/1000:.2f}s，执行智能切分")
                    
                    if should_slice:
                        if websocket.mode == "2pass" or websocket.mode == "offline":
                            audio_in_offline = b"".join(frames_asr)
                            if len(audio_in_offline) > 0:
                                try:
                                    logger.info(f"🎯 [浏览器-离线] 执行离线识别: 时间={websocket.vad_pre_idx}ms, 音频={len(audio_in_offline)}字节")
                                    # 使用离线模型，加标点（output_mode="2pass-offline"）
                                    await async_asr_with_speaker(websocket, audio_in_offline, server_state, output_mode="2pass-offline")
                                except Exception as e:
                                    logger.error(f"离线识别错误: {e}")
                            
                            # 清空两个缓冲区，避免重复处理
                            frames_asr = []  # 清空离线识别缓冲区
                            frames_asr_online = []  # 同时清空在线缓冲区，避免重复
                            logger.debug("🔄 [智能切分] 清空所有缓冲区")
                        
                        # 更新离线识别时间戳
                        websocket.last_offline_asr_time = websocket.vad_pre_idx
                        # 同时重置在线识别时间戳，开始新的周期
                        websocket.last_online_asr_time = websocket.vad_pre_idx
                        logger.debug(f"🔄 [智能切分] 重置时间戳: offline={websocket.vad_pre_idx}ms, online={websocket.vad_pre_idx}ms")
                    
                    # 保持音频帧缓存在合理大小（保留最近20帧）
                    if len(frames) > 100:  # 当缓存过大时进行清理
                        frames = frames[-20:]
    
    except websockets.ConnectionClosed as e:
        logger.info(f"🔌 WebSocket连接正常关闭: {e}")
    except websockets.InvalidState as e:
        logger.warning(f"⚠️ WebSocket状态异常: {e}")
    except websockets.ProtocolError as e:
        logger.error(f"❌ WebSocket协议错误: {e}")
    except Exception as e:
        logger.error(f"❌ WebSocket服务异常: {e}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
    finally:
        # 取消音频处理任务（如果存在）
        if hasattr(websocket, 'audio_processing_task') and websocket.audio_processing_task:
            try:
                logger.info("🛑 取消音频处理任务")
                websocket.audio_processing_task.cancel()
                try:
                    await websocket.audio_processing_task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                logger.error(f"❌ 取消音频处理任务失败: {e}")
        
        # 停止服务器音频采集（如果正在运行）
        if hasattr(websocket, 'server_audio_capture') and websocket.server_audio_capture:
            try:
                logger.info("🛑 停止服务器音频采集")
                websocket.server_audio_capture.stop()
            except Exception as e:
                logger.error(f"❌ 停止服务器音频采集失败: {e}")
        
        # 确保连接被正确清理
        try:
            await clear_websocket(websocket, server_state)
        except Exception as cleanup_error:
            logger.error(f"❌ 连接清理失败: {cleanup_error}")


async def handle_speaker_message(websocket, message_json):
    """
    处理说话人相关的WebSocket消息
    
    支持的操作:
    - speaker_register: 注册说话人
    - speaker_identify: 识别说话人
    - speaker_verify: 验证说话人
    - speaker_list: 获取说话人列表
    - speaker_delete: 删除说话人
    - speaker_info: 获取说话人信息
    """
    try:
        action = message_json.get("action")
        speaker_manager = get_speaker_manager()
        
        if action == "speaker_register":
            await handle_speaker_register(websocket, message_json, speaker_manager)
        elif action == "speaker_identify":
            await handle_speaker_identify(websocket, message_json, speaker_manager)
        elif action == "speaker_verify":
            await handle_speaker_verify(websocket, message_json, speaker_manager)
        elif action == "speaker_list":
            await handle_speaker_list(websocket, speaker_manager)
        elif action == "speaker_delete":
            await handle_speaker_delete(websocket, message_json, speaker_manager)
        elif action == "speaker_info":
            await handle_speaker_info(websocket, message_json, speaker_manager)
        else:
            await send_error_response(websocket, f"未知的说话人操作: {action}")
            
    except Exception as e:
        await send_error_response(websocket, f"处理说话人消息时出错: {str(e)}")


async def handle_speaker_register(websocket, message_json, speaker_manager):
    """处理说话人注册"""
    try:
        speaker_name = message_json.get("speaker_name")
        audio_data = message_json.get("audio_data")
        description = message_json.get("description", "")
        overwrite = message_json.get("overwrite", False)
        
        if not speaker_name:
            await send_error_response(websocket, "缺少说话人姓名")
            return
            
        if not audio_data:
            await send_error_response(websocket, "缺少音频数据")
            return
        
        # 处理base64音频数据并转换为标准WAV格式
        try:
            temp_path = process_base64_audio(audio_data, target_sr=16000)
        except Exception as e:
            await send_error_response(websocket, f"音频数据处理失败: {str(e)}")
            return
        
        try:
            # 注册说话人
            result = speaker_manager.register_speaker(
                speaker_name=speaker_name,
                audio_input=temp_path,
                description=description,
                overwrite=overwrite
            )
            
            # 发送响应
            response = {
                "action": "speaker_register",
                "success": result["success"],
                "message": result["message"],
                "speaker_name": speaker_name
            }
            
            if result["success"]:
                response["speaker_info"] = result.get("speaker_info")
            
            await websocket.send(json.dumps(response, ensure_ascii=False))
            
        finally:
            # 清理临时文件
            cleanup_temp_file(temp_path)
                
    except Exception as e:
        await send_error_response(websocket, f"注册说话人失败: {str(e)}")


async def handle_speaker_identify(websocket, message_json, speaker_manager):
    """处理说话人识别"""
    try:
        audio_data = message_json.get("audio_data")
        top_k = message_json.get("top_k", 3)
        
        if not audio_data:
            await send_error_response(websocket, "缺少音频数据")
            return
        
        # 处理base64音频数据并转换为标准WAV格式
        try:
            temp_path = process_base64_audio(audio_data, target_sr=16000)
        except Exception as e:
            await send_error_response(websocket, f"音频数据处理失败: {str(e)}")
            return
        
        try:
            # 识别说话人
            result = identify_speaker(
                audio_input=temp_path,
                top_k=top_k
            )
            
            # 发送响应
            response = {
                "action": "speaker_identify",
                "success": result["success"],
                "message": result.get("message", "识别完成"),
                "best_match": result.get("best_match"),
                "candidates": result.get("candidates", []),
                "threshold": result.get("threshold")
            }
            
            await websocket.send(json.dumps(response, ensure_ascii=False))
            
        finally:
            # 清理临时文件
            cleanup_temp_file(temp_path)
                
    except Exception as e:
        await send_error_response(websocket, f"识别说话人失败: {str(e)}")


async def handle_speaker_verify(websocket, message_json, speaker_manager):
    """处理说话人验证"""
    try:
        speaker_name = message_json.get("speaker_name")
        audio_data = message_json.get("audio_data")
        
        if not speaker_name:
            await send_error_response(websocket, "缺少说话人姓名")
            return
            
        if not audio_data:
            await send_error_response(websocket, "缺少音频数据")
            return
        
        # 解码base64音频数据
        try:
            audio_bytes = base64.b64decode(audio_data)
        except Exception as e:
            await send_error_response(websocket, f"音频数据解码失败: {str(e)}")
            return
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        try:
            # 先识别说话人
            identify_result = identify_speaker(temp_path)
            
            if not identify_result["success"]:
                response = {
                    "action": "speaker_verify",
                    "success": False,
                    "message": "验证失败：无法识别说话人",
                    "is_verified": False,
                    "speaker_name": speaker_name
                }
            else:
                best_match = identify_result.get("best_match")
                is_verified = (best_match and best_match["speaker_name"] == speaker_name)
                
                response = {
                    "action": "speaker_verify",
                    "success": True,
                    "message": "验证完成",
                    "is_verified": is_verified,
                    "speaker_name": speaker_name,
                    "similarity": best_match["similarity"] if best_match else 0.0,
                    "threshold": identify_result.get("threshold")
                }
            
            await websocket.send(json.dumps(response, ensure_ascii=False))
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        await send_error_response(websocket, f"验证说话人失败: {str(e)}")


async def handle_speaker_list(websocket, speaker_manager):
    """处理获取说话人列表"""
    try:
        speakers = speaker_manager.list_speakers()
        
        response = {
            "action": "speaker_list",
            "success": True,
            "message": "获取说话人列表成功",
            "speakers": speakers,
            "total_count": len(speakers)
        }
        
        await websocket.send(json.dumps(response, ensure_ascii=False))
        
    except Exception as e:
        await send_error_response(websocket, f"获取说话人列表失败: {str(e)}")


async def handle_speaker_delete(websocket, message_json, speaker_manager):
    """处理删除说话人"""
    try:
        speaker_name = message_json.get("speaker_name")
        
        if not speaker_name:
            await send_error_response(websocket, "缺少说话人姓名")
            return
        
        result = speaker_manager.delete_speaker(speaker_name)
        
        response = {
            "action": "speaker_delete",
            "success": result["success"],
            "message": result["message"],
            "speaker_name": speaker_name
        }
        
        await websocket.send(json.dumps(response, ensure_ascii=False))
        
    except Exception as e:
        await send_error_response(websocket, f"删除说话人失败: {str(e)}")


async def handle_speaker_info(websocket, message_json, speaker_manager):
    """处理获取说话人信息"""
    try:
        speaker_name = message_json.get("speaker_name")
        
        if not speaker_name:
            await send_error_response(websocket, "缺少说话人姓名")
            return
        
        speaker_info = speaker_manager.get_speaker_info(speaker_name)
        
        if speaker_info:
            response = {
                "action": "speaker_info",
                "success": True,
                "message": "获取说话人信息成功",
                "speaker_info": speaker_info
            }
        else:
            response = {
                "action": "speaker_info",
                "success": False,
                "message": f"说话人 {speaker_name} 不存在",
                "speaker_name": speaker_name
            }
        
        await websocket.send(json.dumps(response, ensure_ascii=False))
        
    except Exception as e:
        await send_error_response(websocket, f"获取说话人信息失败: {str(e)}")


async def handle_config_update(websocket, message_json, logger):
    """
    处理配置更新消息
    支持在录音过程中无感知地更新配置
    """
    try:
        updated_params = []
        
        # 处理说话人识别配置更新
        if "enable_speaker_diarization" in message_json:
            old_value = getattr(websocket, 'enable_speaker_diarization', False)
            new_value = message_json["enable_speaker_diarization"]
            
            websocket.enable_speaker_diarization = new_value
            websocket.enable_speaker_identification = new_value
            websocket.speaker_diarization_client_configured = True
            
            updated_params.append(f"说话人识别: {old_value} -> {new_value}")

        if "enable_translation" in message_json:
            old_value = getattr(websocket, 'enable_translation', False)
            raw_value = message_json["enable_translation"]
            if isinstance(raw_value, str):
                new_value = raw_value.strip().lower() in {"1", "true", "yes", "on"}
            else:
                new_value = bool(raw_value)

            websocket.enable_translation = new_value
            updated_params.append(f"翻译功能: {old_value} -> {new_value}")

        
        # 处理热词权重更新
        if "fst_inc_wts" in message_json:
            old_value = websocket.status_dict_asr.get("fst_inc_wts", 20)
            new_value = int(message_json["fst_inc_wts"])
            websocket.status_dict_asr["fst_inc_wts"] = new_value
            updated_params.append(f"热词权重: {old_value} -> {new_value}")

        
        # 记录所有更新的参数
        if updated_params:
            logger.info(f"🔧 实时更新配置参数: {', '.join(updated_params)}")
        
    except Exception as e:
        logger.error(f"❌ 处理配置更新失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")


async def process_server_audio(websocket, frames_asr, frames_asr_online, server_state, logger):
    """
    处理服务器采集的音频数据
    
    这个任务持续运行，定期检查音频缓冲区并进行ASR处理
    
    处理逻辑：
    1. 在线识别（600ms）：每600ms调用async_asr_with_speaker，标记为2pass-online
    2. 离线识别（5秒）：每5秒调用async_asr_with_speaker，标记为2pass-offline
    3. online和offline完全独立，互不影响、互不阻塞
    """
    logger.info("process_server_audio started")
    
    # 检查串口管理器是否已初始化，如果是则强制启用说话人识别
    from ..serial import get_serial_manager
    serial_manager = get_serial_manager()
    if serial_manager is not None and not getattr(websocket, 'speaker_diarization_client_configured', False):
        logger.info("Serial manager is initialized, forcing speaker diarization ON")
        websocket.enable_speaker_diarization = True
        websocket.enable_speaker_identification = True
    
    logger.info(f"Config: mode={websocket.mode}, online_interval={websocket.online_interval_ms}ms, offline_interval={websocket.offline_interval_ms}ms, speaker={'ON' if getattr(websocket, 'enable_speaker_diarization', False) else 'OFF'}")
    
    try:
        while websocket.is_speaking and websocket.audio_capture_mode == "server":
            await asyncio.sleep(0.05)  # 50ms 检查间隔（更快响应）
            
            # ==================== 在线识别处理（600ms间隔）====================
            # 每600ms调用一次，发送时标记为2pass-online
            # 与offline完全独立，互不影响
            time_since_last_online = websocket.vad_pre_idx - websocket.last_online_asr_time
            
            if time_since_last_online >= websocket.online_interval_ms:
                logger.debug(f"[600ms online trigger] vad_pre_idx={websocket.vad_pre_idx}ms, last={websocket.last_online_asr_time}ms, diff={time_since_last_online}ms")
                
                # 2pass 或 online 模式才执行在线识别
                if websocket.mode == "2pass" or websocket.mode == "online":
                    # 使用frames_asr_online缓冲区（与offline独立）
                    audio_in_online = b"".join(frames_asr_online)
                    
                    if len(audio_in_online) > 0:
                        # 创建独立的任务，不阻塞主循环
                        asyncio.create_task(
                            _process_online_asr(websocket, audio_in_online, server_state, logger)
                        )
                        
                        # 清空在线缓冲区
                        frames_asr_online.clear()
                
                # 更新在线识别时间戳
                websocket.last_online_asr_time = websocket.vad_pre_idx
            
            # ==================== 离线识别处理（4.5s-7s 智能切分）====================
            # 在 4.5秒-7.0秒 区间内寻找静音点进行切分，防止单词断在半空。若没有静音，7.0秒强制切分。
            time_since_last_offline = websocket.vad_pre_idx - websocket.last_offline_asr_time
            
            should_slice = False
            if time_since_last_offline >= 7000:
                should_slice = True
                logger.info(f"⏳ [服务器-离线-智能切分] 达到强制切分上限 7.0s，执行强制切分: time_since_last_offline={time_since_last_offline}ms")
            elif time_since_last_offline >= 4500:
                latest_chunk = frames_asr[-1] if len(frames_asr) > 0 else None
                if latest_chunk:
                    rms = calculate_rms(latest_chunk)
                    if rms < RMS_SILENCE_THRESHOLD:
                        should_slice = True
                        logger.info(f"🤫 [服务器-离线-智能切分] 检测到静音点 (RMS={rms:.1f} < 300) 且时长达 {time_since_last_offline/1000:.2f}s，执行智能切分")
            
            if should_slice:
                logger.info(f"[智能切分离线触发] vad_pre_idx={websocket.vad_pre_idx}ms, last={websocket.last_offline_asr_time}ms, diff={time_since_last_offline}ms")
                
                # 2pass 或 offline 模式才执行离线识别
                if websocket.mode == "2pass" or websocket.mode == "offline":
                    # 使用frames_asr缓冲区（与online独立）
                    audio_in_offline = b"".join(frames_asr)
                    
                    if len(audio_in_offline) > 0:
                        # 创建独立的任务，不阻塞主循环
                        asyncio.create_task(
                            _process_offline_asr(websocket, audio_in_offline, server_state, logger)
                        )
                        
                        # 清空两个缓冲区，避免重复处理
                        frames_asr.clear()
                        frames_asr_online.clear()
                        logger.debug("🔄 [服务器-离线-智能切分] 清空所有缓冲区")
                
                # 更新离线识别时间戳
                websocket.last_offline_asr_time = websocket.vad_pre_idx
                # 同时重置在线识别时间戳，开始新的周期
                websocket.last_online_asr_time = websocket.vad_pre_idx
                logger.debug(f"🔄 [服务器-离线-智能切分] 重置时间戳: offline={websocket.vad_pre_idx}ms, online={websocket.vad_pre_idx}ms")
    
    except asyncio.CancelledError:
        logger.info("🛑 音频处理任务已取消")
    except Exception as e:
        logger.error(f"❌ 音频处理任务异常: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
    finally:
        logger.info("✅ 音频处理任务已结束")


async def _process_online_asr(websocket, audio_in: bytes, server_state, logger):
    """
    独立的在线ASR处理任务（600ms间隔）
    使用离线模型但不加标点，发送时标记为2pass-online
    """
    try:
        logger.debug(f"🌊 [在线ASR-600ms] 开始处理: 音频长度={len(audio_in)} bytes")
        
        # 使用离线模型，但不加标点（output_mode="2pass-online"）
        await async_asr_with_speaker(websocket, audio_in, server_state, output_mode="2pass-online")
        
        logger.debug(f"✅ [在线ASR-600ms] 处理完成")
        
    except Exception as e:
        logger.error(f"❌ [在线ASR-600ms] 处理失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def _process_offline_asr(websocket, audio_in: bytes, server_state, logger):
    """
    独立的离线ASR处理任务（5秒间隔）
    发送时标记为2pass-offline
    """
    try:
        logger.info(f"🎯 [离线ASR-5s] 开始处理: 音频长度={len(audio_in)} bytes")
        
        # 调用async_asr_with_speaker，指定输出模式为2pass-offline
        await async_asr_with_speaker(websocket, audio_in, server_state, output_mode="2pass-offline")
        
        logger.info(f"✅ [离线ASR-5s] 处理完成")
        
    except Exception as e:
        logger.error(f"❌ [离线ASR-5s] 处理失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def send_error_response(websocket, error_message):
    """发送错误响应"""
    response = {
        "success": False,
        "error": True,
        "message": error_message
    }
    await websocket.send(json.dumps(response, ensure_ascii=False))
