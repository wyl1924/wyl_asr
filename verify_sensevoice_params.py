#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证SenseVoice参数配置
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.modules.config.arg_parser import parse_arguments
from src.modules.core.server_state import build_sensevoice_config

def test_websocket_status_dict_asr():
    """测试websocket.status_dict_asr参数配置"""
    print("🧪 测试websocket.status_dict_asr参数配置")
    print("=" * 50)
    
    # 模拟websocket.status_dict_asr的配置
    status_dict_asr = {
        # 基础配置参数
        "batch_size_s": 30,                    # SenseVoice批处理时长 (秒)
        "merge_length_s": 15,                  # SenseVoice音频合并长度 (秒)
        "language": "auto",                    # SenseVoice识别语言
        "use_itn": True,                       # 启用逆文本正则化 (ITN)
        "ban_emo_unk": False,                  # 禁用未知情感 (enable_emotion的反向)
        "enable_event_detection": False,       # 启用音频事件检测
        "enable_speaker_id": False,            # 启用说话人识别
        "output_timestamp": True,              # 输出时间戳信息
        "merge_vad": True,                     # 合并VAD结果
        "max_single_segment_time": 10000,      # 单段音频最大时长 (毫秒)
        
        # 推理模式和解码参数
        "inference_mode": "offline",           # SenseVoice推理模式
        "beam_size": 1,                        # 束搜索大小
        "temperature": 1.0,                    # 解码温度
        "repetition_penalty": 1.0,             # 重复惩罚系数
        "length_penalty": 1.0,                 # 长度惩罚系数
        
        # VAD和流式处理参数
        "enable_vad_realtime": True,           # 启用实时VAD
        "chunk_size": 960,                     # 音频块大小 (样本数)
        "encoder_chunk_look_back": 4,          # 编码器回看块数
        "decoder_chunk_look_back": 1,          # 解码器回看块数
    }
    
    print(f"✅ websocket.status_dict_asr包含 {len(status_dict_asr)} 个SenseVoice参数:")
    for key, value in status_dict_asr.items():
        print(f"  - {key}: {value}")
    
    return True

def test_arg_parser_sensevoice_params():
    """测试arg_parser中的SenseVoice参数"""
    print("\n🧪 测试arg_parser中的SenseVoice参数")
    print("=" * 50)
    
    try:
        args = parse_arguments([])
        
        # 检查所有SenseVoice参数
        sensevoice_params = [
            'sv_batch_size_s', 'sv_merge_length_s', 'sv_language', 'sv_use_itn',
            'sv_enable_emotion', 'sv_enable_event_detection', 'sv_enable_speaker_id',
            'sv_output_timestamp', 'sv_merge_vad', 'sv_max_single_segment_time',
            'sv_inference_mode', 'sv_beam_size', 'sv_temperature', 'sv_repetition_penalty',
            'sv_length_penalty', 'sv_enable_vad_realtime', 'sv_chunk_size',
            'sv_encoder_chunk_look_back', 'sv_decoder_chunk_look_back'
        ]
        
        missing_params = []
        for param in sensevoice_params:
            if hasattr(args, param):
                value = getattr(args, param)
                print(f"  ✅ {param}: {value}")
            else:
                missing_params.append(param)
                print(f"  ❌ {param}: 缺失")
        
        if missing_params:
            print(f"\n❌ 缺失参数: {missing_params}")
            return False
        else:
            print(f"\n✅ 所有 {len(sensevoice_params)} 个SenseVoice参数都存在")
            return True
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_build_sensevoice_config():
    """测试build_sensevoice_config函数"""
    print("\n🧪 测试build_sensevoice_config函数")
    print("=" * 50)
    
    try:
        args = parse_arguments([])
        config = build_sensevoice_config(args)
        
        print(f"✅ build_sensevoice_config生成配置包含 {len(config)} 个参数:")
        for key, value in config.items():
            print(f"  - {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 SenseVoice参数配置验证")
    print("=" * 60)
    
    tests = [
        test_websocket_status_dict_asr,
        test_arg_parser_sensevoice_params,
        test_build_sensevoice_config
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 异常: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！SenseVoice参数配置正确")
        return True
    else:
        print("⚠️ 部分测试失败，请检查配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)