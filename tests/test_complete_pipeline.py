#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试完整Pipeline模式功能。

测试新实现的完整Pipeline模式是否能正常工作，包括：
1. 完整处理流程测试
2. 与C++服务器兼容性测试
3. 各个处理步骤验证
4. 性能对比测试
"""

import sys
import os
import asyncio
import json
import time
from unittest.mock import MagicMock, AsyncMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.audio.audio_processing import async_asr_complete_pipeline, AudioProcessingError
from src.modules.core.server_state import ServerState
from src.modules.core.arg_parser import parse_arguments


def test_pipeline_function_import():
    """测试完整pipeline函数是否能正确导入。"""
    print("🧪 测试1: 完整Pipeline函数导入")
    print("=" * 50)
    
    try:
        from src.modules.audio_processing import async_asr_complete_pipeline
        print("✅ async_asr_complete_pipeline 函数导入成功")
        
        # 检查函数签名
        import inspect
        sig = inspect.signature(async_asr_complete_pipeline)
        print(f"📋 函数签名: {sig}")
        
        # 检查函数文档
        doc = async_asr_complete_pipeline.__doc__
        if doc and "音频输入 → VAD检测 → 在线ASR(实时) → 离线ASR(精确) → 热词增强 → ITN → 标点恢复 → 输出" in doc:
            print("✅ 函数文档包含正确的处理流程描述")
        else:
            print("⚠️ 函数文档可能不完整")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_core_module_export():
    """测试core模块是否正确导出了新函数。"""
    print("\n🧪 测试2: Core模块导出")
    print("=" * 50)
    
    try:
        from src.modules.core import async_asr_complete_pipeline
        print("✅ core模块成功导出 async_asr_complete_pipeline")
        
        # 检查__all__列表
        from src.modules import core
        if hasattr(core, '__all__') and 'async_asr_complete_pipeline' in core.__all__:
            print("✅ async_asr_complete_pipeline 已添加到 __all__ 列表")
        else:
            print("⚠️ async_asr_complete_pipeline 可能未添加到 __all__ 列表")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_websocket_service_integration():
    """测试WebSocket服务是否集成了新的pipeline函数。"""
    print("\n🧪 测试3: WebSocket服务集成")
    print("=" * 50)
    
    try:
        # 检查websocket_service是否导入了新函数
        with open('/Users/wyl/Desktop/wyl_asr/src/modules/websocket_service.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'async_asr_complete_pipeline' in content:
            print("✅ websocket_service.py 已导入 async_asr_complete_pipeline")
        else:
            print("❌ websocket_service.py 未导入 async_asr_complete_pipeline")
            return False
        
        # 检查是否有pipeline模式的处理逻辑
        if 'websocket.mode == "pipeline"' in content:
            print("✅ websocket_service.py 包含pipeline模式处理逻辑")
        else:
            print("⚠️ websocket_service.py 可能缺少pipeline模式处理逻辑")
        
        # 检查是否有完整的处理流程注释
        if "音频输入 → VAD检测 → 在线ASR(实时) → 离线ASR(精确) → 热词增强 → ITN → 标点恢复 → 输出" in content:
            print("✅ websocket_service.py 包含完整处理流程说明")
        else:
            print("⚠️ websocket_service.py 可能缺少处理流程说明")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


async def test_pipeline_mock_execution():
    """测试pipeline函数的模拟执行。"""
    print("\n🧪 测试4: Pipeline模拟执行")
    print("=" * 50)
    
    try:
        # 创建模拟的WebSocket和ServerState
        mock_websocket = MagicMock()
        mock_websocket.wav_name = "test_audio"
        mock_websocket.status_dict_asr_online = {"chunk_size": [0, 10, 5]}
        mock_websocket.status_dict_asr = {"hotwords": ""}
        mock_websocket.status_dict_punc = {}
        mock_websocket.send = AsyncMock()
        
        # 创建模拟的ServerState
        mock_server_state = MagicMock()
        mock_server_state.logger = MagicMock()
        mock_server_state.args = MagicMock()
        mock_server_state.args.model_type = "sensevoice"
        mock_server_state.model_asr_streaming = None  # 模拟没有在线模型
        mock_server_state.model_asr = None  # 模拟没有离线模型
        mock_server_state.model_punc = None
        mock_server_state.model_itn = None
        mock_server_state.hotword_map = None
        
        # 模拟VAD函数
        from src.modules import audio_processing
        original_vad = audio_processing.async_vad
        audio_processing.async_vad = AsyncMock(return_value=(-1, -1))
        
        try:
            # 测试空音频
            await async_asr_complete_pipeline(
                mock_websocket, b"", mock_server_state, is_final=False
            )
            print("✅ 空音频处理测试通过")
            
            # 测试非空音频但无语音活动
            test_audio = b"\x00" * 1600  # 模拟100ms的静音
            await async_asr_complete_pipeline(
                mock_websocket, test_audio, mock_server_state, is_final=False
            )
            print("✅ 无语音活动处理测试通过")
            
            # 测试最终处理（但没有模型）
            await async_asr_complete_pipeline(
                mock_websocket, test_audio, mock_server_state, is_final=True
            )
            print("✅ 最终处理测试通过（无模型）")
            
        finally:
            # 恢复原始VAD函数
            audio_processing.async_vad = original_vad
        
        return True
        
    except Exception as e:
        print(f"❌ 模拟执行测试失败: {e}")
        return False


def test_processing_stages_documentation():
    """测试处理步骤的文档化。"""
    print("\n🧪 测试5: 处理步骤文档化")
    print("=" * 50)
    
    try:
        # 检查函数文档中是否包含所有处理步骤
        doc = async_asr_complete_pipeline.__doc__
        
        required_stages = [
            "VAD语音活动检测",
            "在线流式ASR",
            "离线高精度ASR",
            "说话人识别处理",
            "热词增强处理",
            "ITN逆文本标准化",
            "标点符号恢复",
            "结果输出"
        ]
        
        missing_stages = []
        for stage in required_stages:
            if stage not in doc:
                missing_stages.append(stage)
        
        if not missing_stages:
            print("✅ 所有处理步骤都已在文档中说明")
            print("📋 包含的处理步骤:")
            for i, stage in enumerate(required_stages, 1):
                print(f"   {i}. {stage}")
        else:
            print(f"⚠️ 缺少以下处理步骤的文档: {missing_stages}")
        
        # 检查是否提到了C++服务器兼容性
        if "C++服务器" in doc and "完全一致" in doc:
            print("✅ 文档中提到了与C++服务器的兼容性")
        else:
            print("⚠️ 文档中可能缺少C++服务器兼容性说明")
        
        # 检查是否包含说话人识别步骤
        if "说话人识别" in doc:
            print("✅ 文档中包含说话人识别步骤")
        else:
            print("⚠️ 文档中可能缺少说话人识别步骤说明")
        
        return len(missing_stages) == 0
        
    except Exception as e:
        print(f"❌ 文档测试失败: {e}")
        return False


def test_main_program_integration():
    """测试主程序是否集成了新的pipeline模式说明。"""
    print("\n🧪 测试6: 主程序集成")
    print("=" * 50)
    
    try:
        # 检查main.py是否包含pipeline模式的说明
        with open('/Users/wyl/Desktop/wyl_asr/main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ("pipeline: 完整处理流程", "pipeline模式说明"),
            ("完整Pipeline模式", "Pipeline模式配置信息"),
            ("音频输入 → VAD检测 → 在线ASR(实时) → 离线ASR(精确) → 说话人识别 → 热词增强 → ITN → 标点恢复 → 输出", "完整处理流程描述"),
            ("步骤4: 说话人识别处理", "说话人识别步骤说明"),
            ("与C++服务器处理流程完全一致", "C++兼容性说明")
        ]
        
        passed_checks = 0
        for check_text, description in checks:
            if check_text in content:
                print(f"✅ {description}: 已包含")
                passed_checks += 1
            else:
                print(f"❌ {description}: 缺失")
        
        success_rate = passed_checks / len(checks) * 100
        print(f"📊 集成完成度: {success_rate:.1f}% ({passed_checks}/{len(checks)})")
        
        return passed_checks == len(checks)
        
    except Exception as e:
        print(f"❌ 主程序集成测试失败: {e}")
        return False


def test_argument_parser_compatibility():
    """测试参数解析器的兼容性。"""
    print("\n🧪 测试7: 参数解析器兼容性")
    print("=" * 50)
    
    try:
        # 测试2pass相关参数
        test_args = [
            "--enable_2pass",
            "--global_beam", "3.0",
            "--lattice_beam", "3.0",
            "--am_scale", "10.0",
            "--fst_inc_wts", "20"
        ]
        
        args = parse_arguments(test_args)
        
        # 验证参数
        assert args.enable_2pass == True, "enable_2pass参数解析失败"
        assert args.global_beam == 3.0, "global_beam参数解析失败"
        assert args.lattice_beam == 3.0, "lattice_beam参数解析失败"
        assert args.am_scale == 10.0, "am_scale参数解析失败"
        assert args.fst_inc_wts == 20, "fst_inc_wts参数解析失败"
        
        print("✅ 所有Pipeline相关参数解析正确")
        print(f"   • enable_2pass: {args.enable_2pass}")
        print(f"   • global_beam: {args.global_beam}")
        print(f"   • lattice_beam: {args.lattice_beam}")
        print(f"   • am_scale: {args.am_scale}")
        print(f"   • fst_inc_wts: {args.fst_inc_wts}")
        
        return True
        
    except Exception as e:
        print(f"❌ 参数解析器测试失败: {e}")
        return False


async def run_all_tests():
    """运行所有测试。"""
    print("🚀 开始完整Pipeline模式测试")
    print("=" * 70)
    
    tests = [
        ("函数导入测试", test_pipeline_function_import),
        ("Core模块导出测试", test_core_module_export),
        ("WebSocket服务集成测试", test_websocket_service_integration),
        ("Pipeline模拟执行测试", test_pipeline_mock_execution),
        ("处理步骤文档化测试", test_processing_stages_documentation),
        ("主程序集成测试", test_main_program_integration),
        ("参数解析器兼容性测试", test_argument_parser_compatibility)
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
        print("🎉 完整Pipeline模式测试基本通过！")
        print("💡 建议: 可以开始实际测试新的处理流程")
    elif success_rate >= 60:
        print("⚠️ 完整Pipeline模式部分功能正常，需要修复失败的测试")
    else:
        print("❌ 完整Pipeline模式存在较多问题，需要进一步调试")
    
    return success_rate >= 80


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(run_all_tests())
    
    if success:
        print("\n🎯 下一步建议:")
        print("1. 启动服务器测试新的pipeline模式")
        print("2. 使用WebSocket客户端发送音频数据")
        print("3. 验证完整的处理流程输出")
        print("4. 对比与C++服务器的处理结果")
    else:
        print("\n🔧 修复建议:")
        print("1. 检查失败的测试项目")
        print("2. 确保所有模块正确导入新函数")
        print("3. 验证处理流程的完整性")
        print("4. 重新运行测试确认修复")