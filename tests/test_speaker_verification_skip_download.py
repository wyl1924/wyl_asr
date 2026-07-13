#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试说话人验证模块的跳过下载功能

测试内容：
1. 当模型不存在时，是否正确跳过下载
2. 模型加载失败时的错误处理
3. 模型为 None 时各方法的行为
"""

import sys
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.speaker_verification import SpeakerVerifier

def test_model_not_exists_skip_download():
    """测试模型不存在时跳过下载"""
    print("\n=== 测试模型不存在时跳过下载 ===")
    
    # 创建临时缓存目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 使用不存在的模型名称
        non_existent_model = "non-existent/model"
        
        try:
            verifier = SpeakerVerifier(
                model_name=non_existent_model,
                cache_dir=temp_dir
            )
            
            # 检查模型是否为 None
            if verifier.model is None:
                print("✅ 模型正确设置为 None，跳过了下载")
            else:
                print("❌ 模型不应该被加载")
                
            # 检查模型信息
            model_info = verifier.get_model_info()
            print(f"模型信息: {model_info}")
            
            if not model_info['model_loaded']:
                print("✅ model_loaded 正确显示为 False")
            else:
                print("❌ model_loaded 应该为 False")
                
        except Exception as e:
            print(f"❌ 初始化过程中出现异常: {e}")

def test_extract_embedding_with_no_model():
    """测试模型为 None 时提取特征的行为"""
    print("\n=== 测试模型为 None 时提取特征 ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        verifier = SpeakerVerifier(
            model_name="non-existent/model",
            cache_dir=temp_dir
        )
        
        # 确保模型为 None
        if verifier.model is None:
            print("✅ 模型正确设置为 None")
            
            # 尝试提取特征，应该抛出异常
            try:
                verifier.extract_embedding("dummy_audio.wav")
                print("❌ 应该抛出异常")
            except RuntimeError as e:
                if "说话人验证模型未加载" in str(e):
                    print("✅ 正确抛出了友好的错误信息")
                    print(f"错误信息: {e}")
                else:
                    print(f"❌ 错误信息不够友好: {e}")
            except Exception as e:
                print(f"❌ 抛出了意外的异常类型: {type(e).__name__}: {e}")
        else:
            print("❌ 模型不应该被加载")

def test_check_model_exists_method():
    """测试 _check_model_exists 方法"""
    print("\n=== 测试 _check_model_exists 方法 ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        verifier = SpeakerVerifier(
            model_name="test/model",
            cache_dir=temp_dir
        )
        
        # 测试不存在的模型
        exists = verifier._check_model_exists("non-existent/model")
        if not exists:
            print("✅ 正确识别不存在的模型")
        else:
            print("❌ 不应该认为模型存在")
        
        # 创建一个假的模型目录
        fake_model_dir = os.path.join(temp_dir, "test--model")
        os.makedirs(fake_model_dir, exist_ok=True)
        
        # 测试存在的模型
        exists = verifier._check_model_exists("test/model")
        if exists:
            print("✅ 正确识别存在的模型")
        else:
            print("❌ 应该认为模型存在")

def test_backup_models_behavior():
    """测试备用模型的行为"""
    print("\n=== 测试备用模型行为 ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 使用多个不存在的模型
        verifier = SpeakerVerifier(
            model_name="non-existent-1/model",
            cache_dir=temp_dir
        )
        
        # 检查是否所有模型都被跳过
        if verifier.model is None:
            print("✅ 所有不存在的模型都被正确跳过")
        else:
            print("❌ 不应该有模型被加载")
        
        # 检查模型信息
        model_info = verifier.get_model_info()
        print(f"最终模型信息: {model_info}")

def main():
    """运行所有测试"""
    print("开始测试说话人验证模块的跳过下载功能...")
    
    try:
        test_model_not_exists_skip_download()
        test_extract_embedding_with_no_model()
        test_check_model_exists_method()
        test_backup_models_behavior()
        
        print("\n=== 测试总结 ===")
        print("✅ 所有测试完成")
        print("💡 说话人验证模块现在会在模型不存在时跳过下载")
        print("💡 用户可以通过错误信息了解需要先下载模型")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()