#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试说话人验证模块与统一模型管理的集成
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_speaker_verifier_model_loading():
    """测试说话人验证器的模型加载逻辑"""
    print("🧪 测试说话人验证器模型加载...")
    
    try:
        from src.modules.speaker_verification import SpeakerVerifier, get_speaker_verifier
        from src.modules.server_state import get_local_model_path
        
        print("✅ 模块导入成功")
        
        # 测试 get_local_model_path 函数
        root_dir = os.path.dirname(os.path.abspath(__file__))
        test_model = "iic/speech_campplus_sv_zh-cn_16k-common"
        local_path = get_local_model_path(test_model, root_dir)
        
        if local_path:
            print(f"🎯 找到本地模型: {local_path}")
        else:
            print(f"🌊 本地模型不存在，将使用远程模型: {test_model}")
        
        # 测试说话人验证器初始化（不实际加载模型）
        print("📝 测试说话人验证器配置...")
        
        # 创建验证器实例（这会触发模型加载）
        print("⚠️  注意：以下将尝试加载实际模型，可能需要一些时间...")
        verifier = SpeakerVerifier(
            device="cpu",
            threshold=0.5
        )
        
        # 获取模型信息
        model_info = verifier.get_model_info()
        print(f"✅ 说话人验证器创建成功")
        print(f"📊 模型信息: {model_info}")
        
        # 测试全局实例
        global_verifier = get_speaker_verifier()
        print(f"✅ 全局说话人验证器获取成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return False

def test_model_path_logic():
    """测试模型路径逻辑"""
    print("\n🧪 测试模型路径逻辑...")
    
    try:
        from src.modules.server_state import get_local_model_path
        
        root_dir = os.path.dirname(os.path.abspath(__file__))
        test_models = [
            "iic/speech_campplus_sv_zh-cn_16k-common",
            "damo/speech_campplus_sv_zh_en_16k-common_advanced",
            "nonexistent/model"
        ]
        
        for model in test_models:
            local_path = get_local_model_path(model, root_dir)
            if local_path:
                print(f"✅ {model} -> 本地路径: {local_path}")
            else:
                print(f"🌊 {model} -> 将使用远程下载")
        
        return True
        
    except Exception as e:
        print(f"❌ 模型路径测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 开始测试说话人验证模块与统一模型管理的集成")
    print("=" * 60)
    
    # 测试模型路径逻辑
    path_test_result = test_model_path_logic()
    
    # 测试说话人验证器（可能会下载模型）
    model_test_result = test_speaker_verifier_model_loading()
    
    print("\n" + "=" * 60)
    print("📋 测试结果汇总:")
    print(f"  模型路径逻辑: {'✅ 通过' if path_test_result else '❌ 失败'}")
    print(f"  说话人验证器: {'✅ 通过' if model_test_result else '❌ 失败'}")
    
    if path_test_result and model_test_result:
        print("\n🎉 所有测试通过！说话人验证模块已成功集成统一模型管理。")
    else:
        print("\n⚠️  部分测试失败，请检查错误信息。")