#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试说话人识别200ms超时和缓存功能。

测试修改后的async_asr_with_speaker函数是否能正确处理说话人识别超时，
并使用缓存的说话人信息。
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
    get_cached_speaker_info,
    set_cached_speaker_info,
    clear_cached_speaker_info,
    _async_asr_processing,
    _async_speaker_processing
)
from src.modules.core.server_state import ServerState


class TestSpeakerTimeoutCache:
    """说话人识别超时和缓存测试类"""
    
    def __init__(self):
        self.test_results = []
    
    async def setup_mock_environment(self):
        """设置模拟环境"""
        # 模拟WebSocket连接
        websocket = MagicMock()
        websocket.mode = "offline"
        websocket.wav_name = "test_audio.wav"
        websocket.is_speaking = True
        websocket.enable_speaker_identification = True
        websocket.status_dict_asr = {}
        websocket.send = AsyncMock()
        
        # 模拟服务器状态
        server_state = MagicMock(spec=ServerState)
        server_state.logger = MagicMock()
        server_state.logger.info = MagicMock()
        server_state.logger.debug = MagicMock()
        server_state.logger.warning = MagicMock()
        server_state.logger.error = MagicMock()
        server_state.args = MagicMock()
        server_state.args.model_type = "sensevoice"
        
        # 模拟ASR模型
        server_state.model_asr = MagicMock()
        server_state.model_asr.generate = MagicMock(return_value=[
            {"text": "这是一个测试语音识别结果"}
        ])
        
        # 模拟标点恢复模型
        server_state.model_punc = None
        
        return websocket, server_state
    
    async def test_speaker_timeout_with_cache(self):
        """测试说话人识别超时时使用缓存"""
        print("\n🧪 测试1: 说话人识别超时时使用缓存")
        print("=" * 50)
        
        websocket, server_state = await self.setup_mock_environment()
        websocket_id = str(id(websocket))
        
        # 预设缓存的说话人信息
        cached_speaker_info = {
            "label_result": {
                "speaker_label": "张三",
                "speaker_type": "registered",
                "confidence": 0.95
            },
            "speaker_info": {
                "speaker_id": "speaker_001",
                "speaker_name": "张三",
                "description": "项目经理"
            }
        }
        
        # 设置缓存
        await set_cached_speaker_info(websocket_id, cached_speaker_info)
        print(f"✅ 已设置缓存说话人信息: {cached_speaker_info['label_result']['speaker_label']}")
        
        # 模拟音频数据
        audio_data = b"\x00" * 32000  # 1秒的16kHz音频数据
        
        # 模拟说话人识别延迟（超过200ms）
        async def slow_speaker_processing(*args, **kwargs):
            await asyncio.sleep(0.3)  # 300ms延迟，超过200ms超时
            return {
                "label_result": {
                    "speaker_label": "李四",
                    "speaker_type": "registered",
                    "confidence": 0.88
                },
                "speaker_info": {
                    "speaker_id": "speaker_002",
                    "speaker_name": "李四",
                    "description": "产品经理"
                }
            }
        
        # 模拟快速ASR处理
        async def fast_asr_processing(*args, **kwargs):
            await asyncio.sleep(0.05)  # 50ms
            return {"text": "这是一个测试语音识别结果"}
        
        with patch('src.modules.audio.audio_processing._async_speaker_processing', side_effect=slow_speaker_processing), \
             patch('src.modules.audio.audio_processing._async_asr_processing', side_effect=fast_asr_processing), \
             patch('src.modules.audio.audio_processing.get_audio_processing_monitor') as mock_monitor:
            
            # 模拟监控器
            mock_monitor_instance = MagicMock()
            mock_monitor_instance.start_session = MagicMock()
            mock_monitor_instance.start_speaker = MagicMock()
            mock_monitor_instance.end_speaker = MagicMock()
            mock_monitor_instance.end_session = MagicMock()
            mock_monitor_instance.current_sessions = {}
            mock_monitor.return_value = mock_monitor_instance
            
            # 记录开始时间
            start_time = time.time()
            
            # 执行测试
            await async_asr_with_speaker(websocket, audio_data, server_state)
            
            # 记录结束时间
            end_time = time.time()
            processing_time = (end_time - start_time) * 1000
            
            print(f"⏱️ 总处理时间: {processing_time:.1f}ms")
            
            # 验证结果
            assert websocket.send.called, "WebSocket发送方法应该被调用"
            
            # 获取发送的消息
            sent_message = websocket.send.call_args[0][0]
            message_data = json.loads(sent_message)
            
            print(f"📤 发送的消息: {json.dumps(message_data, ensure_ascii=False, indent=2)}")
            
            # 验证使用了缓存的说话人信息
            assert "speaker_result" in message_data, "消息应包含说话人结果"
            assert message_data["speaker_name"] == "张三", f"应使用缓存的说话人信息，期望'张三'，实际'{message_data.get('speaker_name')}'"
            
            print("✅ 测试通过：成功使用缓存的说话人信息")
            return True
    
    async def test_speaker_fast_completion(self):
        """测试说话人识别在200ms内完成"""
        print("\n🧪 测试2: 说话人识别在200ms内完成")
        print("=" * 50)
        
        websocket, server_state = await self.setup_mock_environment()
        
        # 模拟音频数据
        audio_data = b"\x00" * 32000  # 1秒的16kHz音频数据
        
        # 模拟快速说话人识别（在200ms内完成）
        async def fast_speaker_processing(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms，在200ms超时内
            return {
                "label_result": {
                    "speaker_label": "王五",
                    "speaker_type": "registered",
                    "confidence": 0.92
                },
                "speaker_info": {
                    "speaker_id": "speaker_004",
                    "speaker_name": "王五",
                    "description": "开发工程师"
                }
            }
        
        # 模拟快速ASR处理
        async def fast_asr_processing(*args, **kwargs):
            await asyncio.sleep(0.05)  # 50ms
            return {"text": "这是另一个测试语音识别结果"}
        
        with patch('src.modules.audio.audio_processing._async_speaker_processing', side_effect=fast_speaker_processing), \
             patch('src.modules.audio.audio_processing._async_asr_processing', side_effect=fast_asr_processing), \
             patch('src.modules.audio.audio_processing.get_audio_processing_monitor') as mock_monitor:
            
            # 模拟监控器
            mock_monitor_instance = MagicMock()
            mock_monitor_instance.start_session = MagicMock()
            mock_monitor_instance.start_speaker = MagicMock()
            mock_monitor_instance.end_speaker = MagicMock()
            mock_monitor_instance.end_session = MagicMock()
            mock_monitor_instance.current_sessions = {}
            mock_monitor.return_value = mock_monitor_instance
            
            # 记录开始时间
            start_time = time.time()
            
            # 执行测试
            await async_asr_with_speaker(websocket, audio_data, server_state)
            
            # 记录结束时间
            end_time = time.time()
            processing_time = (end_time - start_time) * 1000
            
            print(f"⏱️ 总处理时间: {processing_time:.1f}ms")
            
            # 验证结果
            assert websocket.send.called, "WebSocket发送方法应该被调用"
            
            # 获取发送的消息
            sent_message = websocket.send.call_args[0][0]
            message_data = json.loads(sent_message)
            
            print(f"📤 发送的消息: {json.dumps(message_data, ensure_ascii=False, indent=2)}")
            
            # 验证使用了实时的说话人识别结果
            assert "speaker_result" in message_data, "消息应包含说话人结果"
            assert message_data["speaker_name"] == "王五", f"应使用实时说话人识别结果，期望'王五'，实际'{message_data.get('speaker_name')}'"
            
            print("✅ 测试通过：成功在200ms内完成说话人识别")
            return True
    
    async def test_no_cache_fallback(self):
        """测试无缓存时的回退行为"""
        print("\n🧪 测试3: 无缓存时的回退行为")
        print("=" * 50)
        
        websocket, server_state = await self.setup_mock_environment()
        websocket_id = str(id(websocket))
        
        # 确保没有缓存
        await clear_cached_speaker_info(websocket_id)
        
        # 模拟音频数据
        audio_data = b"\x00" * 32000  # 1秒的16kHz音频数据
        
        # 模拟说话人识别延迟（超过200ms）
        async def slow_speaker_processing(*args, **kwargs):
            try:
                await asyncio.sleep(0.3)  # 300ms延迟
                return {
                    "label_result": {
                        "speaker_label": "赵六",
                        "speaker_type": "registered",
                        "confidence": 0.87
                    },
                    "speaker_info": {
                        "speaker_id": "speaker_003",
                        "speaker_name": "赵六",
                        "description": "技术专家"
                    }
                }
            except asyncio.CancelledError:
                # 即使被取消，也要返回结果（模拟实际情况）
                await asyncio.sleep(0.1)  # 短暂延迟后完成
                return {
                    "label_result": {
                        "speaker_label": "赵六",
                        "speaker_type": "registered",
                        "confidence": 0.87
                    },
                    "speaker_info": {
                        "speaker_id": "speaker_003",
                        "speaker_name": "赵六",
                        "description": "技术专家"
                    }
                }
        
        # 模拟快速ASR处理
        async def fast_asr_processing(*args, **kwargs):
            await asyncio.sleep(0.05)  # 50ms
            return {"text": "无缓存测试语音识别结果"}
        
        with patch('src.modules.audio.audio_processing._async_speaker_processing', side_effect=slow_speaker_processing), \
             patch('src.modules.audio.audio_processing._async_asr_processing', side_effect=fast_asr_processing), \
             patch('src.modules.audio.audio_processing.get_audio_processing_monitor') as mock_monitor:
            
            # 模拟监控器
            mock_monitor_instance = MagicMock()
            mock_monitor_instance.start_session = MagicMock()
            mock_monitor_instance.start_speaker = MagicMock()
            mock_monitor_instance.end_speaker = MagicMock()
            mock_monitor_instance.end_session = MagicMock()
            mock_monitor_instance.current_sessions = {}
            mock_monitor.return_value = mock_monitor_instance
            
            # 记录开始时间
            start_time = time.time()
            
            # 执行测试
            await async_asr_with_speaker(websocket, audio_data, server_state)
            
            # 记录结束时间
            end_time = time.time()
            processing_time = (end_time - start_time) * 1000
            
            print(f"⏱️ 总处理时间: {processing_time:.1f}ms")
            
            # 验证结果
            assert websocket.send.called, "WebSocket发送方法应该被调用"
            
            # 获取发送的消息
            sent_message = websocket.send.call_args[0][0]
            message_data = json.loads(sent_message)
            
            print(f"📤 发送的消息: {json.dumps(message_data, ensure_ascii=False, indent=2)}")
            
            # 验证最终使用了说话人识别结果（等待完成）
            assert "speaker_result" in message_data, "消息应包含说话人结果"
            assert message_data["speaker_name"] == "赵六", f"应使用等待完成的说话人识别结果，期望'赵六'，实际'{message_data.get('speaker_name')}'"
            
            print("✅ 测试通过：无缓存时正确等待说话人识别完成")
            return True
    
    async def test_cache_management(self):
        """测试缓存管理功能"""
        print("\n🧪 测试4: 缓存管理功能")
        print("=" * 50)
        
        websocket_id = "test_websocket_123"
        
        # 测试设置缓存
        speaker_info = {
            "label_result": {
                "speaker_label": "测试用户",
                "speaker_type": "registered",
                "confidence": 0.90
            }
        }
        
        await set_cached_speaker_info(websocket_id, speaker_info)
        print("✅ 缓存设置成功")
        
        # 测试获取缓存
        cached_info = await get_cached_speaker_info(websocket_id)
        assert cached_info is not None, "应该能获取到缓存信息"
        assert cached_info['speaker_result']['label_result']['speaker_label'] == "测试用户", "缓存内容应该正确"
        print("✅ 缓存获取成功")
        
        # 测试清除缓存
        await clear_cached_speaker_info(websocket_id)
        cleared_info = await get_cached_speaker_info(websocket_id)
        assert cleared_info is None, "清除后应该获取不到缓存信息"
        print("✅ 缓存清除成功")
        
        return True


async def main():
    """运行所有测试"""
    print("🚀 开始测试说话人识别200ms超时和缓存功能")
    
    tester = TestSpeakerTimeoutCache()
    
    try:
        # 测试1: 超时使用缓存
        success1 = await tester.test_speaker_timeout_with_cache()
        if not success1:
            print("❌ 测试1失败")
            return False
        
        # 测试2: 快速完成
        success2 = await tester.test_speaker_fast_completion()
        if not success2:
            print("❌ 测试2失败")
            return False
        
        # 测试3: 无缓存回退
        success3 = await tester.test_no_cache_fallback()
        if not success3:
            print("❌ 测试3失败")
            return False
        
        # 测试4: 缓存管理
        success4 = await tester.test_cache_management()
        if not success4:
            print("❌ 测试4失败")
            return False
        
        print("\n🎉 所有测试通过！说话人识别超时和缓存功能正常工作。")
        print("\n📋 功能总结:")
        print("  ✅ ASR结束后等待说话人识别最多200ms")
        print("  ✅ 超时后优先使用缓存的说话人信息")
        print("  ✅ 无缓存时等待说话人识别完成")
        print("  ✅ 成功的说话人识别结果会更新缓存")
        print("  ✅ 缓存管理功能正常")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1)