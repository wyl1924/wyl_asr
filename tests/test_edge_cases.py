#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试边界情况和异常处理。

测试空音频、异常情况等边界条件的处理。
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


async def test_empty_audio_asr():
    """测试空音频的ASR处理。"""
    print("🧪 测试1: 空音频ASR处理")
    print("=" * 50)
    
    websocket = create_mock_websocket()
    server_state = create_mock_server_state()
    empty_audio = b""  # 空音频数据
    
    result = await _async_asr_processing(websocket, empty_audio, server_state)
    
    print(f"✅ 空音频ASR处理完成")
    print(f"📝 识别结果: '{result.get('text', '')}'")
    
    assert result is not None
    assert result.get("text") == ""
    print("✅ 空音频ASR处理测试通过")


async def test_empty_audio_speaker():
    """测试空音频的说话人识别。"""
    print("\n🧪 测试2: 空音频说话人识别")
    print("=" * 50)
    
    websocket = create_mock_websocket()
    server_state = create_mock_server_state()
    empty_audio = b""  # 空音频数据
    
    result = await _async_speaker_processing(websocket, empty_audio, server_state)
    
    print(f"✅ 空音频说话人识别完成")
    print(f"👤 识别结果: {result}")
    
    assert result is None
    print("✅ 空音频说话人识别测试通过")


async def test_disabled_speaker_identification():
    """测试禁用说话人识别的情况。"""
    print("\n🧪 测试3: 禁用说话人识别")
    print("=" * 50)
    
    websocket = create_mock_websocket()
    websocket.enable_speaker_identification = False  # 禁用说话人识别
    server_state = create_mock_server_state()
    audio_data = b"fake_audio_data" * 1000
    
    result = await _async_speaker_processing(websocket, audio_data, server_state)
    
    print(f"✅ 禁用说话人识别处理完成")
    print(f"👤 识别结果: {result}")
    
    assert result is None
    print("✅ 禁用说话人识别测试通过")


async def test_asr_exception_handling():
    """测试ASR异常处理。"""
    print("\n🧪 测试4: ASR异常处理")
    print("=" * 50)
    
    websocket = create_mock_websocket()
    server_state = create_mock_server_state()
    
    # 模拟ASR模型抛出异常
    server_state.model_asr.generate.side_effect = Exception("模拟ASR错误")
    
    audio_data = b"fake_audio_data" * 1000
    
    try:
        result = await _async_asr_processing(websocket, audio_data, server_state)
        print("❌ 应该抛出异常但没有")
        assert False, "应该抛出异常"
    except Exception as e:
        print(f"✅ 正确捕获异常: {e}")
        assert "ASR处理失败" in str(e)
        print("✅ ASR异常处理测试通过")


async def test_full_function_empty_audio():
    """测试完整函数处理空音频。"""
    print("\n🧪 测试5: 完整函数空音频处理")
    print("=" * 50)
    
    websocket = create_mock_websocket()
    server_state = create_mock_server_state()
    empty_audio = b""  # 空音频数据
    
    await async_asr_with_speaker(websocket, empty_audio, server_state)
    
    print(f"✅ 完整函数空音频处理完成")
    
    # 验证WebSocket发送被调用
    assert websocket.send.called
    print("✅ WebSocket消息发送正常")
    
    # 检查发送的消息内容
    sent_message = websocket.send.call_args[0][0]
    message_data = json.loads(sent_message)
    
    assert message_data["text"] == ""
    assert "speaker_result" not in message_data  # 空音频不应该有说话人结果
    print("✅ 空音频消息格式正确")
    print("✅ 完整函数空音频处理测试通过")


async def test_parallel_with_mixed_conditions():
    """测试混合条件下的并行处理。"""
    print("\n🧪 测试6: 混合条件并行处理")
    print("=" * 50)
    
    websocket = create_mock_websocket()
    server_state = create_mock_server_state()
    audio_data = b"fake_audio_data" * 1000
    
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
        
        # 测试正常音频数据的并行处理
        asr_task = _async_asr_processing(websocket, audio_data, server_state)
        speaker_task = _async_speaker_processing(websocket, audio_data, server_state)
        
        asr_result, speaker_result = await asyncio.gather(asr_task, speaker_task)
        
        print(f"✅ 混合条件并行处理完成")
        print(f"📝 ASR结果: {asr_result.get('text', '')}")
        print(f"👤 说话人结果: {speaker_result.get('label_result', {}).get('speaker_label', '无') if speaker_result else '无'}")
        
        assert asr_result is not None
        assert asr_result.get("text") == "这是一个测试音频"
        assert speaker_result is not None
        assert speaker_result.get("label_result", {}).get("speaker_label") == "测试说话人"
        
        print("✅ 混合条件并行处理测试通过")


async def main():
    """主测试函数。"""
    print("🎯 边界情况和异常处理测试")
    print("=" * 60)
    
    try:
        # 运行所有测试
        await test_empty_audio_asr()
        await test_empty_audio_speaker()
        await test_disabled_speaker_identification()
        await test_asr_exception_handling()
        await test_full_function_empty_audio()
        await test_parallel_with_mixed_conditions()
        
        print("\n🎉 所有边界测试通过！")
        print("✅ 空音频处理正常")
        print("✅ 异常处理机制有效")
        print("✅ 边界条件处理正确")
        
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
        print("\n🎯 测试结论: 边界情况和异常处理完善！")
    else:
        print("\n❌ 测试结论: 需要进一步调试")
        sys.exit(1)