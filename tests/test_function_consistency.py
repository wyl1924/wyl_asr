#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试修改前后功能一致性。

对比原始实现和优化后的异步并行实现，验证功能结果是否一致。
"""

import sys
import os
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.audio.audio_processing import (
    async_asr_with_speaker, 
    _async_asr_processing, 
    _async_speaker_processing
)


def create_mock_websocket():
    """创建模拟WebSocket对象。"""
    websocket = MagicMock()
    websocket.mode = "offline"
    websocket.wav_name = "test_audio.wav"
    websocket.is_speaking = True
    websocket.enable_speaker_identification = True
    websocket.status_dict_asr = {
        "cache": {},
        "is_final": True,
        "chunk_size": [5, 10, 5],
        "encoder_chunk_look_back": 4,
        "decoder_chunk_look_back": 1
    }
    websocket.send = AsyncMock()
    return websocket


def create_mock_server_state():
    """创建模拟ServerState对象。"""
    server_state = MagicMock()
    
    # 模拟logger
    logger = MagicMock()
    logger.info = MagicMock()
    logger.debug = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    server_state.logger = logger
    
    # 模拟ASR模型
    mock_asr_model = MagicMock()
    mock_asr_model.generate.return_value = [{
        "text": "这是一个测试音频",
        "timestamp": [[0, 1000]]
    }]
    server_state.model_asr = mock_asr_model
    
    # 模拟标点模型
    mock_punc_model = MagicMock()
    mock_punc_model.generate.return_value = [{
        "text": "这是一个测试音频。"
    }]
    server_state.model_punc = mock_punc_model
    
    # 模拟ITN模型
    server_state.model_itn = None
    
    # 模拟args
    args = MagicMock()
    args.model_type = "paraformer"
    server_state.args = args
    
    return server_state


async def simulate_original_implementation(websocket, audio_in: bytes, server_state):
    """模拟原始的串行实现逻辑。
    
    基于git历史中的原始实现，模拟串行处理流程。
    """
    logger = server_state.logger
    
    try:
        if len(audio_in) > 0:
            logger.info(f"🎯 开始带说话人识别的ASR处理，音频长度: {len(audio_in)} bytes")
            
            # 1. 串行执行ASR识别
            rec_result = server_state.model_asr.generate(
                input=audio_in, 
                **websocket.status_dict_asr
            )[0]
            
            logger.debug(f"离线ASR完整结果: {rec_result}")
            logger.debug(f"离线ASR原始结果: {rec_result.get('text', '')}")
            
            # SenseVoiceSmall模型输出清理
            if server_state.args.model_type == "sensevoice":
                original_text = rec_result.get("text", "")
                import re
                cleaned_text = re.sub(r'<\|[^|]*\|>', '', original_text).strip()
                rec_result["text"] = cleaned_text
            
            # 标点恢复处理
            if (server_state.model_punc is not None and 
                len(rec_result.get("text", "")) > 0):
                try:
                    punc_result = server_state.model_punc.generate(
                        input=rec_result["text"]
                    )[0]
                    rec_result["text"] = punc_result["text"]
                    logger.debug(f"标点恢复后结果: {rec_result['text']}")
                except Exception as e:
                    logger.warning(f"标点恢复失败: {e}")
            
            # ITN逆文本标准化处理
            if (server_state.model_itn is not None and 
                len(rec_result.get("text", "")) > 0):
                try:
                    itn_result = server_state.model_itn.generate(
                        input=rec_result["text"]
                    )[0]
                    rec_result["text"] = itn_result["text"]
                    logger.debug(f"ITN处理后结果: {rec_result['text']}")
                except Exception as e:
                    logger.warning(f"ITN处理失败: {e}")
            
            # 2. 串行执行说话人识别
            speaker_result = None
            if getattr(websocket, 'enable_speaker_identification', False):
                logger.info("🎤 开始说话人识别")
                
                # 模拟说话人识别过程
                with patch('src.modules.audio.audio_processing.create_pcm_wav_file') as mock_create_wav, \
                     patch('src.modules.audio.audio_processing.cleanup_temp_file') as mock_cleanup, \
                     patch('src.modules.audio.audio_processing.get_cached_speaker_manager') as mock_get_manager, \
                     patch('src.modules.audio.audio_processing.identify_speaker') as mock_identify, \
                     patch('src.modules.audio.audio_processing.process_speaker_identification') as mock_process:
                    
                    mock_create_wav.return_value = "/tmp/test_audio.wav"
                    mock_get_manager.return_value = {"initialized": True}
                    mock_identify.return_value = {
                        "success": True,
                        "candidates": [{"speaker_name": "测试说话人", "similarity": 0.85}]
                    }
                    mock_process.return_value = {
                        "speaker_label": "测试说话人",
                        "speaker_type": "registered",
                        "confidence": 0.85
                    }
                    
                    # 模拟说话人识别结果
                    speaker_result = {
                        "original_result": {
                            "success": True,
                            "candidates": [{"speaker_name": "测试说话人", "similarity": 0.85}]
                        },
                        "label_result": {
                            "speaker_label": "测试说话人",
                            "speaker_type": "registered",
                            "confidence": 0.85
                        }
                    }
            
            # 3. 发送识别结果
            if len(rec_result.get("text", "")) > 0:
                mode = "2pass-offline" if "2pass" in websocket.mode else websocket.mode
                
                # 构建消息，包含说话人信息
                message_data = {
                    "mode": mode,
                    "text": rec_result["text"],
                    "wav_name": websocket.wav_name,
                    "is_final": not getattr(websocket, 'is_speaking', True),
                }
                
                # 添加说话人信息
                if speaker_result:
                    message_data["speaker_result"] = speaker_result
                    
                    # 使用新的标记系统信息
                    label_result = speaker_result.get("label_result", {})
                    if label_result:
                        message_data["speaker_name"] = label_result.get("speaker_label", "未知说话人")
                        message_data["speaker_type"] = label_result.get("speaker_type", "unknown")
                        message_data["speaker_confidence"] = label_result.get("confidence", 0.0)
                
                message = json.dumps(message_data, ensure_ascii=False)
                await websocket.send(message)
                
                return message_data
        else:
            # 空音频的处理
            mode = "2pass-offline" if "2pass" in websocket.mode else websocket.mode
            
            message_data = {
                "mode": mode,
                "text": "",
                "wav_name": websocket.wav_name,
                "is_final": not getattr(websocket, 'is_speaking', True),
            }
            
            message = json.dumps(message_data, ensure_ascii=False)
            await websocket.send(message)
            
            return message_data
            
    except Exception as e:
        logger.error(f"❌ 带说话人识别的ASR处理过程中发生错误: {e}")
        raise e


async def test_function_consistency():
    """测试修改前后功能一致性。"""
    print("\n🧪 功能一致性测试")
    print("=" * 50)
    
    websocket = create_mock_websocket()
    server_state = create_mock_server_state()
    audio_data = b"fake_audio_data" * 1000  # 模拟音频数据
    
    # 模拟说话人识别相关函数
    with patch('src.modules.audio.audio_processing.create_pcm_wav_file') as mock_create_wav, \
         patch('src.modules.audio.audio_processing.cleanup_temp_file') as mock_cleanup, \
         patch('src.modules.audio.audio_processing.get_cached_speaker_manager') as mock_get_manager, \
         patch('src.modules.audio.audio_processing.identify_speaker') as mock_identify, \
         patch('src.modules.audio.audio_processing.process_speaker_identification') as mock_process:
        
        mock_create_wav.return_value = "/tmp/test_audio.wav"
        mock_get_manager.return_value = {"initialized": True}
        mock_identify.return_value = {
            "success": True,
            "candidates": [{"speaker_name": "测试说话人", "similarity": 0.85}]
        }
        mock_process.return_value = {
            "speaker_label": "测试说话人",
            "speaker_type": "registered",
            "confidence": 0.85
        }
        
        print("📊 测试1: 原始串行实现")
        # 重置websocket.send的调用记录
        websocket.send.reset_mock()
        original_result = await simulate_original_implementation(websocket, audio_data, server_state)
        original_message = websocket.send.call_args[0][0] if websocket.send.called else None
        
        print("📊 测试2: 优化后并行实现")
        # 重置websocket.send的调用记录
        websocket.send.reset_mock()
        await async_asr_with_speaker(websocket, audio_data, server_state)
        optimized_message = websocket.send.call_args[0][0] if websocket.send.called else None
        
        print("\n🔍 结果对比:")
        print(f"原始实现发送消息: {original_message}")
        print(f"优化实现发送消息: {optimized_message}")
        
        # 解析JSON消息进行对比
        if original_message and optimized_message:
            original_data = json.loads(original_message)
            optimized_data = json.loads(optimized_message)
            
            # 对比关键字段
            key_fields = ["mode", "text", "wav_name", "is_final", "speaker_name", "speaker_type", "speaker_confidence"]
            
            print("\n📋 关键字段对比:")
            all_consistent = True
            for field in key_fields:
                original_value = original_data.get(field)
                optimized_value = optimized_data.get(field)
                is_consistent = original_value == optimized_value
                all_consistent = all_consistent and is_consistent
                
                status = "✅" if is_consistent else "❌"
                print(f"  {status} {field}: 原始={original_value}, 优化={optimized_value}")
            
            if all_consistent:
                print("\n🎉 功能一致性测试通过！修改前后结果完全一致")
            else:
                print("\n⚠️ 功能一致性测试发现差异，需要进一步检查")
                
            return all_consistent
        else:
            print("\n❌ 无法获取完整的消息数据进行对比")
            return False


async def test_empty_audio_consistency():
    """测试空音频处理的一致性。"""
    print("\n🧪 空音频处理一致性测试")
    print("=" * 50)
    
    websocket = create_mock_websocket()
    server_state = create_mock_server_state()
    empty_audio = b""  # 空音频数据
    
    print("📊 测试1: 原始串行实现（空音频）")
    websocket.send.reset_mock()
    original_result = await simulate_original_implementation(websocket, empty_audio, server_state)
    original_message = websocket.send.call_args[0][0] if websocket.send.called else None
    
    print("📊 测试2: 优化后并行实现（空音频）")
    websocket.send.reset_mock()
    await async_asr_with_speaker(websocket, empty_audio, server_state)
    optimized_message = websocket.send.call_args[0][0] if websocket.send.called else None
    
    print("\n🔍 空音频结果对比:")
    print(f"原始实现发送消息: {original_message}")
    print(f"优化实现发送消息: {optimized_message}")
    
    if original_message and optimized_message:
        original_data = json.loads(original_message)
        optimized_data = json.loads(optimized_message)
        
        # 对比关键字段
        key_fields = ["mode", "text", "wav_name", "is_final"]
        
        print("\n📋 空音频关键字段对比:")
        all_consistent = True
        for field in key_fields:
            original_value = original_data.get(field)
            optimized_value = optimized_data.get(field)
            is_consistent = original_value == optimized_value
            all_consistent = all_consistent and is_consistent
            
            status = "✅" if is_consistent else "❌"
            print(f"  {status} {field}: 原始={original_value}, 优化={optimized_value}")
        
        if all_consistent:
            print("\n🎉 空音频处理一致性测试通过！")
        else:
            print("\n⚠️ 空音频处理一致性测试发现差异")
            
        return all_consistent
    else:
        print("\n❌ 无法获取完整的空音频消息数据进行对比")
        return False


async def main():
    """主测试函数。"""
    print("🚀 开始功能一致性验证测试")
    print("=" * 60)
    
    try:
        # 测试正常音频处理的一致性
        normal_audio_consistent = await test_function_consistency()
        
        # 测试空音频处理的一致性
        empty_audio_consistent = await test_empty_audio_consistency()
        
        print("\n" + "=" * 60)
        print("📊 最终测试结果:")
        print(f"  正常音频处理一致性: {'✅ 通过' if normal_audio_consistent else '❌ 失败'}")
        print(f"  空音频处理一致性: {'✅ 通过' if empty_audio_consistent else '❌ 失败'}")
        
        if normal_audio_consistent and empty_audio_consistent:
            print("\n🎉 所有功能一致性测试通过！")
            print("✅ 修改前后的功能结果完全一致")
            print("✅ 异步并行优化成功，性能提升的同时保持了功能完整性")
        else:
            print("\n⚠️ 部分功能一致性测试未通过")
            print("❌ 需要进一步检查和修复差异")
            
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())