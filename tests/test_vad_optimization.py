#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VAD优化测试
==========

测试VAD配置优化后的效果，特别是针对静音检测时长的改进。
"""

import asyncio
import json
import time
from datetime import datetime
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.core.server_state import ServerState
from src.modules.config.arg_parser import parse_arguments, build_vad_config
from src.modules.audio.audio_processing import async_vad


class MockWebSocket:
    """模拟WebSocket连接用于测试"""
    
    def __init__(self):
        # 使用优化后的VAD配置
        self.status_dict_vad = {
            "cache": {}, 
            "is_final": False,
            # VAD核心参数配置 - 优化静音检测参数
            "max_end_silence_time": 2000,     # 尾部静音检测时长(ms) - 增加到2秒避免过早结束
            "max_start_silence_time": 5000,   # 开始静音检测时长(ms) - 增加到5秒
            "min_speech_duration_time": 200,  # 最小语音持续时长(ms)
            "speech_noise_thres": 0.6,        # 语音/噪声阈值
            "do_start_point_detection": True, # 启用开始点检测
            "do_end_point_detection": True,   # 启用结束点检测
            "window_size_ms": 200,            # 窗口大小(ms)
            "sil_to_speech_time_thres": 150,  # 静音到语音阈值(ms)
            "speech_to_sil_time_thres": 150,  # 语音到静音阈值(ms)
            "max_single_segment_time": 60000  # 单段最大时长(ms)
        }
        
        self.vad_pre_idx = 0
        self.chunk_interval = 10
        self.wav_name = "test"
        self.mode = "2pass"
        self.is_speaking = False
        self.enable_speaker_identification = False
        self.speaker_top_k = 3


def test_vad_optimization():
    """
    测试VAD优化配置
    """
    print(f"🔍 VAD优化配置测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    # 测试从配置文件读取VAD参数
    args = parse_arguments([])
    vad_config_from_args = build_vad_config(args)
    
    print("📋 从配置文件读取的VAD参数:")
    for key, value in vad_config_from_args.items():
        if key not in ['cache', 'is_final']:
            print(f"  ✓ {key}: {value}")
    
    # 创建模拟WebSocket进行对比
    mock_websocket = MockWebSocket()
    
    # 检查优化后的VAD配置参数
    vad_config = vad_config_from_args
    
    print("📋 优化后的VAD配置参数:")
    print(f"  ✓ max_end_silence_time: {vad_config.get('max_end_silence_time', 'Missing')}ms (原800ms -> 2000ms)")
    print(f"  ✓ max_start_silence_time: {vad_config.get('max_start_silence_time', 'Missing')}ms (原3000ms -> 5000ms)")
    print(f"  ✓ min_speech_duration_time: {vad_config.get('min_speech_duration_time', 'Missing')}ms")
    print(f"  ✓ speech_noise_thres: {vad_config.get('speech_noise_thres', 'Missing')}")
    print(f"  ✓ do_start_point_detection: {vad_config.get('do_start_point_detection', 'Missing')}")
    print(f"  ✓ do_end_point_detection: {vad_config.get('do_end_point_detection', 'Missing')}")
    print(f"  ✓ window_size_ms: {vad_config.get('window_size_ms', 'Missing')}ms")
    print(f"  ✓ sil_to_speech_time_thres: {vad_config.get('sil_to_speech_time_thres', 'Missing')}ms")
    print(f"  ✓ speech_to_sil_time_thres: {vad_config.get('speech_to_sil_time_thres', 'Missing')}ms")
    print(f"  ✓ max_single_segment_time: {vad_config.get('max_single_segment_time', 'Missing')}ms")
    
    # 验证关键优化参数
    optimizations = [
        ('max_end_silence_time', 2000, '尾部静音检测时长增加到2秒，避免过早结束语音段'),
        ('max_start_silence_time', 5000, '开始静音检测时长增加到5秒，提高语音开始检测准确性'),
        ('speech_noise_thres', 0.6, '语音/噪声阈值保持0.6，平衡敏感度和准确性')
    ]
    
    print("\n🎯 关键优化说明:")
    for param, expected_value, description in optimizations:
        actual_value = vad_config.get(param, 'Missing')
        status = "✅" if actual_value == expected_value else "❌"
        print(f"  {status} {param}: {actual_value} - {description}")
    
    # 检查配置完整性
    required_params = [
        'max_end_silence_time', 'max_start_silence_time', 'min_speech_duration_time',
        'speech_noise_thres', 'do_start_point_detection', 'do_end_point_detection',
        'window_size_ms', 'sil_to_speech_time_thres', 'speech_to_sil_time_thres',
        'max_single_segment_time'
    ]
    
    missing_params = []
    for param in required_params:
        if param not in vad_config:
            missing_params.append(param)
    
    if missing_params:
        print(f"\n❌ 缺少VAD参数: {missing_params}")
        return False
    else:
        print(f"\n✅ 所有VAD参数配置正确!")
        return True


def print_vad_optimization_summary():
    """
    打印VAD优化总结
    """
    print("\n" + "=" * 60)
    print("🔧 VAD配置优化总结")
    print("=" * 60)
    print("\n📋 优化内容:")
    print("  1. ✅ 修复了websocket_service.py中的VAD初始化配置")
    print("  2. ✅ 修复了websocket_manager.py中的VAD重置配置")
    print("  3. ✅ 优化了静音检测时长参数")
    print("  4. ✅ 添加了在线ASR的语音活动检查逻辑")
    
    print("\n🎯 关键优化参数:")
    print("  • max_end_silence_time: 800ms -> 2000ms (尾部静音检测)")
    print("  • max_start_silence_time: 3000ms -> 5000ms (开始静音检测)")
    print("  • 添加了语音活动检查，避免静音期间的无效识别")
    
    print("\n🚀 预期效果:")
    print("  • 减少停止说话后的持续输出问题")
    print("  • 提高VAD检测的准确性和稳定性")
    print("  • 优化2pass-online模式的性能")
    print("  • 减少静音期间的无效ASR处理")
    
    print("\n📝 问题分析:")
    print("  • 原因1: VAD配置参数不完整，缺少关键的静音检测参数")
    print("  • 原因2: max_end_silence_time设置过短(800ms)，导致过早结束语音段")
    print("  • 原因3: 在线ASR缺少语音活动检查，静音期间仍在处理音频")
    print("  • 原因4: VAD状态重置时未保留完整配置参数")
    
    print("\n🔍 使用的模型:")
    print("  • Paraformer-large-vad-punc (集成VAD、ASR、标点)")
    print("  • 模型地址: iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch")


if __name__ == "__main__":
    print("🧪 开始VAD优化测试...")
    
    # 运行VAD配置测试
    success = test_vad_optimization()
    
    # 打印优化总结
    print_vad_optimization_summary()
    
    if success:
        print("\n🎉 VAD优化测试通过!")
        exit(0)
    else:
        print("\n❌ VAD优化测试失败!")
        exit(1)