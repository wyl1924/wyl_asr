#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块集成测试脚本
测试说话人验证和管理模块是否正确集成到项目中
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    
    try:
        # 测试基础模块导入
        from src.modules.speaker_verification import check_audio_file
        print("✓ speaker_verification 基础函数导入成功")
        
        from src.modules.speaker_manager import SpeakerManager
        print("✓ SpeakerManager 类导入成功")
        
        # 测试核心模块导入
        from src.modules.core import SpeakerManager as CoreSpeakerManager
        from src.modules.core import get_speaker_manager
        print("✓ 核心模块中的说话人管理功能导入成功")
        
        print("所有模块导入测试通过！")
        return True
        
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 其他错误: {e}")
        return False

def test_basic_functionality():
    """测试基础功能"""
    print("\n测试基础功能...")
    
    try:
        from src.modules.speaker_manager import get_speaker_manager
        
        # 创建说话人管理器实例
        manager = get_speaker_manager()
        print("✓ 说话人管理器创建成功")
        
        # 测试统计信息
        stats = manager.get_statistics()
        print(f"✓ 统计信息获取成功: {stats}")
        
        # 测试列表功能
        speakers = manager.list_speakers()
        print(f"✓ 说话人列表获取成功，当前有 {len(speakers)} 个说话人")
        
        print("基础功能测试通过！")
        return True
        
    except Exception as e:
        print(f"✗ 基础功能测试失败: {e}")
        return False

def test_directory_structure():
    """测试目录结构"""
    print("\n测试目录结构...")
    
    try:
        # 检查数据目录
        data_dir = "data/speaker"
        if os.path.exists(data_dir):
            print(f"✓ 数据目录存在: {data_dir}")
        else:
            print(f"! 数据目录不存在，将在首次使用时创建: {data_dir}")
        
        print("目录结构检查完成！")
        return True
        
    except Exception as e:
        print(f"✗ 目录结构检查失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始模块集成测试...\n")
    
    tests = [
        test_imports,
        test_basic_functionality,
        test_directory_structure
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print("-" * 50)
    
    print(f"\n测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！说话人模块集成成功！")
        return 0
    else:
        print("❌ 部分测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    exit(main())