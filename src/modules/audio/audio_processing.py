#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音频处理模块。

提供语音活动检测(VAD)、在线ASR和离线ASR的核心处理功能。
"""

import asyncio
import json
import logging
import tempfile
import os
import time
import re
from typing import Any, Dict, Optional, Tuple

import websockets

from ..core.server_state import ServerState
from ..speaker.speaker_manager import get_speaker_manager, identify_speaker
from ..network import local_translation
from ..audio.vad_monitor import get_vad_monitor
from ..audio.audio_duration_handler import get_audio_duration_handler, validate_speaker_audio
from ..audio.audio_format_handler import create_pcm_wav_file, cleanup_temp_file
from ..audio.text_processor import TextProcessor
from ..audio.audio_processing_monitor import get_audio_processing_monitor
from ..speaker.speaker_labeling import process_speaker_identification
from ..serial import get_serial_manager

# 创建logger实例
logger = logging.getLogger(__name__)

# 全局缓存的说话人管理器
_cached_speaker_manager = None
_speaker_manager_initialized = False

# 全局说话人信息缓存（按websocket连接缓存）
_speaker_info_cache = {}
_speaker_cache_lock = asyncio.Lock()


def is_valid_text(text: str, min_chars: int = 2) -> bool:
    """
    检查文本是否有效（包含实际内容，不只是标点符号或空格）
    
    Args:
        text: 待检查的文本
        min_chars: 最少需要的有效字符数（默认2个）
        
    Returns:
        bool: 文本有效返回True，否则返回False
    """
    if not text or not text.strip():
        return False
    
    # 移除所有标点符号和空格
    # 包括中文标点、英文标点、空格等
    cleaned_text = re.sub(r'[，。！？；：、,.!?;:\s…—\-。]+', '', text)
    
    # 移除标点后至少需要指定数量的字符才算有效
    # 默认至少2个字符，过滤"我。"、"呀。"等单字+标点的情况
    return len(cleaned_text) >= min_chars


def format_timestamp_for_display(milliseconds: int) -> str:
    """
    将毫秒时间戳格式化为可读的时间字符串 (HH:MM:SS)
    
    Args:
        milliseconds: 毫秒时间戳
        
    Returns:
        str: 格式化的时间字符串，如 "00:05:23"
    """
    total_seconds = milliseconds // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_cached_speaker_manager():
    """获取缓存的说话人管理器，避免重复调用"""
    global _cached_speaker_manager, _speaker_manager_initialized
    
    if not _speaker_manager_initialized:
        try:
            _cached_speaker_manager = get_speaker_manager()
            _speaker_manager_initialized = True
            if _cached_speaker_manager and _cached_speaker_manager.get('initialized', False):
                logger.info("✅ 说话人管理器已缓存并初始化")
            else:
                logger.info("ℹ️ 说话人管理器已缓存但未初始化，将使用说话人分离模式")
        except Exception as e:
            logger.warning(f"获取说话人管理器失败: {e}，将使用说话人分离模式")
            _cached_speaker_manager = None
            _speaker_manager_initialized = True
    
    return _cached_speaker_manager

def reset_speaker_manager_cache():
    """重置说话人管理器缓存，强制重新初始化"""
    global _cached_speaker_manager, _speaker_manager_initialized
    _cached_speaker_manager = None
    _speaker_manager_initialized = False
    logger.info("🔄 说话人管理器缓存已重置")

async def get_cached_speaker_info(websocket_id: str) -> Optional[dict]:
    """获取缓存的说话人信息"""
    async with _speaker_cache_lock:
        return _speaker_info_cache.get(websocket_id)


def build_manual_speaker_result(speaker_name: str) -> Dict[str, Any]:
    """构建手动指定参会人的返回结构。"""
    return {
        'original_result': {
            'success': True,
            'message': '手动指定参会人成功',
            'method': 'manual_override',
            'best_match': {
                'speaker_name': speaker_name,
                'similarity': 1.0,
                'speaker_id': f'manual_override_{speaker_name}'
            },
            'candidates': [{
                'speaker_name': speaker_name,
                'similarity': 1.0,
                'speaker_id': f'manual_override_{speaker_name}'
            }],
            'threshold': 1.0,
            'unit_number': None
        },
        'label_result': {
            'speaker_label': speaker_name,
            'speaker_type': 'manual',
            'confidence': 1.0,
            'source': 'manual_override',
            'unit_number': None
        }
    }


def get_speaker_from_serial(websocket=None) -> Optional[Dict[str, Any]]:
    """获取当前说话人信息。

    优先返回当前会话手动指定的参会人；如果没有手动指定，则回退到现有串口识别逻辑。
    
    Returns:
        说话人信息字典，如果没有则返回None
    """
    try:
        logger.info("🔍 [DEBUG] get_speaker_from_serial 被调用")

        manual_speaker_name = getattr(websocket, "manual_speaker_name", None) if websocket else None
        if manual_speaker_name:
            manual_speaker_name = str(manual_speaker_name).strip()
            if manual_speaker_name:
                logger.info(f"🙋 [手动参会人] 当前会话使用手动指定参会人: {manual_speaker_name}")
                return build_manual_speaker_result(manual_speaker_name)
        
        serial_manager = get_serial_manager()
        if not serial_manager:
            logger.warning("⚠️ [DEBUG] serial_manager 为 None")
            return None
        
        logger.info(f"🔍 [DEBUG] serial_manager 存在: {serial_manager}")
        
        # 获取说话人识别模式
        speaker_mode = serial_manager.get_speaker_mode()
        logger.info(f"🔍 [DEBUG] 说话人识别模式: {speaker_mode}")
        
        # 如果是声纹模式，不使用串口
        if speaker_mode == 'voiceprint':
            logger.info("ℹ️ [DEBUG] 声纹模式，不使用串口")
            return None
        
        # 获取当前说话人（在serial模式下，即使超时也返回最后一个）
        current_speaker = None
        
        if speaker_mode == 'serial':
            # serial模式：总是使用最后一个打开的单元，不检查超时
            current_speaker = serial_manager.last_opened_speaker
            logger.info(f"🔍 [DEBUG] Serial模式 - last_opened_speaker: {current_speaker}")
            logger.info(f"🔍 [DEBUG] Serial模式 - last_opened_unit: {serial_manager.last_opened_unit}")
            if current_speaker:
                logger.info(f"🎤 [串口说话人-Serial模式] 使用最后打开的单元: {current_speaker}")
        else:
            # hybrid模式：检查超时
            current_speaker = serial_manager.get_current_speaker()
            logger.info(f"🔍 [DEBUG] Hybrid模式 - current_speaker: {current_speaker}")
            if current_speaker:
                logger.info(f"🎤 [串口说话人-Hybrid模式] 使用串口识别: {current_speaker}")
        
        if not current_speaker:
            if speaker_mode == 'serial':
                logger.warning("⚠️ [串口说话人] Serial模式下 last_opened_speaker 为 None")
                logger.warning("⚠️ [串口说话人] 可能原因：")
                logger.warning("   1. 串口未收到任何'打开'信号")
                logger.warning("   2. 串口连接问题或配置错误")
                logger.warning("   3. 会议系统话筒未打开")
                logger.warning(f"   当前串口状态: last_opened_unit={serial_manager.last_opened_unit}, last_opened_time={serial_manager.last_opened_time}")
            else:
                logger.warning("⚠️ [DEBUG] current_speaker 为 None，返回 None")
            return None
        
        # 构建说话人信息（与声纹识别返回格式完全一致）
        speaker_info = {
            'original_result': {
                'success': True,
                'message': '串口识别成功',
                'method': 'serial_port',
                'best_match': {
                    'speaker_name': current_speaker,
                    'similarity': 1.0,  # 串口识别置信度100%
                    'speaker_id': f'serial_unit_{serial_manager.last_opened_unit}'
                },
                'candidates': [{
                    'speaker_name': current_speaker,
                    'similarity': 1.0,
                    'speaker_id': f'serial_unit_{serial_manager.last_opened_unit}'
                }],
                'threshold': 1.0,
                'unit_number': serial_manager.last_opened_unit
            },
            'label_result': {
                'speaker_label': current_speaker,
                'speaker_type': 'serial',  # 标记为串口识别
                'confidence': 1.0,  # 串口信号的置信度为100%
                'source': 'serial_port',
                'unit_number': serial_manager.last_opened_unit
            }
        }
        
        logger.info(f"✅ [DEBUG] 返回串口说话人信息: {current_speaker} (单元{serial_manager.last_opened_unit})")
        return speaker_info
        
    except Exception as e:
        logger.warning(f"从串口获取说话人失败: {e}")
        return None


def should_use_serial_speaker() -> bool:
    """判断是否应该使用串口说话人识别
    
    Returns:
        True表示使用串口，False表示使用声纹
    """
    try:
        logger.info("🔍 [DEBUG] should_use_serial_speaker 被调用")
        
        serial_manager = get_serial_manager()
        if not serial_manager:
            logger.warning("⚠️ [DEBUG] serial_manager 为 None，返回 False")
            return False
        
        speaker_mode = serial_manager.get_speaker_mode()
        logger.info(f"🔍 [DEBUG] speaker_mode: {speaker_mode}")
        
        # serial模式：总是使用串口（即使没有新信号，也用最后一个）
        if speaker_mode == 'serial':
            logger.info("✅ [DEBUG] Serial模式，返回 True")
            return True
        
        # hybrid模式：优先使用串口，如果有有效的串口信号则使用
        if speaker_mode == 'hybrid':
            current_speaker = serial_manager.get_current_speaker()
            result = current_speaker is not None
            logger.info(f"🔍 [DEBUG] Hybrid模式 - current_speaker: {current_speaker}, 返回: {result}")
            return result
        
        # voiceprint模式：不使用串口
        logger.info("ℹ️ [DEBUG] Voiceprint模式，返回 False")
        return False
        
    except Exception as e:
        logger.warning(f"判断说话人模式失败: {e}")
        return False

async def set_cached_speaker_info(websocket_id: str, speaker_info: dict) -> None:
    """设置缓存的说话人信息"""
    async with _speaker_cache_lock:
        _speaker_info_cache[websocket_id] = {
            'speaker_result': speaker_info,
            'timestamp': time.time()
        }
        logger.debug(f"💾 缓存说话人信息: {websocket_id}")

async def clear_cached_speaker_info(websocket_id: str) -> None:
    """清除指定连接的缓存说话人信息"""
    async with _speaker_cache_lock:
        if websocket_id in _speaker_info_cache:
            del _speaker_info_cache[websocket_id]
            logger.debug(f"🗑️ 清除说话人缓存: {websocket_id}")


class AudioProcessingError(Exception):
    """音频处理相关异常。"""
    pass


def segment_audio_by_duration(
    audio_in: bytes,
    segment_duration_ms: int = 30000,
    sample_rate: int = 16000,
    sample_width: int = 2
) -> Tuple[int, int]:
    """基于时长进行音频分割，跳过VAD检测。
    
    当用户确定音频全为语音内容时，可以使用此函数直接基于时长进行分割，
    避免VAD检测的计算开销和可能的误判。
    
    Args:
        audio_in: 输入的音频数据 (PCM格式)
        segment_duration_ms: 分割时长(毫秒)，默认30秒
        sample_rate: 采样率，默认16kHz
        sample_width: 采样位宽，默认2字节(16-bit)
        
    Returns:
        Tuple[int, int]: (语音开始时间ms, 语音结束时间ms)
                        对于时长分割，开始时间为0，结束时间为音频实际时长或分割时长的较小值
    """
    if not audio_in or len(audio_in) == 0:
        return -1, -1
    
    # 计算音频实际时长(毫秒)
    audio_duration_ms = len(audio_in) / (sample_rate * sample_width) * 1000
    
    # 语音开始时间固定为0
    speech_start = 0
    
    # 语音结束时间为音频时长和分割时长的较小值
    speech_end = min(int(audio_duration_ms), segment_duration_ms)
    
    return speech_start, speech_end


async def async_vad(
    websocket: websockets.WebSocketServerProtocol,
    audio_in: bytes,
    server_state: ServerState,
    vad_config: Optional[Dict[str, Any]] = None
) -> Tuple[int, int]:
    """异步语音活动检测 (Voice Activity Detection)。

    参考FunASR官方服务器实现，简化VAD处理逻辑，提高稳定性和性能。
    
    Args:
        websocket: WebSocket连接对象，包含VAD状态信息
        audio_in: 输入的音频数据 (PCM格式)
        server_state: 服务器状态对象
        vad_config: 可选的VAD配置参数，覆盖默认配置

    Returns:
        Tuple[int, int]: (语音开始时间ms, 语音结束时间ms)
                        -1表示未检测到对应事件

    Raises:
        AudioProcessingError: VAD模型推理失败时抛出异常
    """
    logger = server_state.logger
    
    # 获取时间监控器
    monitor = get_audio_processing_monitor()
    
    # 生成会话ID
    session_id = f"vad_{int(time.time() * 1000)}_{id(websocket)}"
    
    # 计算音频时长
    audio_duration = len(audio_in) / (16000 * 2) * 1000  # 16kHz, 16-bit
    
    # 开始会话监控
    monitor.start_session(session_id, len(audio_in), audio_duration)
    monitor.start_vad(session_id)
    
    try:
        # 检查VAD模型是否已加载
        if server_state.model_vad is None:
            monitor.end_vad(session_id, False, "VAD模型未加载")
            monitor.end_session(session_id)
            raise AudioProcessingError("VAD模型未加载")
        
        # 检查音频数据有效性
        if not audio_in or len(audio_in) == 0:
            monitor.end_vad(session_id, True, "音频数据为空")
            monitor.end_session(session_id)
            return -1, -1
        
        # 构建VAD参数配置 - 参考官方实现
        vad_params = websocket.status_dict_vad.copy() if hasattr(websocket, 'status_dict_vad') else {}
        
        # 应用自定义配置
        if vad_config:
            vad_params.update(vad_config)
        
        # 调用VAD模型进行语音活动检测 - 使用官方相同的调用方式
        segments_result = server_state.model_vad.generate(
            input=audio_in, 
            **vad_params
        )[0]["value"]
        
        # 参考官方实现的简化处理逻辑
        speech_start = -1
        speech_end = -1

        # 官方逻辑：只处理单个语音段，多个或零个都返回-1
        if len(segments_result) == 0 or len(segments_result) > 1:
            monitor.end_vad(session_id, True, f"检测到{len(segments_result)}个语音段")
            monitor.end_session(session_id)
            return speech_start, speech_end
            
        # 处理单个语音段
        if len(segments_result) == 1:
            segment = segments_result[0]
            if len(segment) >= 2:
                if segment[0] != -1:
                    speech_start = segment[0]
                if segment[1] != -1:
                    speech_end = segment[1]
        
        # VAD处理成功
        monitor.end_vad(session_id, True)
        
        # 获取处理时间（在session被删除前）
        vad_time = 0.0
        if session_id in monitor.current_sessions:
            session_record = monitor.current_sessions[session_id]
            vad_time = session_record.vad_processing_time or 0.0
        
        monitor.end_session(session_id)
        
        # 记录VAD结果到日志
        logger.info(f"🎤 VAD处理完成，耗时: {vad_time:.2f}ms")
        logger.debug(f"🎤 VAD处理完成 - 会话:{session_id}, 开始:{speech_start}ms, 结束:{speech_end}ms, 处理时长:{vad_time:.2f}ms")
        
        return speech_start, speech_end
        
    except Exception as e:
        # VAD处理失败
        monitor.end_vad(session_id, False, str(e))
        
        # 获取处理时间（在session被删除前）
        vad_time = 0.0
        if session_id in monitor.current_sessions:
            session_record = monitor.current_sessions[session_id]
            vad_time = session_record.vad_processing_time or 0.0
        
        monitor.end_session(session_id)
        
        # 记录错误日志（包含实际处理时间）
        logger.error(f"VAD检测失败: {str(e)}, 处理时长:{vad_time:.2f}ms")
        raise AudioProcessingError(f"VAD模型推理失败: {str(e)}") from e


async def async_asr(
    websocket: websockets.WebSocketServerProtocol,
    audio_in: bytes,
    server_state: ServerState,
) -> None:
    """异步离线ASR语音识别。

    使用高精度的离线ASR模型对完整的语音段进行识别，通常在VAD检测到
    语音结束后调用。识别结果会经过标点恢复处理，然后发送给客户端。

    Args:
        websocket: WebSocket连接对象
        audio_in: 输入的音频数据 (PCM格式)
        server_state: 服务器状态对象

    Raises:
        AudioProcessingError: ASR模型推理失败时抛出异常

    Examples:
        >>> await async_asr(websocket, audio_segment, server_state)
        # 识别结果会通过websocket发送给客户端
    """
    logger = server_state.logger
    
    # 获取时间监控器
    monitor = get_audio_processing_monitor()
    
    # 生成会话ID
    session_id = f"asr_offline_{int(time.time() * 1000)}_{id(websocket)}"
    
    # 计算音频时长
    audio_duration = len(audio_in) / (16000 * 2) * 1000  # 16kHz, 16-bit
    
    # 开始会话监控
    monitor.start_session(session_id, len(audio_in), audio_duration)
    monitor.start_asr(session_id, 'offline')
    
    try:
        if len(audio_in) > 0:
        #    logger.debug(f"🎯 开始离线ASR识别，音频长度: {len(audio_in)} bytes")
            
            # 执行ASR识别
            rec_result = server_state.model_asr.generate(
                input=audio_in, 
                **websocket.status_dict_asr
            )[0]
            
            logger.debug(f"离线ASR完整结果: {rec_result}")
            logger.debug(f"离线ASR原始结果: {rec_result.get('text', '')}")
            
            # SenseVoiceSmall模型输出清理
            if server_state.args.model_type == "sensevoice":
                original_text = rec_result.get("text", "")
                # 移除SenseVoiceSmall的特殊标记: <|zh|><|NEUTRAL|><|Speech|>
                import re
                cleaned_text = re.sub(r'<\|[^|]*\|>', '', original_text).strip()
                rec_result["text"] = cleaned_text
                logger.debug(f"SenseVoice清理后结果: {cleaned_text}")
            
            # 标点恢复处理
            if (server_state.model_punc is not None and 
                len(rec_result.get("text", "")) > 0):
                
                try:
                    # 使用标点恢复模型
                    punc_result = server_state.model_punc.generate(
                        input=rec_result["text"], 
                        **websocket.status_dict_punc
                    )[0]
                    
                    # 更新识别结果
                    rec_result["text"] = punc_result.get("text", rec_result["text"])
                #    logger.debug(f"标点恢复后结果: {rec_result['text']}")
                    
                except Exception as e:
                    logger.warning(f"标点恢复失败: {e}，使用原始识别结果")
                    # 继续使用原始识别结果，不中断流程
            
            # 文本后处理
            if len(rec_result.get("text", "")) > 0:
                try:
                    # 创建文本处理器实例
                    hotword_map = getattr(websocket, 'hotword_map', {})
                    text_processor = TextProcessor(hotword_map=hotword_map)
                    
                    # 对识别结果进行文本后处理
                    processed_text = text_processor.process_text(
                        rec_result["text"],
                        enable_rich_postprocess=True,
                        enable_punctuation_cleaning=True,
                        enable_hotword_boost=True
                    )
                    
                    # 更新识别结果
                    rec_result["raw_text"] = rec_result["text"]  # 保存原始文本
                    rec_result["text"] = processed_text
                    
                    logger.debug(f"文本后处理: '{rec_result['raw_text']}' -> '{processed_text}'")
                    
                except Exception as e:
                    logger.warning(f"文本后处理失败: {e}，使用原始识别结果")
                    # 继续使用原始识别结果，不中断流程
            
            # 发送识别结果
            if len(rec_result.get("text", "")) > 0:
                # 检查文本是否有效（过滤只有标点符号的结果）
                if not is_valid_text(rec_result["text"]):
                    logger.debug(f"🚫 过滤无效识别结果（仅标点符号）: '{rec_result['text']}'")
                    monitor.end_asr(session_id, True, "文本无效")
                    monitor.end_session(session_id)
                    return
                
                mode = "2pass-offline" if "2pass" in websocket.mode else websocket.mode
                
                # 构建基础消息数据
                message_data = {
                    "mode": mode,
                    "text": rec_result["text"],
                    "wav_name": websocket.wav_name,
                    "is_final": websocket.status_dict_asr_online.get("is_final", False),
                }
                
                # 计算并添加绝对时间戳
                if "timestamp" in rec_result and rec_result["timestamp"]:
                    # 获取基准时间（上次识别的时间点）
                    base_time_ms = getattr(websocket, 'last_offline_asr_time', 0)
                    
                    # 计算绝对时间戳：基准时间 + 相对时间
                    absolute_timestamps = []
                    for ts_pair in rec_result["timestamp"]:
                        if len(ts_pair) >= 2:
                            start_ms = ts_pair[0] + base_time_ms
                            end_ms = ts_pair[1] + base_time_ms
                            absolute_timestamps.append([start_ms, end_ms])
                    
                    message_data["timestamp"] = absolute_timestamps
                    
                    # 添加格式化的时间范围（方便前端直接显示）
                    if absolute_timestamps:
                        start_time_str = format_timestamp_for_display(absolute_timestamps[0][0])
                        end_time_str = format_timestamp_for_display(absolute_timestamps[-1][1])
                        message_data["time_range"] = f"{start_time_str} - {end_time_str}"
                        message_data["start_time"] = start_time_str
                        message_data["end_time"] = end_time_str
                    
                    logger.debug(f"时间戳计算: 基准时间={base_time_ms}ms, 相对时间={rec_result['timestamp']}, 绝对时间={absolute_timestamps}")
                
                # 添加翻译功能（如果启用）
                if getattr(websocket, 'enable_translation', False):
                    try:
                        translation = await local_translation.translate(rec_result["text"])
                        if translation:
                            message_data["translation"] = translation
                            logger.debug(f"翻译: '{rec_result['text']}' -> '{translation}'")
                    except Exception as e:
                        logger.warning(f"翻译过程中出现错误: {e}")
                
                message = json.dumps(message_data, ensure_ascii=False)
                
        #        logger.info(f"📤 [WebSocket发送] 离线ASR结果 - 模式: {mode}, 文本: '{rec_result['text']}', 音频源: {websocket.wav_name}, 最终结果: {websocket.is_speaking}")
                logger.debug(f"📤 [WebSocket发送] 完整消息内容: {message}")
                
                await websocket.send(message)
        #    logger.info(f"✅ [WebSocket发送成功] 离线ASR结果已发送给客户端")
                
                # ASR处理成功
                monitor.end_asr(session_id, True)
                
                # 获取ASR处理时间
                asr_time = 0.0
                if session_id in monitor.current_sessions:
                    session_record = monitor.current_sessions[session_id]
                    asr_time = session_record.asr_processing_time or 0.0
                
                logger.info(f"🎯 ASR处理完成，耗时: {asr_time:.2f}ms")
                
                monitor.end_session(session_id)
                
                # 记录ASR结果到日志
                record = monitor.records[-1] if monitor.records else None
                if record:
                    logger.debug(f"🎯 离线ASR处理完成 - 会话:{session_id}, 处理时长:{record.asr_processing_time:.2f}ms, 文本:'{rec_result.get('text', '')[:50]}...'")
        else:
            # 空音频的处理
        #    logger.debug("🔇 音频为空，发送空结果")
            mode = "2pass-offline" if "2pass" in websocket.mode else websocket.mode
            
            message = json.dumps({
                "mode": mode,
                "text": "",
                "wav_name": websocket.wav_name,
                "is_final": getattr(websocket, 'is_speaking', True),
            }, ensure_ascii=False)
            
        #    logger.info(f"📤 [WebSocket发送] 空音频结果 - 模式: {mode}, 音频源: {websocket.wav_name}, 最终结果: {websocket.is_speaking}")
            logger.debug(f"📤 [WebSocket发送] 完整消息内容: {message}")
            
            await websocket.send(message)
        #    logger.info(f"✅ [WebSocket发送成功] 空音频结果已发送给客户端")
            
            # 空音频处理成功
            monitor.end_asr(session_id, True, "音频为空")
            monitor.end_session(session_id)
            
    except Exception as e:
        # ASR处理失败
        monitor.end_asr(session_id, False, str(e))
        monitor.end_session(session_id)
        
        logger.error(f"❌ 离线ASR识别过程中发生错误: {e}")
        logger.error(f"音频长度: {len(audio_in)}, ASR状态: {websocket.status_dict_asr}")


async def _async_asr_processing(websocket, audio_in: bytes, server_state: ServerState, session_id: str = None, enable_punctuation: bool = True) -> dict:
    """独立的ASR处理异步函数。
    
    执行语音识别处理。
    
    Args:
        websocket: WebSocket连接对象
        audio_in: 输入的音频数据 (PCM格式)
        server_state: 服务器状态对象
        session_id: 会话ID，用于时间监控
        enable_punctuation: 是否启用标点恢复（默认True）
        
    Returns:
        dict: ASR识别结果
        
    Raises:
        AudioProcessingError: ASR处理失败时抛出异常
    """
    logger = server_state.logger
    
    # 获取时间监控器
    monitor = get_audio_processing_monitor()
    
    # 如果提供了session_id，开始ASR时间记录
    if session_id:
        monitor.start_asr(session_id, 'offline_with_speaker')
    
    # 检查音频数据长度
    if len(audio_in) == 0:
        logger.warning("⚠️ 音频数据为空，跳过ASR处理")
        return {"text": ""}
    
    try:
        # 执行ASR识别
        asr_raw_result = server_state.model_asr.generate(
            input=audio_in, 
            **websocket.status_dict_asr
        )
        logger.info(f"🔍 [调试] 带说话人识别ASR完整结果: {asr_raw_result}")
        rec_result = asr_raw_result[0]
        logger.info(f"🔍 [调试] 带说话人识别ASR原始结果: {rec_result}")
        
        # SenseVoiceSmall模型输出清理
        if server_state.args.model_type == "sensevoice":
            original_text = rec_result.get("text", "")
            import re
            cleaned_text = re.sub(r'<\|[^|]*\|>', '', original_text).strip()
            rec_result["text"] = cleaned_text
        
        # 标点恢复处理（根据enable_punctuation参数决定是否启用）
        if (enable_punctuation and 
            server_state.model_punc is not None and 
            len(rec_result.get("text", "")) > 0):
            
            try:
                logger.debug("📝 开始标点恢复处理...")
                punc_result = server_state.model_punc.generate(
                    input=rec_result["text"], 
                    **websocket.status_dict_punc
                )[0]
                original_text = rec_result["text"]
                rec_result["text"] = punc_result.get("text", rec_result["text"])
                logger.debug(f"📝 标点恢复: '{original_text}' -> '{rec_result['text']}'")
            except Exception as e:
                logger.warning(f"标点恢复失败: {e}，使用原始识别结果")
        elif not enable_punctuation:
            logger.debug("⚡ 标点恢复已禁用（在线模式）")
            # 在线模式：移除SenseVoice自带的标点符号
            if server_state.args.model_type == "sensevoice" and len(rec_result.get("text", "")) > 0:
                import re
                original_text = rec_result["text"]
                # 移除所有中文和英文标点符号
                text_no_punct = re.sub(r'[，。！？；：、,.!?;:\s…—\-]+', '', original_text)
                rec_result["text"] = text_no_punct
                logger.debug(f"🔧 移除SenseVoice标点: '{original_text}' -> '{text_no_punct}'")
            
        # ITN功能已移除
        
        # 文本后处理
        if len(rec_result.get("text", "")) > 0:
            try:
                # 创建文本处理器实例
                hotword_map = getattr(websocket, 'hotword_map', {})
                text_processor = TextProcessor(hotword_map=hotword_map)
                
                # 对识别结果进行文本后处理
                processed_text = text_processor.process_text(
                    rec_result["text"],
                    enable_rich_postprocess=True,
                    enable_punctuation_cleaning=True,
                    enable_hotword_boost=True
                )
                
                # 更新识别结果
                rec_result["raw_text"] = rec_result["text"]  # 保存原始文本
                rec_result["text"] = processed_text
                
                logger.debug(f"带说话人识别文本后处理: '{rec_result['raw_text']}' -> '{processed_text}'")
                
            except Exception as e:
                logger.warning(f"文本后处理失败: {e}，使用原始识别结果")
                # 继续使用原始识别结果，不中断流程
        
        # 如果提供了session_id，结束ASR时间记录（成功情况）
        if session_id:
            monitor.end_asr(session_id, True)
            
            # 获取ASR处理时间
            asr_time = 0.0
            if session_id in monitor.current_sessions:
                session_record = monitor.current_sessions[session_id]
                asr_time = session_record.asr_processing_time or 0.0
            
            logger.info(f"🎯 ASR处理完成，耗时: {asr_time:.2f}ms")
            
        return rec_result
        
    except Exception as e:
        # 如果提供了session_id，结束ASR时间记录（失败情况）
        if session_id:
            monitor.end_asr(session_id, False, str(e))
            
        logger.error(f"❌ ASR处理过程中发生错误: {e}")
        raise AudioProcessingError(f"ASR处理失败: {e}") from e


async def _async_speaker_processing(websocket, audio_in: bytes, server_state: ServerState) -> dict:
    """独立的说话人识别异步函数（仅串口识别）。
    
    只执行串口说话人识别，不执行声纹识别。
    
    Args:
        websocket: WebSocket连接对象
        audio_in: 输入的音频数据 (PCM格式)
        server_state: 服务器状态对象
        
    Returns:
        dict: 串口说话人识别结果，如果未收到串口信号则返回None
        
    Raises:
        AudioProcessingError: 说话人识别处理失败时抛出异常
    """
    logger = server_state.logger
    
    # 检查音频数据长度
    if len(audio_in) == 0:
        logger.warning("⚠️ 音频数据为空，跳过说话人识别")
        return None
        
    try:
        logger.info("🎤 开始串口说话人识别")
        
        # 只使用串口说话人识别
        serial_speaker = get_speaker_from_serial(websocket)
        if serial_speaker:
            logger.info("✅ 串口识别成功，返回说话人信息")
            return serial_speaker
        else:
            logger.info("ℹ️ 串口识别返回 None（可能未收到串口信号）")
            return None
                
    except Exception as e:
        logger.warning(f"串口说话人识别过程中出现错误: {e}")
        return None


async def async_asr_with_speaker(websocket, audio_in: bytes, server_state: ServerState, output_mode: str = None) -> None:
    """带串口说话人识别的异步离线ASR语音识别。

    集成语音识别和串口说话人识别功能，提供完整的语音处理流水线。
    在进行语音识别的同时，从串口获取说话人信息并在结果中包含。
    
    注意：本函数只使用串口识别，不使用声纹识别。

    Args:
        websocket: WebSocket连接对象
        audio_in: 输入的音频数据 (PCM格式)
        server_state: 服务器状态对象
        output_mode: 输出模式标记，如果指定则覆盖默认的mode（例如："2pass-online"）

    Raises:
        AudioProcessingError: ASR或串口识别失败时抛出异常
    """
    logger = server_state.logger
    
    # 获取时间监控器
    monitor = get_audio_processing_monitor()
    
    # 生成会话ID
    session_id = f"asr_with_speaker_{int(time.time() * 1000)}_{id(websocket)}"
    
    # 计算音频时长
    audio_duration = len(audio_in) / (16000 * 2) * 1000  # 16kHz, 16-bit
    
    # 开始会话监控
    monitor.start_session(session_id, len(audio_in), audio_duration)
    
    try:
        if len(audio_in) > 0:
            logger.info(f"🎯 开始带说话人识别的ASR处理，音频长度: {len(audio_in)} bytes")
            
            # 只使用串口识别，不使用声纹识别
            speaker_result = None
            logger.info("🔍 使用串口说话人识别")
            
            # 先检查串口管理器状态
            serial_manager = get_serial_manager()
            if serial_manager:
                logger.info(f"🔍 [诊断] 串口管理器状态: 已初始化")
                logger.info(f"🔍 [诊断] 说话人模式: {serial_manager.get_speaker_mode()}")
                logger.info(f"🔍 [诊断] last_opened_speaker: {serial_manager.last_opened_speaker}")
                logger.info(f"🔍 [诊断] last_opened_unit: {serial_manager.last_opened_unit}")
            else:
                logger.warning("⚠️ [诊断] 串口管理器未初始化！请检查是否启用了 --enable_serial 参数")
            
            monitor.start_speaker(session_id)
            speaker_result = get_speaker_from_serial(websocket)
            monitor.end_speaker(session_id, speaker_result is not None)
            
            if speaker_result:
                logger.info(f"✅ 串口识别完成: {speaker_result.get('label_result', {}).get('speaker_label', '未知')}")
            else:
                logger.warning("⚠️ 串口识别返回 None - 请检查：")
                logger.warning("   1. 是否启用了 --enable_serial 参数")
                logger.warning("   2. 串口是否正确连接")
                logger.warning("   3. 会议系统话筒是否已打开")
            
            # 执行ASR处理
            # 根据output_mode决定是否启用标点恢复
            # 在线模式（2pass-online）不加标点，离线模式加标点
            enable_punctuation = (output_mode != "2pass-online")
            logger.debug(f"🔧 标点恢复设置: {'禁用' if not enable_punctuation else '启用'} (mode={output_mode})")
            
            asr_task = _async_asr_processing(websocket, audio_in, server_state, session_id, enable_punctuation=enable_punctuation)
            
            # 等待ASR完成
            rec_result = await asr_task
            
            # 记录说话人识别处理时间
            if session_id in monitor.current_sessions:
                speaker_time = monitor.current_sessions[session_id].speaker_processing_time
                if speaker_time is not None:
                    logger.info(f"🎯 说话人识别处理完成，耗时: {speaker_time:.2f}ms")
            
            logger.info(f"🔄 并行处理完成 - ASR结果: {rec_result.get('text', '')[:50]}..., 说话人结果: {'已获取' if speaker_result else '未启用'}")
            
            # 3. 发送识别结果
            if len(rec_result.get("text", "")) > 0:
                # 检查文本是否有效（过滤只有标点符号的结果）
                if not is_valid_text(rec_result["text"]):
                    logger.debug(f"🚫 过滤无效识别结果（仅标点符号）: '{rec_result['text']}'")
                    monitor.end_session(session_id)
                    return
                
                # 使用指定的输出模式，如果没有指定则使用默认模式
                if output_mode:
                    mode = output_mode
                else:
                    mode = "2pass-offline" if "2pass" in websocket.mode else websocket.mode
                
                # 构建消息，包含说话人信息
                message_data = {
                    "mode": mode,
                    "text": rec_result["text"],
                    "wav_name": websocket.wav_name,
                    "is_final": websocket.is_speaking,
                }
                
                # 计算并添加绝对时间戳
                if "timestamp" in rec_result and rec_result["timestamp"]:
                    # 根据输出模式选择正确的基准时间
                    if output_mode == "2pass-online":
                        # 在线模式使用last_online_asr_time作为基准
                        base_time_ms = getattr(websocket, 'last_online_asr_time', 0)
                        logger.debug(f"[时间戳] 使用在线基准时间: {base_time_ms}ms")
                    else:
                        # 离线模式使用last_offline_asr_time作为基准
                        base_time_ms = getattr(websocket, 'last_offline_asr_time', 0)
                        logger.debug(f"[时间戳] 使用离线基准时间: {base_time_ms}ms")
                    
                    # 计算绝对时间戳：基准时间 + 相对时间
                    absolute_timestamps = []
                    for ts_pair in rec_result["timestamp"]:
                        if len(ts_pair) >= 2:
                            start_ms = ts_pair[0] + base_time_ms
                            end_ms = ts_pair[1] + base_time_ms
                            absolute_timestamps.append([start_ms, end_ms])
                    
                    message_data["timestamp"] = absolute_timestamps
                    
                    # 添加格式化的时间范围（方便前端直接显示）
                    if absolute_timestamps:
                        start_time_str = format_timestamp_for_display(absolute_timestamps[0][0])
                        end_time_str = format_timestamp_for_display(absolute_timestamps[-1][1])
                        message_data["time_range"] = f"{start_time_str} - {end_time_str}"
                        message_data["start_time"] = start_time_str
                        message_data["end_time"] = end_time_str
                    
                    logger.debug(f"时间戳计算: 基准时间={base_time_ms}ms, 相对时间={rec_result['timestamp']}, 绝对时间={absolute_timestamps}")
                
                # 添加说话人信息
                logger.info(f"🔍 [DEBUG] speaker_result 是否存在: {speaker_result is not None}")
                if speaker_result:
                    logger.info(f"🔍 [DEBUG] speaker_result 内容: {speaker_result}")
                    message_data["speaker_result"] = speaker_result
                    
                    # 使用新的标记系统信息
                    label_result = speaker_result.get("label_result", {})
                    logger.info(f"🔍 [DEBUG] label_result: {label_result}")
                    if label_result:
                        speaker_name = label_result.get("speaker_label", "未知说话人")
                        message_data["speaker_name"] = speaker_name
                        message_data["speaker_type"] = label_result.get("speaker_type", "unknown")
                        message_data["speaker_confidence"] = label_result.get("confidence", 0.0)
                        logger.info(f"✅ [DEBUG] 已添加说话人信息到消息: {speaker_name}")
                        
                        # 如果是已注册说话人，添加详细信息
                        if label_result.get("speaker_type") == "registered":
                            speaker_info = label_result.get("speaker_info", {})
                            if speaker_info:
                                message_data["speaker_info"] = speaker_info
                    else:
                        # 兼容旧格式
                        best_match = speaker_result.get("best_match")
                        if best_match:
                            message_data["speaker_name"] = best_match["speaker_name"]
                            message_data["speaker_confidence"] = best_match["similarity"]
                
                # 添加翻译功能（如果启用）
                if getattr(websocket, 'enable_translation', False):
                    try:
                        translation = await local_translation.translate(rec_result["text"])
                        if translation:
                            message_data["translation"] = translation
                            logger.debug(f"翻译: '{rec_result['text']}' -> '{translation}'")
                    except Exception as e:
                        logger.warning(f"翻译过程中出现错误: {e}")
                
                # 调试：显示 message_data 的键
                logger.info(f"🔍 [DEBUG] message_data 包含的键: {list(message_data.keys())}")
                if "speaker_name" in message_data:
                    logger.info(f"🔍 [DEBUG] message_data['speaker_name']: {message_data['speaker_name']}")
                
                message = json.dumps(message_data, ensure_ascii=False)
                
                logger.info(f"📤 [WebSocket发送] 带说话人信息的ASR结果: {message}")
                await websocket.send(message)
                
                # 广播给所有其他连接的客户端（例如滚动字幕应用）
                from ..network.websocket_manager import broadcast_message
                await broadcast_message(message, server_state, exclude_websocket=websocket)
                
                # 记录成功处理的日志
                logger.info(f"⏱️ [时间监控] 带说话人识别ASR处理完成 - 音频时长: {audio_duration:.1f}ms, 识别文本: '{rec_result['text'][:50]}...'")
                
        else:
            # 空音频的处理
            mode = "2pass-offline" if "2pass" in websocket.mode else websocket.mode
            
            message = json.dumps({
                "mode": mode,
                "text": "",
                "wav_name": websocket.wav_name,
                "is_final": websocket.is_speaking,
            }, ensure_ascii=False)
            
            await websocket.send(message)
            
        # 结束会话监控（成功情况）
        monitor.end_session(session_id)
            
    except Exception as e:
        # 结束会话监控（失败情况）
        monitor.end_session(session_id)
        
        logger.error(f"❌ 带说话人识别的ASR处理过程中发生错误: {e}")
        logger.error(f"音频长度: {len(audio_in)}, ASR状态: {websocket.status_dict_asr}")
        raise AudioProcessingError(f"带说话人识别的ASR处理失败: {e}") from e


async def async_asr_online(websocket, audio_in: bytes, server_state: ServerState) -> None:
    """
    异步在线流式ASR语音识别
    
    使用流式ASR模型对音频进行实时识别，提供低延迟的识别结果。
    适用于需要实时反馈的场景，如实时字幕、语音输入等。
    
    Args:
        websocket: WebSocket连接对象
        audio_in: 输入的音频数据  
        server_state: 服务器状态对象
    """
    logger = server_state.logger
    
    try:
        if len(audio_in) > 0:
        #    logger.debug(f"🌊 开始在线ASR识别，音频长度: {len(audio_in)} bytes")
            
            # 执行流式ASR识别
            result = server_state.model_asr_streaming.generate(
                input=audio_in, 
                **websocket.status_dict_asr_online
            )
             # 在2pass模式下，如果是最终结果则跳过在线输出
            if (websocket.mode == "2pass" and 
                websocket.status_dict_asr_online.get("is_final", False)):
                logger.debug("2pass模式下跳过最终在线结果，等待离线结果")
                return
            # 安全检查：确保结果不为空
            if not result or len(result) == 0:
                logger.warning("在线ASR返回空结果，跳过处理")
                return
                
            rec_result = result[0]
            #logger.debug(f"ASR结果: {rec_result}")
            
            # SenseVoiceSmall模型输出清理
            if server_state.args.model_type == "sensevoice":
                original_text = rec_result.get("text", "")
                # 移除SenseVoiceSmall的特殊标记: <|zh|><|NEUTRAL|><|Speech|>
                import re
                cleaned_text = re.sub(r'<\|[^|]*\|>', '', original_text).strip()
                rec_result["text"] = cleaned_text
            #    logger.debug(f"SenseVoice在线清理后结果: {cleaned_text}")
            
            # 文本后处理（仅对最终结果进行完整处理）
            if (len(rec_result.get("text", "")) > 0 and 
                websocket.status_dict_asr_online.get("is_final", False)):
                try:
                    # 创建文本处理器实例
                    hotword_map = getattr(websocket, 'hotword_map', {})
                    text_processor = TextProcessor(hotword_map=hotword_map)
                    
                    # 对识别结果进行文本后处理
                    processed_text = text_processor.process_text(
                        rec_result["text"],
                        enable_rich_postprocess=True,
                        enable_punctuation_cleaning=True,
                        enable_hotword_boost=True
                    )
                    
                    # 更新识别结果
                    rec_result["raw_text"] = rec_result["text"]  # 保存原始文本
                    rec_result["text"] = processed_text
                    
                    logger.debug(f"在线ASR文本后处理: '{rec_result['raw_text']}' -> '{processed_text}'")
                    
                except Exception as e:
                    logger.warning(f"在线ASR文本后处理失败: {e}，使用原始识别结果")
                    # 继续使用原始识别结果，不中断流程
            
            # 发送识别结果
            if len(rec_result.get("text", "")):
                # 检查文本是否有效（过滤只有标点符号的结果）
                if not is_valid_text(rec_result["text"]):
                    logger.debug(f"🚫 过滤无效在线识别结果（仅标点符号）: '{rec_result['text']}'")
                    return
                
                mode = "2pass-online" if "2pass" in websocket.mode else websocket.mode
                
                # 构建基础消息数据
                message_data = {
                    "mode": mode,
                    "text": rec_result["text"],
                    "wav_name": websocket.wav_name,
                    "is_final": websocket.is_speaking,
                }
                
                # 添加翻译功能（如果启用且为最终结果）
                if (getattr(websocket, 'enable_translation', False) and 
                    websocket.status_dict_asr_online.get("is_final", False)):
                    try:
                        translation = await local_translation.translate(rec_result["text"])
                        if translation:
                            message_data["translation"] = translation
                            logger.debug(f"翻译: '{rec_result['text']}' -> '{translation}'")
                    except Exception as e:
                        logger.warning(f"在线翻译过程中出现错误: {e}")
                
                message = json.dumps(message_data, ensure_ascii=False)
                
            #    logger.info(f"📤 [WebSocket发送] 在线ASR结果 - 模式: {mode}, 文本: '{rec_result['text']}', 音频源: {websocket.wav_name}, 最终结果: {websocket.is_speaking}")
            #    print(f"📤 [在线发送完整消息] {message}")
                logger.debug(f"📤 [WebSocket发送] 完整消息内容: {message}")
                
                await websocket.send(message)
            #    logger.info(f"✅ [WebSocket发送成功] 在线ASR结果已发送给客户端")
                
    except Exception as e:
        logger.error(f"❌ 在线ASR识别过程中发生错误: {e}")
        logger.error(f"音频长度: {len(audio_in)}, 在线ASR状态: {websocket.status_dict_asr_online}")


async def async_asr_online_with_speaker(websocket, audio_in: bytes, server_state: ServerState) -> None:
    """
    带说话人识别的异步在线流式ASR语音识别
    
    使用流式ASR模型对音频进行实时识别，同时从串口获取说话人信息。
    适用于需要实时反馈且需要说话人标识的场景。
    
    Args:
        websocket: WebSocket连接对象
        audio_in: 输入的音频数据  
        server_state: 服务器状态对象
    """
    logger = server_state.logger
    
    try:
        if len(audio_in) > 0:
            # 检查流式模型是否已加载
            if server_state.model_asr_streaming is None:
                logger.warning("⚠️ 在线流式ASR模型未加载，跳过在线识别")
                return
            
            # 获取说话人信息（从串口）- 始终尝试获取
            speaker_result = get_speaker_from_serial(websocket)
            if speaker_result:
                logger.debug(f"🎤 [在线-说话人] 串口识别: {speaker_result.get('label_result', {}).get('speaker_label', '未知')}")
            
            # 执行流式ASR识别
            # 注意：流式模型使用 **websocket.status_dict_asr_online 传递参数
            # cache 会在原地被更新，保持状态
            result = server_state.model_asr_streaming.generate(
                input=audio_in, 
                **websocket.status_dict_asr_online
            )
            
            # 调试：打印在线ASR原始结果和cache状态
            if result and len(result) > 0:
                text_preview = result[0].get('text', '')[:50] if result[0].get('text') else '空'
                cache_keys = list(websocket.status_dict_asr_online.get("cache", {}).keys())
                logger.debug(f"🌊 [在线ASR] 原始结果: {text_preview}, cache keys: {cache_keys}")
            
            # 在2pass模式下，如果是最终结果则跳过在线输出
            if (websocket.mode == "2pass" and 
                websocket.status_dict_asr_online.get("is_final", False)):
                logger.debug("2pass模式下跳过最终在线结果，等待离线结果")
                return
            
            # 安全检查：确保结果不为空
            if not result or len(result) == 0:
                # 流式识别返回空是正常的，不需要警告
                return
                
            rec_result = result[0]
            
            # SenseVoiceSmall模型输出清理
            if server_state.args.model_type == "sensevoice":
                original_text = rec_result.get("text", "")
                import re
                cleaned_text = re.sub(r'<\|[^|]*\|>', '', original_text).strip()
                rec_result["text"] = cleaned_text
            
            # 文本后处理（仅对最终结果进行完整处理）
            if (len(rec_result.get("text", "")) > 0 and 
                websocket.status_dict_asr_online.get("is_final", False)):
                try:
                    hotword_map = getattr(websocket, 'hotword_map', {})
                    text_processor = TextProcessor(hotword_map=hotword_map)
                    
                    processed_text = text_processor.process_text(
                        rec_result["text"],
                        enable_rich_postprocess=True,
                        enable_punctuation_cleaning=True,
                        enable_hotword_boost=True
                    )
                    
                    rec_result["raw_text"] = rec_result["text"]
                    rec_result["text"] = processed_text
                    
                    logger.debug(f"在线ASR文本后处理: '{rec_result['raw_text']}' -> '{processed_text}'")
                    
                except Exception as e:
                    logger.warning(f"在线ASR文本后处理失败: {e}，使用原始识别结果")
            
            # 发送识别结果
            if len(rec_result.get("text", "")):
                # 检查文本是否有效（过滤只有标点符号的结果）
                if not is_valid_text(rec_result["text"]):
                    logger.debug(f"🚫 过滤无效在线识别结果（仅标点符号）: '{rec_result['text']}'")
                    return
                
                mode = "2pass-online" if "2pass" in websocket.mode else websocket.mode
                
                # 构建基础消息数据
                message_data = {
                    "mode": mode,
                    "text": rec_result["text"],
                    "wav_name": websocket.wav_name,
                    "is_final": websocket.is_speaking,
                }
                
                # 添加说话人信息
                if speaker_result:
                    message_data["speaker_result"] = speaker_result
                    label_result = speaker_result.get("label_result", {})
                    if label_result:
                        speaker_name = label_result.get("speaker_label", "未知说话人")
                        message_data["speaker_name"] = speaker_name
                        message_data["speaker_type"] = label_result.get("speaker_type", "unknown")
                        message_data["speaker_confidence"] = label_result.get("confidence", 0.0)
                        logger.debug(f"🎤 [在线-说话人] 添加说话人信息: {speaker_name}")
                
                # 添加翻译功能（如果启用且为最终结果）
                # if (getattr(websocket, 'enable_translation', False) and 
                #     websocket.status_dict_asr_online.get("is_final", False)):
                #     try:
                #         translation_service = get_translation_service()
                #         if translation_service.is_initialized:
                #             translation = await translation_service.translate(rec_result["text"])
                #             if translation:
                #                 message_data["translation"] = translation
                #                 logger.debug(f"在线翻译结果: '{rec_result['text']}' -> '{translation}'")
                #     except Exception as e:
                #         logger.warning(f"在线翻译过程中出现错误: {e}")
                
                message = json.dumps(message_data, ensure_ascii=False)
                logger.debug(f"📤 [WebSocket发送] online带说话人的在线ASR结果: {message}")
                
                await websocket.send(message)
                
    except Exception as e:
        logger.error(f"❌ 带说话人的在线ASR识别过程中发生错误: {e}")
        logger.error(f"音频长度: {len(audio_in)}, 在线ASR状态: {websocket.status_dict_asr_online}")


async def async_asr_2pass(
    websocket: websockets.WebSocketServerProtocol,
    audio_in: bytes,
    server_state: ServerState,
    is_final: bool = False
) -> None:
    """异步2pass模式ASR语音识别。

    实现类似FunASR C++服务器的2pass模式：
    1. 在线模式：使用流式模型提供实时识别结果（低延迟）
    2. 离线模式：使用高精度模型提供最终识别结果（高精度）
    
    2pass模式的优势：
    - 实时性：在线模型提供即时反馈
    - 准确性：离线模型提供高精度最终结果
    - 用户体验：既有实时反馈又有准确结果

    Args:
        websocket: WebSocket连接对象
        audio_in: 输入的音频数据 (PCM格式)
        server_state: 服务器状态对象
        is_final: 是否为最终音频段（语音结束）

    Raises:
        AudioProcessingError: ASR模型推理失败时抛出异常

    Examples:
        >>> # 实时处理音频流
        >>> await async_asr_2pass(websocket, audio_chunk, state, is_final=False)
        >>> 
        >>> # 处理最终音频段
        >>> await async_asr_2pass(websocket, final_audio, state, is_final=True)
    """
    logger = server_state.logger
    args = server_state.args
    
    try:
        if len(audio_in) == 0:
            logger.debug("🔇 音频为空，跳过2pass处理")
            return
        
        logger.debug(f"🔄 开始2pass模式处理，音频长度: {len(audio_in)} bytes, 最终段: {is_final}")
        
        # 检查是否禁用VAD，直接基于时长处理
        disable_vad = getattr(args, 'disable_vad', False)
        if disable_vad:
            logger.debug("⚡ VAD已禁用，使用时长分割模式")
            segment_duration_ms = getattr(args, 'segment_duration_ms', 30000)
            
            # 使用时长分割替代VAD
            speech_start, speech_end = segment_audio_by_duration(
                audio_in, 
                segment_duration_ms
            )
            
            logger.debug(f"⏱️ 时长分割结果: 开始={speech_start}ms, 结束={speech_end}ms")
            
            # 如果音频时长不足，且不是最终段，跳过处理
            if speech_start == -1 and speech_end == -1 and not is_final:
                logger.debug("🔇 音频时长不足，跳过处理")
                return
        
        # 第一步：在线流式识别（实时反馈）
        if not is_final and server_state.model_asr_streaming is not None:
            try:
                # 执行在线流式识别
                online_result = server_state.model_asr_streaming.generate(
                    input=audio_in,
                    **websocket.status_dict_asr_online
                )
                
                if online_result and len(online_result) > 0:
                    online_rec = online_result[0]
                    online_text = online_rec.get("text", "")
                    
                    # SenseVoiceSmall模型输出清理
                    if args.model_type == "sensevoice":
                        import re
                        online_text = re.sub(r'<\|[^|]*\|>', '', online_text).strip()
                    
                    # 文本后处理（在线模式）
                    if online_text:
                        try:
                            text_processor = TextProcessor()
                            original_text = online_text
                            processed_result = text_processor.process_text(
                                online_text,
                                enable_rich_postprocess=True,
                                enable_punctuation_cleaning=True,
                                enable_hotword_boost=True
                            )
                            online_text = (
                                processed_result.get('processed_text', online_text)
                                if isinstance(processed_result, dict)
                                else processed_result
                            )
                            logger.debug(f"📝 [2pass-在线] 文本后处理: '{original_text}' -> '{online_text}'")
                        except Exception as e:
                            logger.warning(f"⚠️ [2pass-在线] 文本后处理失败: {e}")
                    
                    # 发送在线识别结果（临时结果）
                    if online_text:
                        # 检查文本是否有效（过滤只有标点符号的结果）
                        if not is_valid_text(online_text):
                            logger.debug(f"🚫 过滤无效2pass在线结果（仅标点符号）: '{online_text}'")
                        else:
                            message_data = {
                                "mode": "2pass-online",
                                "text": online_text,
                                "wav_name": websocket.wav_name,
                                "is_final": False,
                                "confidence": online_rec.get("confidence", 0.0),
                                "timestamp": time.time()
                            }
                            
                            # 应用热词增强（如果配置了热词）
                            if server_state.hotword_map:
                                message_data["text"] = apply_hotword_boost(
                                    online_text, 
                                    server_state.hotword_map,
                                    getattr(args, 'fst_inc_wts', 20)
                                )
                            
                            message = json.dumps(message_data, ensure_ascii=False)
                            logger.debug(f"📤 [2pass-在线] 发送实时结果: '{online_text}'")
                            await websocket.send(message)
                        
            except Exception as e:
                logger.warning(f"⚠️ 2pass在线识别失败: {e}")
        
        # 第二步：离线高精度识别（最终结果）
        if is_final and server_state.model_asr is not None:
            try:
                # 执行离线高精度识别
                offline_result = server_state.model_asr.generate(
                    input=audio_in,
                    **websocket.status_dict_asr
                )
                
                if offline_result and len(offline_result) > 0:
                    offline_rec = offline_result[0]
                    offline_text = offline_rec.get("text", "")
                    
                    # SenseVoiceSmall模型输出清理
                    if args.model_type == "sensevoice":
                        import re
                        offline_text = re.sub(r'<\|[^|]*\|>', '', offline_text).strip()
                    
                    # 标点恢复处理
                    if server_state.model_punc is not None and offline_text:
                        try:
                            punc_result = server_state.model_punc.generate(
                                input=offline_text,
                                **websocket.status_dict_punc
                            )[0]
                            offline_text = punc_result.get("text", offline_text)
                            logger.debug(f"📝 标点恢复: '{offline_text}'")
                        except Exception as e:
                            logger.warning(f"⚠️ 标点恢复失败: {e}")
                    
                    # ITN功能已移除
                    
                    # 文本后处理（离线模式）
                    if offline_text:
                        try:
                            text_processor = TextProcessor()
                            original_text = offline_text
                            processed_result = text_processor.process_text(
                                offline_text,
                                enable_rich_postprocess=True,
                                enable_punctuation_cleaning=True,
                                enable_hotword_boost=True
                            )
                            offline_text = (
                                processed_result.get('processed_text', offline_text)
                                if isinstance(processed_result, dict)
                                else processed_result
                            )
                            logger.debug(f"📝 [2pass-离线] 文本后处理: '{original_text}' -> '{offline_text}'")
                        except Exception as e:
                            logger.warning(f"⚠️ [2pass-离线] 文本后处理失败: {e}")
                    
                    # 应用热词增强
                    if server_state.hotword_map and offline_text:
                        offline_text = apply_hotword_boost(
                            offline_text,
                            server_state.hotword_map,
                            getattr(args, 'fst_inc_wts', 20)
                        )
                    
                    # 发送最终识别结果
                    if offline_text:
                        message_data = {
                            "mode": "2pass-offline",
                            "text": offline_text,
                            "wav_name": websocket.wav_name,
                            "is_final": True,
                            "confidence": offline_rec.get("confidence", 0.0),
                            "timestamp": time.time()
                        }
                        
                        # 计算并添加绝对时间戳
                        if "timestamp" in offline_rec and offline_rec["timestamp"]:
                            # 获取基准时间（上次识别的时间点）
                            base_time_ms = getattr(websocket, 'last_offline_asr_time', 0)
                            
                            # 计算绝对时间戳：基准时间 + 相对时间
                            absolute_timestamps = []
                            for ts_pair in offline_rec["timestamp"]:
                                if len(ts_pair) >= 2:
                                    start_ms = ts_pair[0] + base_time_ms
                                    end_ms = ts_pair[1] + base_time_ms
                                    absolute_timestamps.append([start_ms, end_ms])
                            
                            message_data["asr_timestamp"] = absolute_timestamps
                            
                            # 添加格式化的时间范围
                            if absolute_timestamps:
                                start_time_str = format_timestamp_for_display(absolute_timestamps[0][0])
                                end_time_str = format_timestamp_for_display(absolute_timestamps[-1][1])
                                message_data["time_range"] = f"{start_time_str} - {end_time_str}"
                                message_data["start_time"] = start_time_str
                                message_data["end_time"] = end_time_str
                            
                            logger.debug(f"[2pass-离线] 时间戳计算: 基准={base_time_ms}ms, 相对={offline_rec['timestamp']}, 绝对={absolute_timestamps}")
                        
                        # 添加翻译功能（如果启用）
                        if getattr(websocket, 'enable_translation', False):
                            try:
                                translation = await local_translation.translate(offline_text)
                                if translation:
                                    message_data["translation"] = translation
                                    logger.debug(f"🌐 翻译结果: '{offline_text}' -> '{translation}'")
                            except Exception as e:
                                logger.warning(f"⚠️ 翻译失败: {e}")
                        
                        message = json.dumps(message_data, ensure_ascii=False)
                        logger.info(f"📤 [2pass-离线] 发送最终结果: '{offline_text}'")
                        await websocket.send(message)
                        
            except Exception as e:
                logger.error(f"❌ 2pass离线识别失败: {e}")
                raise AudioProcessingError(f"2pass离线识别失败: {e}") from e
        
        logger.debug(f"✅ 2pass模式处理完成")
        
    except Exception as e:
        logger.error(f"❌ 2pass模式处理过程中发生错误: {e}")
        logger.error(f"音频长度: {len(audio_in)}, 最终段: {is_final}")
        raise AudioProcessingError(f"2pass模式处理失败: {e}") from e


def apply_hotword_boost(text: str, hotword_map: dict, boost_weight: int = 20) -> str:
    """应用热词增强，类似C++服务器的热词处理。
    
    Args:
        text: 原始识别文本
        hotword_map: 热词映射表 {热词: 权重}
        boost_weight: 默认增强权重
        
    Returns:
        增强后的文本
    """
    if not text or not hotword_map:
        return text
    
    # 简单的热词替换逻辑
    # 在实际应用中，这里应该实现更复杂的热词增强算法
    enhanced_text = text
    for hotword, weight in hotword_map.items():
        if hotword in text:
            # 这里可以实现更复杂的热词增强逻辑
            # 目前只是简单标记
            pass
    
    return enhanced_text


# ITN相关函数已移除


async def perform_speaker_diarization(
    audio_in: bytes,
    server_state: ServerState,
    text: str,
    logger
) -> dict:
    """执行说话人分离处理。
    
    参考FunnyASR的实现，使用FunASR的说话人分离功能来区分不同说话人。
    当没有已注册说话人或未找到匹配说话人时，使用此功能进行说话人分离。
    
    Args:
        audio_in: 输入音频数据
        server_state: 服务器状态对象
        text: 识别的文本
        logger: 日志记录器
        
    Returns:
        说话人分离结果字典
    """
    try:
        logger.debug("🎭 开始说话人分离处理...")
        
        # 检查是否有说话人模型
        if not hasattr(server_state, 'model_speaker') or server_state.model_speaker is None:
            logger.debug("🎭 说话人模型未加载，无法进行说话人分离")
            return None
        
        # 将音频数据转换为numpy数组
        import numpy as np
        audio_data = np.frombuffer(audio_in, dtype=np.int16).astype(np.float64)
        
        # 使用FunASR的说话人分离功能
        # 参考FunnyASR的实现，使用return_spk_res=True来获取说话人信息
        try:
            # 使用离线ASR模型进行说话人分离识别
            diarization_result = server_state.model_asr.generate(
                input=audio_data,
                return_spk_res=True,  # 启用说话人分离
                sentence_timestamp=True,  # 启用时间戳
                return_raw_text=True,  # 返回原始文本
                is_final=True
            )
            
            if diarization_result and len(diarization_result) > 0:
                result = diarization_result[0]
                
                # 提取说话人信息
                sentence_info = result.get('sentence_info', [])
                speakers_found = set()
                speaker_segments = []
                
                for sentence in sentence_info:
                    if 'spk' in sentence:
                        speaker_id = sentence['spk']
                        speakers_found.add(speaker_id)
                        speaker_segments.append({
                            "speaker_id": speaker_id,
                            "text": sentence.get('text', ''),
                            "start_time": sentence.get('start', 0),
                            "end_time": sentence.get('end', 0)
                        })
                
                if speakers_found:
                    # 统计每个说话人的发言时长
                    speaker_stats = {}
                    for segment in speaker_segments:
                        speaker_id = segment['speaker_id']
                        duration = segment['end_time'] - segment['start_time']
                        if speaker_id not in speaker_stats:
                            speaker_stats[speaker_id] = {
                                "speaker_id": speaker_id,
                                "total_duration": 0,
                                "segment_count": 0,
                                "text_segments": []
                            }
                        speaker_stats[speaker_id]['total_duration'] += duration
                        speaker_stats[speaker_id]['segment_count'] += 1
                        speaker_stats[speaker_id]['text_segments'].append(segment['text'])
                    
                    # 按发言时长排序，主要说话人是发言时间最长的
                    sorted_speakers = sorted(
                        speaker_stats.values(),
                        key=lambda x: x['total_duration'],
                        reverse=True
                    )
                    
                    logger.debug(f"🎭 说话人分离成功，检测到 {len(speakers_found)} 个说话人")
                    
                    return {
                        "type": "diarization",
                        "speakers": sorted_speakers,
                        "primary_speaker": sorted_speakers[0] if sorted_speakers else None,
                        "speaker_segments": speaker_segments,
                        "total_speakers": len(speakers_found)
                    }
                else:
                    logger.debug("🎭 说话人分离未检测到多个说话人")
                    return {
                        "type": "diarization",
                        "speakers": [{"speaker_id": "speaker_0", "total_duration": 0, "segment_count": 1, "text_segments": [text]}],
                        "primary_speaker": {"speaker_id": "speaker_0", "total_duration": 0, "segment_count": 1},
                        "speaker_segments": [{"speaker_id": "speaker_0", "text": text, "start_time": 0, "end_time": 0}],
                        "total_speakers": 1
                    }
            else:
                logger.debug("🎭 说话人分离返回空结果")
                return None
                
        except Exception as e:
            logger.warning(f"🎭 FunASR说话人分离失败: {e}")
            # 如果FunASR分离失败，返回单说话人结果
            return {
                "type": "diarization",
                "speakers": [{"speaker_id": "speaker_0", "total_duration": 0, "segment_count": 1, "text_segments": [text]}],
                "primary_speaker": {"speaker_id": "speaker_0", "total_duration": 0, "segment_count": 1},
                "speaker_segments": [{"speaker_id": "speaker_0", "text": text, "start_time": 0, "end_time": 0}],
                "total_speakers": 1
            }
            
    except Exception as e:
        logger.warning(f"🎭 说话人分离处理失败: {e}")
        return None


async def perform_speaker_diarization_with_duration_handling(
    audio_in: bytes,
    server_state: ServerState,
    text: str,
    logger
) -> dict:
    """执行带时长处理的说话人分离。
    
    智能处理音频时长限制问题：
    - 短音频：检查是否满足最小时长要求
    - 长音频：自动分段处理并合并结果
    - 优化音频：确保最佳的分离效果
    
    Args:
        audio_in: 输入音频数据
        server_state: 服务器状态对象
        text: 识别的文本
        logger: 日志记录器
        
    Returns:
        说话人分离结果字典
    """
    try:
        logger.debug("🎭 开始带时长处理的说话人分离...")
        
        # 获取音频时长处理器
        duration_handler = get_audio_duration_handler()
        
        # 验证和优化音频用于说话人分离
        dia_validation = validate_speaker_audio(audio_in, "diarization")
        
        if not dia_validation["valid"]:
            logger.warning(f"⚠️ 音频不适合说话人分离: {dia_validation['reason']}")
            logger.debug(f"💡 建议: {dia_validation['suggestion']}")
            
            # 如果音频过短，返回单说话人结果
            if "过短" in dia_validation["reason"]:
                return {
                    "type": "diarization",
                    "speakers": [{"speaker_id": "speaker_0", "total_duration": 0, "segment_count": 1, "text_segments": [text]}],
                    "primary_speaker": {"speaker_id": "speaker_0", "total_duration": 0, "segment_count": 1},
                    "speaker_segments": [{"speaker_id": "speaker_0", "text": text, "start_time": 0, "end_time": 0}],
                    "total_speakers": 1,
                    "processing_info": {
                        "method": "single_speaker_fallback",
                        "reason": dia_validation["reason"]
                    }
                }
            return None
        
        # 处理单段音频
        if dia_validation["processed_audio"]:
            logger.debug("🎭 处理单段音频分离")
            result = await perform_speaker_diarization(
                dia_validation["processed_audio"], server_state, text, logger
            )
            
            if result:
                # 添加处理信息
                result["processing_info"] = {
                    "method": "single_segment",
                    "original_duration_ms": duration_handler.get_audio_duration_ms(audio_in),
                    "processed_duration_ms": duration_handler.get_audio_duration_ms(dia_validation["processed_audio"]),
                    "optimization_reason": dia_validation["reason"]
                }
            
            return result
        
        # 处理分段音频
        if dia_validation["segments"]:
            logger.debug(f"🎭 处理分段音频分离，共{len(dia_validation['segments'])}段")
            
            segment_results = []
            
            for segment in dia_validation["segments"]:
                try:
                    logger.debug(f"🎭 处理第{segment['index']+1}段 ({segment['duration_ms']}ms)")
                    
                    # 对每段进行说话人分离
                    segment_result = await perform_speaker_diarization(
                        segment["audio_data"], server_state, text, logger
                    )
                    
                    if segment_result:
                        # 添加段信息
                        segment_result["segment_info"] = {
                            "index": segment["index"],
                            "start_time_ms": segment["start_time_ms"],
                            "end_time_ms": segment["end_time_ms"],
                            "duration_ms": segment["duration_ms"]
                        }
                        segment_results.append(segment_result)
                        
                except Exception as e:
                    logger.warning(f"⚠️ 第{segment['index']+1}段分离失败: {e}")
                    continue
            
            if segment_results:
                # 合并分段结果
                logger.debug(f"🔗 合并{len(segment_results)}段分离结果")
                merged_result = duration_handler.merge_diarization_results(segment_results)
                
                if merged_result:
                    # 添加总体处理信息
                    merged_result["processing_info"] = {
                        "method": "segmented_processing",
                        "total_segments": len(dia_validation["segments"]),
                        "successful_segments": len(segment_results),
                        "original_duration_ms": duration_handler.get_audio_duration_ms(audio_in)
                    }
                    
                    logger.debug(f"✅ 分段分离完成: {merged_result['total_speakers']}个说话人")
                    return merged_result
                else:
                    logger.warning("⚠️ 分段结果合并失败")
            else:
                logger.warning("⚠️ 所有分段处理都失败")
        
        # 如果所有方法都失败，返回单说话人结果
        logger.debug("🎭 使用单说话人备选方案")
        return {
            "type": "diarization",
            "speakers": [{"speaker_id": "speaker_0", "total_duration": 0, "segment_count": 1, "text_segments": [text]}],
            "primary_speaker": {"speaker_id": "speaker_0", "total_duration": 0, "segment_count": 1},
            "speaker_segments": [{"speaker_id": "speaker_0", "text": text, "start_time": 0, "end_time": 0}],
            "total_speakers": 1,
            "processing_info": {
                "method": "fallback_single_speaker",
                "reason": "所有分离方法都失败"
            }
        }
        
    except Exception as e:
        logger.error(f"❌ 带时长处理的说话人分离失败: {e}")
        return None


async def async_asr_complete_pipeline(
    websocket: websockets.WebSocketServerProtocol,
    audio_in: bytes,
    server_state: ServerState,
    is_final: bool = False
) -> None:
    """完整的ASR处理pipeline，实现C++服务器的处理流程。
    
    处理流程：
    音频输入 → VAD检测 → 在线ASR(实时) → 离线ASR(精确) → 说话人识别/分离 → 热词增强 → ITN → 标点恢复 → 输出
    
    这个函数实现了与FunASR C++服务器完全一致的处理逻辑，包括：
    1. VAD语音活动检测
    2. 在线流式ASR（实时反馈）
    3. 离线高精度ASR（最终结果）
    4. 说话人识别/分离处理（智能切换）
    5. 热词增强处理
    6. ITN逆文本标准化
    7. 标点符号恢复
    8. 结果输出
    
    说话人处理策略：
    - 优先尝试说话人识别（基于已注册说话人）
    - 如果无已注册说话人或识别失败，自动切换到说话人分离
    - 说话人分离使用FunASR的内置功能，参考FunnyASR实现
    
    Args:
        websocket: WebSocket连接对象
        audio_in: 输入的音频数据 (PCM格式)
        server_state: 服务器状态对象
        is_final: 是否为最终音频段（语音结束）
        
    Raises:
        AudioProcessingError: 处理过程中发生错误时抛出异常
    """
    logger = server_state.logger
    args = server_state.args
    
    try:
        if len(audio_in) == 0:
            logger.debug("🔇 音频为空，跳过pipeline处理")
            return
        
        logger.debug(f"🔄 开始完整pipeline处理，音频长度: {len(audio_in)} bytes, 最终段: {is_final}")
        
        # ================================================================
        # 第1步：VAD语音活动检测或时长分割
        # ================================================================
        disable_vad = getattr(args, 'disable_vad', False)
        
        if disable_vad:
            logger.debug("⚡ VAD已禁用，使用时长分割模式")
            segment_duration_ms = getattr(args, 'segment_duration_ms', 30000)
            
            # 使用时长分割替代VAD
            vad_start_ms, vad_end_ms = segment_audio_by_duration(
                audio_in, 
                segment_duration_ms
            )
            
            logger.debug(f"⏱️ 时长分割结果: 开始={vad_start_ms}ms, 结束={vad_end_ms}ms")
        else:
            # 使用传统VAD检测
            vad_start_ms, vad_end_ms = await async_vad(
                websocket, audio_in, server_state
            )
        
        logger.debug(f"🎤 VAD检测结果: 开始={vad_start_ms}ms, 结束={vad_end_ms}ms")
        
        # 如果没有检测到语音活动，直接返回
        if vad_start_ms == -1 and vad_end_ms == -1 and not is_final:
            logger.debug("🔇 未检测到语音活动，跳过ASR处理")
            return
        
        # ================================================================
        # 第2步：在线ASR实时识别（低延迟反馈）
        # ================================================================
        online_text = ""
        if server_state.model_asr_streaming is not None and not is_final:
            try:
                logger.debug("🌊 开始在线ASR识别...")
                
                # 执行在线流式识别
                online_result = server_state.model_asr_streaming.generate(
                    input=audio_in,
                    **websocket.status_dict_asr_online
                )
                
                if online_result and len(online_result) > 0:
                    online_rec = online_result[0]
                    online_text = online_rec.get("text", "")
                    
                    # SenseVoiceSmall模型输出清理
                    if args.model_type == "sensevoice":
                        import re
                        online_text = re.sub(r'<\|[^|]*\|>', '', online_text).strip()
                    
                    # 发送在线识别结果（临时结果）
                    if online_text:
                        message_data = {
                            "mode": "pipeline-online",
                            "text": online_text,
                            "wav_name": websocket.wav_name,
                            "is_final": False,
                            "confidence": online_rec.get("confidence", 0.0),
                            "timestamp": time.time(),
                            "stage": "online_asr"
                        }
                        
                        message = json.dumps(message_data, ensure_ascii=False)
                        logger.debug(f"📤 [Pipeline-在线] 发送实时结果: '{online_text}'")
                        await websocket.send(message)
                        
            except Exception as e:
                logger.warning(f"⚠️ 在线ASR识别失败: {e}")
        
        # ================================================================
        # 第3步：离线ASR高精度识别（最终结果）
        # ================================================================
        if is_final and server_state.model_asr is not None:
            try:
                logger.debug("🎯 开始离线ASR识别...")
                
                # 执行离线高精度识别
                offline_result = server_state.model_asr.generate(
                    input=audio_in,
                    **websocket.status_dict_asr
                )
                
                if offline_result and len(offline_result) > 0:
                    offline_rec = offline_result[0]
                    offline_text = offline_rec.get("text", "")
                    
                    # SenseVoiceSmall模型输出清理
                    if args.model_type == "sensevoice":
                        import re
                        offline_text = re.sub(r'<\|[^|]*\|>', '', offline_text).strip()
                    
                    logger.debug(f"🎯 离线ASR原始结果: '{offline_text}'")
                    
                    # ================================================================
                    # 第4步：说话人识别/分离处理（智能时长优化）
                    # ================================================================
                    speaker_info = None
                    if getattr(websocket, 'enable_speaker_identification', False) and offline_text:
                        try:
                            logger.debug("👤 开始说话人识别/分离处理...")
                            
                            # 获取音频时长处理器
                            duration_handler = get_audio_duration_handler()
                            audio_duration = duration_handler.get_audio_duration_ms(audio_in)
                            logger.debug(f"📏 音频时长: {audio_duration}ms")
                            
                            # 获取说话人管理器
                            speaker_manager = get_speaker_manager()
                            
                            # 首先尝试说话人识别
                            if speaker_manager and speaker_manager.is_initialized:
                                logger.debug("🔍 尝试说话人识别...")
                                
                                # 验证和优化音频用于说话人识别
                                id_validation = validate_speaker_audio(audio_in, "identification")
                                
                                if id_validation["valid"] and id_validation["processed_audio"]:
                                    optimized_audio = id_validation["processed_audio"]
                                    logger.debug(f"✅ 音频已优化用于说话人识别: {id_validation['reason']}")
                                    
                                    # 执行说话人识别
                                    speaker_results = identify_speaker(
                                        optimized_audio, 
                                        top_k=getattr(websocket, 'speaker_top_k', 3)
                                    )
                                    
                                    if speaker_results and speaker_results.get("success"):
                                        # 提取音频特征向量用于临时说话人比较
                                        audio_embedding = None
                                        try:
                                            from ..speaker.speaker_verification import extract_embedding
                                            audio_embedding = extract_embedding(optimized_audio)
                                            logger.debug(f"成功提取音频特征向量，维度: {audio_embedding.shape}")
                                        except Exception as e:
                                            logger.warning(f"提取音频特征向量失败: {e}")
                                        
                                        # 使用说话人标记系统处理识别结果
                                        speaker_label_result = process_speaker_identification(speaker_results, audio_embedding)
                                        
                                        speaker_info = {
                                            "type": "identification",
                                            "speakers": speaker_results,
                                            "label_result": speaker_label_result,
                                            "primary_speaker": speaker_label_result.get("speaker_label", "未知"),
                                            "audio_optimization": {
                                                "original_duration_ms": audio_duration,
                                                "optimized_duration_ms": duration_handler.get_audio_duration_ms(optimized_audio),
                                                "optimization_reason": id_validation["reason"]
                                            }
                                        }
                                        
                                        speaker_label = speaker_label_result.get("speaker_label", "未知")
                                        speaker_type = speaker_label_result.get("speaker_type", "unknown")
                                        confidence = speaker_label_result.get("confidence", 0.0)
                                        
                                        if speaker_type == "registered":
                                            logger.debug(f"👤 识别为已注册说话人: {speaker_label} (置信度: {confidence:.3f})")
                                        elif speaker_type == "dynamic":
                                            logger.debug(f"👤 分配动态标签: {speaker_label} (相似度: {confidence:.3f})")
                                        else:
                                            logger.debug(f"👤 说话人标记: {speaker_label}")
                                    else:
                                        logger.debug("👤 说话人识别: 未识别到已注册说话人，尝试说话人分离")
                                        # 执行说话人分离
                                        speaker_info = await perform_speaker_diarization_with_duration_handling(
                                            audio_in, server_state, offline_text, logger
                                        )
                                else:
                                    logger.warning(f"⚠️ 音频不适合说话人识别: {id_validation['reason']}")
                                    logger.debug("🎭 直接尝试说话人分离")
                                    # 执行说话人分离
                                    speaker_info = await perform_speaker_diarization_with_duration_handling(
                                        audio_in, server_state, offline_text, logger
                                    )
                            else:
                                logger.debug("👤 说话人管理器未初始化，尝试说话人分离")
                                # 执行说话人分离
                                speaker_info = await perform_speaker_diarization_with_duration_handling(
                                    audio_in, server_state, offline_text, logger
                                )
                                
                        except Exception as e:
                            logger.warning(f"⚠️ 说话人识别/分离失败: {e}")
                            # 如果识别失败，尝试说话人分离作为备选方案
                            try:
                                speaker_info = await perform_speaker_diarization_with_duration_handling(
                                    audio_in, server_state, offline_text, logger
                                )
                            except Exception as e2:
                                logger.warning(f"⚠️ 说话人分离备选方案也失败: {e2}")
                    
                    # ================================================================
                    # 第5步：热词增强处理
                    # ================================================================
                    if server_state.hotword_map and offline_text:
                        try:
                            logger.debug("🔥 开始热词增强处理...")
                            enhanced_text = apply_hotword_boost(
                                offline_text,
                                server_state.hotword_map,
                                getattr(args, 'fst_inc_wts', 20)
                            )
                            if enhanced_text != offline_text:
                                logger.debug(f"🔥 热词增强: '{offline_text}' -> '{enhanced_text}'")
                                offline_text = enhanced_text
                        except Exception as e:
                            logger.warning(f"⚠️ 热词增强失败: {e}")
                    
                    # ================================================================
                    # 第6步：ITN逆文本标准化（已移除）
                    # ================================================================
                    # ITN功能已移除
                    
                    # ================================================================
                    # 第7步：标点符号恢复
                    # ================================================================
                    if server_state.model_punc is not None and offline_text:
                        try:
                            logger.debug("📝 开始标点恢复处理...")
                            
                            punc_result = server_state.model_punc.generate(
                                input=offline_text,
                                **websocket.status_dict_punc
                            )[0]
                            
                            punc_text = punc_result.get("text", offline_text)
                            if punc_text != offline_text:
                                logger.debug(f"📝 标点恢复: '{offline_text}' -> '{punc_text}'")
                                offline_text = punc_text
                        except Exception as e:
                            logger.warning(f"⚠️ 标点恢复失败: {e}")
                    
                    # ================================================================
                    # 第8步：结果输出
                    # ================================================================
                    if offline_text:
                        message_data = {
                            "mode": "pipeline-final",
                            "text": offline_text,
                            "wav_name": websocket.wav_name,
                            "is_final": True,
                            "confidence": offline_rec.get("confidence", 0.0),
                            "timestamp": time.time(),
                            "stage": "complete_pipeline",
                            "processing_stages": {
                                "vad": f"开始={vad_start_ms}ms, 结束={vad_end_ms}ms",
                                "online_asr": online_text if online_text else "跳过",
                                "offline_asr": "完成",
                                "speaker_identification": "完成" if speaker_info else "跳过",
                                "hotword": "完成" if server_state.hotword_map else "跳过",
                                "itn": "完成" if server_state.model_itn else "跳过",
                                "punctuation": "完成" if server_state.model_punc else "跳过"
                            }
                        }
                        
                        # 计算并添加绝对时间戳
                        if "timestamp" in offline_rec and offline_rec["timestamp"]:
                            # 获取基准时间（上次识别的时间点）
                            base_time_ms = getattr(websocket, 'last_offline_asr_time', 0)
                            
                            # 计算绝对时间戳：基准时间 + 相对时间
                            absolute_timestamps = []
                            for ts_pair in offline_rec["timestamp"]:
                                if len(ts_pair) >= 2:
                                    start_ms = ts_pair[0] + base_time_ms
                                    end_ms = ts_pair[1] + base_time_ms
                                    absolute_timestamps.append([start_ms, end_ms])
                            
                            message_data["asr_timestamp"] = absolute_timestamps
                            
                            # 添加格式化的时间范围
                            if absolute_timestamps:
                                start_time_str = format_timestamp_for_display(absolute_timestamps[0][0])
                                end_time_str = format_timestamp_for_display(absolute_timestamps[-1][1])
                                message_data["time_range"] = f"{start_time_str} - {end_time_str}"
                                message_data["start_time"] = start_time_str
                                message_data["end_time"] = end_time_str
                            
                            logger.debug(f"[Pipeline-最终] 时间戳计算: 基准={base_time_ms}ms, 相对={offline_rec['timestamp']}, 绝对={absolute_timestamps}")
                        
                        # 添加说话人识别信息（如果有）
                        if speaker_info:
                            message_data["speaker_info"] = speaker_info
                        
                        # 添加翻译功能（如果启用）
                        if getattr(websocket, 'enable_translation', False):
                            try:
                                translation = await local_translation.translate(offline_text)
                                if translation:
                                    message_data["translation"] = translation
                                    logger.debug(f"🌐 翻译结果: '{offline_text}' -> '{translation}'")
                            except Exception as e:
                                logger.warning(f"⚠️ 翻译失败: {e}")
                        
                        message = json.dumps(message_data, ensure_ascii=False)
                        logger.info(f"📤 [Pipeline-最终] 完整处理结果: '{offline_text}'")
                        await websocket.send(message)
                        
            except Exception as e:
                logger.error(f"❌ 离线ASR识别失败: {e}")
                raise AudioProcessingError(f"离线ASR识别失败: {e}") from e
        
        logger.debug(f"✅ 完整pipeline处理完成")
        
    except Exception as e:
        logger.error(f"❌ Pipeline处理过程中发生错误: {e}")
        logger.error(f"音频长度: {len(audio_in)}, 最终段: {is_final}")
        raise AudioProcessingError(f"Pipeline处理失败: {e}") from e
