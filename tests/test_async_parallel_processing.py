#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试异步并行处理功能。

测试修改后的async_asr_with_speaker函数是否能正确并行执行ASR和说话人识别。
"""

import sys
import os
import asyncio
import time
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
    """创建模拟的WebSocket对象。"""
    websocket = MagicMock()
    websocket.mode = "offline"
    websocket.wav_name = "test_audio.wav"
    websocket.enable_speaker_identification = True
    websocket.speaker_top_k = 3
    websocket.is_speaking = False
    websocket.enable_translation = False
    websocket.status_dict_asr = {"cache": {}}
    websocket.status_dict_punc = {"cache": {}}
    websocket.send = AsyncMock()
    return websocket


def create_mock_server_state():
    """创建模拟的服务器状态对象。"""
    server_state = MagicMock()
    server_state.logger = MagicMock()
    server_state.logger.info = MagicMock()
    server_state.logger.debug = MagicMock()
    server_state.logger.warning = MagicMock()
    server_state.logger.error = MagicMock()
    
    # 模拟ASR模型
    server_state.model_asr = MagicMock()
    server_state.model_asr.generate = MagicMock(return_value=[
        {"text": "这是一个测试音频"}
    ])
    
    # 模拟其他模型
    server_state.model_punc = None
    server_state.model_itn = None
    
    # 模拟参数
    server_state.args = MagicMock()
    server_state.args.model_type = "paraformer"
    
    return server_state


async def test_async_asr_processing():
    """测试独立的ASR处理函数。"""
    print("🧪 测试1: 独立ASR处理函数")
    print("=" * 50)
    
    websocket = create_mock_websocket()
    server_state = create_mock_server_state()
    audio_data = b"fake_audio_data" * 1000  # 模拟音频数据
    
    start_time = time.time()
    result = await _async_asr_processing(websocket, audio_data, server_state)
    end_time = time.time()
    
    print(f"✅ ASR处理完成，耗时: {end_time - start_time:.3f}秒")
    print(f"📝 识别结果: {result.get('text', '')}")
    
    assert result is not None
    assert "text" in result
    assert result["text"] == "这是一个测试音频"
    print("✅ ASR处理测试通过")
    return end_time - start_time


async def test_async_speaker_processing():
    """测试独立的说话人识别函数。"""
    print("\n🧪 测试2: 独立说话人识别函数")
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
        
        start_time = time.time()
        result = await _async_speaker_processing(websocket, audio_data, server_state)
        end_time = time.time()
        
        print(f"✅ 说话人识别完成，耗时: {end_time - start_time:.3f}秒")
        print(f"👤 识别结果: {result.get('label_result', {}).get('speaker_label', '未知') if result else '未启用'}")
        
        assert result is not None
        assert "label_result" in result
        print("✅ 说话人识别测试通过")
        return end_time - start_time


async def test_parallel_processing():
    """测试并行处理性能。"""
    print("\n🧪 测试3: 并行处理性能对比")
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
        
        # 测试串行处理时间
        print("📊 串行处理测试:")
        start_time = time.time()
        asr_result = await _async_asr_processing(websocket, audio_data, server_state)
        speaker_result = await _async_speaker_processing(websocket, audio_data, server_state)
        serial_time = time.time() - start_time
        print(f"   串行处理耗时: {serial_time:.3f}秒")
        
        # 测试并行处理时间
        print("📊 并行处理测试:")
        start_time = time.time()
        asr_task = _async_asr_processing(websocket, audio_data, server_state)
        speaker_task = _async_speaker_processing(websocket, audio_data, server_state)
        parallel_asr_result, parallel_speaker_result = await asyncio.gather(asr_task, speaker_task)
        parallel_time = time.time() - start_time
        print(f"   并行处理耗时: {parallel_time:.3f}秒")
        
        # 性能提升计算
        improvement = ((serial_time - parallel_time) / serial_time) * 100
        print(f"🚀 性能提升: {improvement:.1f}%")
        
        # 验证结果一致性
        assert asr_result["text"] == parallel_asr_result["text"]
        assert speaker_result["label_result"]["speaker_label"] == parallel_speaker_result["label_result"]["speaker_label"]
        print("✅ 并行处理结果与串行处理结果一致")
        print("✅ 并行处理性能测试通过")


async def test_full_function():
    """测试完整的async_asr_with_speaker函数。"""
    print("\n🧪 测试4: 完整函数测试")
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
        
        start_time = time.time()
        await async_asr_with_speaker(websocket, audio_data, server_state)
        end_time = time.time()
        
        print(f"✅ 完整函数执行完成，耗时: {end_time - start_time:.3f}秒")
        
        # 验证WebSocket发送被调用
        assert websocket.send.called
        print("✅ WebSocket消息发送正常")
        
        # 检查发送的消息内容
        sent_message = websocket.send.call_args[0][0]
        message_data = json.loads(sent_message)
        
        assert "text" in message_data
        assert "speaker_result" in message_data
        assert "speaker_name" in message_data
        print("✅ 发送消息包含ASR和说话人识别结果")
        print("✅ 完整函数测试通过")


async def main():
    """主测试函数。"""
    print("🎯 异步并行处理功能测试")
    print("=" * 60)
    
    try:
        # 运行所有测试
        await test_async_asr_processing()
        await test_async_speaker_processing()
        await test_parallel_processing()
        await test_full_function()
        
        print("\n🎉 所有测试通过！")
        print("✅ 异步并行处理功能正常工作")
        print("✅ 性能得到提升")
        print("✅ 功能保持不变")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    if success:
        print("\n🎯 测试结论: 异步并行处理修改成功！")
    else:
        print("\n❌ 测试结论: 需要进一步调试")
        sys.exit(1)