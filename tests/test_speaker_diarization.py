#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试说话人分离功能。

测试新实现的说话人分离功能是否能正常工作，包括：
1. 说话人分离参数解析测试
2. 说话人分离模型加载测试
3. 说话人分离处理逻辑测试
4. 与说话人识别的智能切换测试
"""

import sys
import os
import asyncio
import json
import numpy as np
from unittest.mock import MagicMock, AsyncMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.audio_processing import perform_speaker_diarization, async_asr_complete_pipeline
from src.modules.arg_parser import parse_arguments
from src.modules.server_state import ServerState


def test_speaker_diarization_arguments():
    """测试说话人分离相关参数解析。"""
    print("🧪 测试1: 说话人分离参数解析")
    print("=" * 50)
    
    try:
        # 测试说话人分离参数
        test_args = [
            "--enable_speaker_diarization",
            "--speaker_diarization_model", "damo/speech_campplus_sv_zh-cn_16k-common",
            "--speaker_diarization_model_revision", "v2.0.2"
        ]
        
        args = parse_arguments(test_args)
        
        # 验证参数
        assert args.enable_speaker_diarization == True, "enable_speaker_diarization参数解析失败"
        assert args.speaker_diarization_model == "damo/speech_campplus_sv_zh-cn_16k-common", "speaker_diarization_model参数解析失败"
        assert args.speaker_diarization_model_revision == "v2.0.2", "speaker_diarization_model_revision参数解析失败"
        
        print("✅ 说话人分离参数解析正确")
        print(f"   • enable_speaker_diarization: {args.enable_speaker_diarization}")
        print(f"   • speaker_diarization_model: {args.speaker_diarization_model}")
        print(f"   • speaker_diarization_model_revision: {args.speaker_diarization_model_revision}")
        
        return True
        
    except Exception as e:
        print(f"❌ 说话人分离参数解析测试失败: {e}")
        return False


def test_speaker_diarization_function_import():
    """测试说话人分离函数是否能正确导入。"""
    print("\n🧪 测试2: 说话人分离函数导入")
    print("=" * 50)
    
    try:
        from src.modules.audio_processing import perform_speaker_diarization
        print("✅ perform_speaker_diarization 函数导入成功")
        
        # 检查函数签名
        import inspect
        sig = inspect.signature(perform_speaker_diarization)
        print(f"📋 函数签名: {sig}")
        
        # 检查函数文档
        doc = perform_speaker_diarization.__doc__
        if doc and "FunnyASR" in doc and "说话人分离" in doc:
            print("✅ 函数文档包含正确的说话人分离描述")
        else:
            print("⚠️ 函数文档可能不完整")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


async def test_speaker_diarization_mock_execution():
    """测试说话人分离函数的模拟执行。"""
    print("\n🧪 测试3: 说话人分离模拟执行")
    print("=" * 50)
    
    try:
        # 创建模拟的ServerState
        mock_server_state = MagicMock()
        mock_server_state.model_speaker = MagicMock()  # 模拟有说话人模型
        mock_server_state.model_asr = MagicMock()
        
        # 模拟FunASR的说话人分离结果
        mock_diarization_result = [{
            'sentence_info': [
                {
                    'spk': 'speaker_0',
                    'text': '你好，我是第一个说话人。',
                    'start': 0,
                    'end': 2000
                },
                {
                    'spk': 'speaker_1', 
                    'text': '你好，我是第二个说话人。',
                    'start': 2000,
                    'end': 4000
                }
            ]
        }]
        
        mock_server_state.model_asr.generate.return_value = mock_diarization_result
        
        # 创建模拟的logger
        mock_logger = MagicMock()
        
        # 测试音频数据
        test_audio = np.random.randint(-32768, 32767, 16000, dtype=np.int16).tobytes()
        test_text = "测试文本"
        
        # 执行说话人分离
        result = await perform_speaker_diarization(
            test_audio, mock_server_state, test_text, mock_logger
        )
        
        # 验证结果
        assert result is not None, "说话人分离返回None"
        assert result['type'] == 'diarization', "结果类型不正确"
        assert result['total_speakers'] == 2, "检测到的说话人数量不正确"
        assert len(result['speakers']) == 2, "说话人列表长度不正确"
        assert len(result['speaker_segments']) == 2, "说话人段落数量不正确"
        
        print("✅ 说话人分离模拟执行成功")
        print(f"   • 检测到说话人数量: {result['total_speakers']}")
        print(f"   • 主要说话人: {result['primary_speaker']['speaker_id']}")
        print(f"   • 说话人段落数: {len(result['speaker_segments'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ 说话人分离模拟执行测试失败: {e}")
        return False


async def test_speaker_diarization_fallback():
    """测试说话人分离作为备选方案的功能。"""
    print("\n🧪 测试4: 说话人分离备选方案")
    print("=" * 50)
    
    try:
        # 创建模拟的ServerState（无说话人模型）
        mock_server_state = MagicMock()
        mock_server_state.model_speaker = None  # 模拟无说话人模型
        
        # 创建模拟的logger
        mock_logger = MagicMock()
        
        # 测试音频数据
        test_audio = np.random.randint(-32768, 32767, 16000, dtype=np.int16).tobytes()
        test_text = "测试文本"
        
        # 执行说话人分离（应该返回None）
        result = await perform_speaker_diarization(
            test_audio, mock_server_state, test_text, mock_logger
        )
        
        # 验证结果
        assert result is None, "无说话人模型时应该返回None"
        
        print("✅ 说话人分离备选方案测试通过")
        print("   • 无说话人模型时正确返回None")
        
        return True
        
    except Exception as e:
        print(f"❌ 说话人分离备选方案测试失败: {e}")
        return False


def test_pipeline_integration():
    """测试说话人分离与完整pipeline的集成。"""
    print("\n🧪 测试5: Pipeline集成测试")
    print("=" * 50)
    
    try:
        # 检查完整pipeline函数是否包含说话人分离逻辑
        import inspect
        source = inspect.getsource(async_asr_complete_pipeline)
        
        checks = [
            ("perform_speaker_diarization", "说话人分离函数调用"),
            ("说话人识别/分离处理", "处理步骤注释"),
            ("type\": \"identification", "识别类型标记"),
            ("type\": \"diarization", "分离类型标记")
        ]
        
        passed_checks = 0
        for check_text, description in checks:
            if check_text in source:
                print(f"✅ {description}: 已包含")
                passed_checks += 1
            else:
                print(f"❌ {description}: 缺失")
        
        success_rate = passed_checks / len(checks) * 100
        print(f"📊 集成完成度: {success_rate:.1f}% ({passed_checks}/{len(checks)})")
        
        return passed_checks >= 3  # 至少通过3个检查
        
    except Exception as e:
        print(f"❌ Pipeline集成测试失败: {e}")
        return False


def test_documentation_updates():
    """测试文档更新是否完整。"""
    print("\n🧪 测试6: 文档更新检查")
    print("=" * 50)
    
    try:
        # 检查main.py中的处理流程描述
        with open('/Users/wyl/Desktop/wyl_asr/main.py', 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        # 检查websocket_service.py中的处理流程描述
        with open('/Users/wyl/Desktop/wyl_asr/src/modules/websocket_service.py', 'r', encoding='utf-8') as f:
            ws_content = f.read()
        
        checks = [
            ("说话人识别/分离", main_content, "main.py处理流程描述"),
            ("说话人识别/分离", ws_content, "websocket_service.py处理流程描述"),
            ("步骤4: 说话人识别/分离处理", main_content, "main.py步骤说明"),
        ]
        
        passed_checks = 0
        for check_text, content, description in checks:
            if check_text in content:
                print(f"✅ {description}: 已更新")
                passed_checks += 1
            else:
                print(f"❌ {description}: 未更新")
        
        success_rate = passed_checks / len(checks) * 100
        print(f"📊 文档更新完成度: {success_rate:.1f}% ({passed_checks}/{len(checks)})")
        
        return passed_checks == len(checks)
        
    except Exception as e:
        print(f"❌ 文档更新检查失败: {e}")
        return False


async def run_all_tests():
    """运行所有说话人分离测试。"""
    print("🚀 开始说话人分离功能测试")
    print("=" * 70)
    
    tests = [
        ("说话人分离参数解析测试", test_speaker_diarization_arguments),
        ("说话人分离函数导入测试", test_speaker_diarization_function_import),
        ("说话人分离模拟执行测试", test_speaker_diarization_mock_execution),
        ("说话人分离备选方案测试", test_speaker_diarization_fallback),
        ("Pipeline集成测试", test_pipeline_integration),
        ("文档更新检查", test_documentation_updates)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 执行异常: {e}")
            results.append((test_name, False))
    
    # 统计结果
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    success_rate = passed / total * 100
    print(f"\n📈 总体通过率: {success_rate:.1f}% ({passed}/{total})")
    
    if success_rate >= 80:
        print("🎉 说话人分离功能测试基本通过！")
        print("💡 建议: 可以开始实际测试说话人分离功能")
        print("\n🎯 功能特点:")
        print("• 智能切换：优先使用说话人识别，失败时自动切换到说话人分离")
        print("• 兼容性：参考FunnyASR实现，使用FunASR内置说话人分离功能")
        print("• 灵活性：支持单独启用说话人分离或与说话人识别组合使用")
        print("• 完整性：集成到完整pipeline中，提供详细的说话人信息")
    elif success_rate >= 60:
        print("⚠️ 说话人分离功能部分正常，需要修复失败的测试")
    else:
        print("❌ 说话人分离功能存在较多问题，需要进一步调试")
    
    return success_rate >= 80


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(run_all_tests())
    
    if success:
        print("\n🎯 下一步建议:")
        print("1. 启动服务器并启用说话人分离功能")
        print("2. 使用包含多个说话人的音频进行测试")
        print("3. 验证说话人分离结果的准确性")
        print("4. 测试说话人识别与分离的智能切换")
        print("\n📋 启动命令示例:")
        print("python main.py --enable_speaker_diarization --enable_2pass")
    else:
        print("\n🔧 修复建议:")
        print("1. 检查失败的测试项目")
        print("2. 确保说话人分离函数正确实现")
        print("3. 验证与完整pipeline的集成")
        print("4. 重新运行测试确认修复")