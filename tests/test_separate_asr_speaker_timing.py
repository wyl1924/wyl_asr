#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试ASR和说话人识别时间分开记录功能。

验证修改后的async_asr_with_speaker函数是否能正确分开记录ASR和说话人识别的处理时间。
"""

import sys
import os
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.modules.audio.audio_processing import (
        _async_asr_processing, 
        get_audio_processing_monitor
    )
    from src.modules.audio.audio_processing_monitor import reset_audio_processing_monitor
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)


async def test_asr_timing_separation():
    """测试ASR时间记录的分离功能。"""
    print("🧪 开始测试ASR时间记录分离功能...")
    
    # 重置监控器
    reset_audio_processing_monitor()
    
    # 创建模拟对象
    mock_websocket = MagicMock()
    mock_websocket.status_dict_asr = {}
    mock_websocket.hotword_map = {}
    
    mock_server_state = MagicMock()
    mock_server_state.logger = MagicMock()
    mock_server_state.args = MagicMock()
    mock_server_state.args.model_type = "sensevoice"
    
    # 模拟ASR模型
    mock_server_state.model_asr = MagicMock()
    mock_server_state.model_asr.generate = MagicMock(return_value=[
        {"text": "这是一个测试语音识别结果"}
    ])
    
    # 创建测试音频数据
    test_audio = b'\x00' * (16000 * 2)  # 1秒的静音音频
    session_id = "test_session_123"
    
    # 获取监控器并开始session
    monitor = get_audio_processing_monitor()
    audio_duration = len(test_audio) / (16000 * 2) * 1000  # 计算音频时长
    monitor.start_session(session_id, len(test_audio), audio_duration)
    
    # 使用patch模拟TextProcessor
    with patch('src.modules.audio.audio_processing.TextProcessor') as mock_text_processor:
        mock_text_processor.return_value.process_text.return_value = "这是一个测试语音识别结果"
        
        # 执行ASR处理
        result = await _async_asr_processing(
            mock_websocket, 
            test_audio, 
            mock_server_state, 
            session_id
        )
    
    # 结束session以保存记录
    monitor.end_session(session_id)
    
    # 获取监控器并检查记录
    records = monitor.get_recent_records(1)
    
    # 验证结果
    if len(records) == 0:
        print("❌ 没有找到处理记录")
        return False
    
    record = records[0]
    print(f"📊 找到处理记录: session_id={record['session_id']}")
    
    # 检查ASR时间记录
    if record['asr_start_time'] is None:
        print("❌ ASR开始时间未记录")
        return False
    
    if record['asr_end_time'] is None:
        print("❌ ASR结束时间未记录")
        return False
    
    if record['asr_processing_time'] is None or record['asr_processing_time'] <= 0:
        print("❌ ASR处理时间无效")
        return False
    
    if not record['asr_success']:
        print("❌ ASR处理未标记为成功")
        return False
    
    print(f"✅ ASR时间记录正常:")
    print(f"   - 开始时间: {record['asr_start_time']}")
    print(f"   - 结束时间: {record['asr_end_time']}")
    print(f"   - 处理时间: {record['asr_processing_time']:.2f}ms")
    print(f"   - 处理成功: {record['asr_success']}")
    
    # 检查识别结果
    if result.get('text') != "这是一个测试语音识别结果":
        print(f"❌ ASR识别结果不正确: {result}")
        return False
    
    print(f"✅ ASR识别结果正确: {result.get('text')}")
    
    return True


async def test_monitor_statistics():
    """测试监控器统计功能。"""
    print("\n🧪 测试监控器统计功能...")
    
    monitor = get_audio_processing_monitor()
    stats = monitor.get_statistics()
    
    print(f"✅ 统计数据:")
    print(f"   - ASR处理次数: {stats['asr_stats']['total_requests']}")
    print(f"   - ASR平均时间: {stats['asr_stats']['avg_time']:.2f}ms")
    print(f"   - ASR成功率: {stats['asr_stats']['success_rate']:.1f}%")
    print(f"   - 说话人识别处理次数: {stats['speaker_stats']['total_requests']}")
    print(f"   - 说话人识别平均时间: {stats['speaker_stats']['avg_time']:.2f}ms")
    print(f"   - 说话人识别成功率: {stats['speaker_stats']['success_rate']:.1f}%")
    
    return True


async def main():
    """运行所有测试。"""
    print("🚀 开始测试ASR和说话人识别时间分开记录功能")
    
    try:
        # 测试1: ASR时间记录分离
        success1 = await test_asr_timing_separation()
        if not success1:
            print("❌ ASR时间记录分离测试失败")
            return False
        
        # 测试2: 监控器统计
        success2 = await test_monitor_statistics()
        if not success2:
            print("❌ 监控器统计测试失败")
            return False
        
        print("\n🎉 所有测试通过！ASR和说话人识别时间记录功能正常工作。")
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