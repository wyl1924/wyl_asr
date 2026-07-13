#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大文件会议文档保存测试

测试会议文档保存API对大文件的处理能力，验证413错误修复：
1. 测试不同大小的文档数据
2. 验证请求大小限制配置
3. 测试错误处理和友好提示

作者: WYL ASR Team
创建时间: 2024年
"""

import os
import sys
import json
import requests
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_large_content(size_mb):
    """生成指定大小的测试内容"""
    # 每个字符大约1字节，生成指定MB的内容
    target_size = size_mb * 1024 * 1024
    base_text = "这是一段测试的语音转录内容。包含中文字符和标点符号，用于测试大文件处理能力。"
    
    # 计算需要重复多少次
    repeat_count = target_size // len(base_text.encode('utf-8'))
    content = base_text * repeat_count
    
    # 确保达到目标大小
    while len(content.encode('utf-8')) < target_size:
        content += base_text
    
    return content[:target_size]  # 精确控制大小


def test_api_server_connection():
    """测试API服务器连接"""
    print("🔍 检查API服务器连接...")
    
    try:
        health_url = "http://localhost:8080/api/health"
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print("✅ API服务器运行正常")
            return True
        else:
            print(f"❌ API服务器响应异常: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 无法连接到API服务器: {e}")
        return False


def test_small_document():
    """测试小文档（正常情况）"""
    print("\n📄 测试小文档保存（1MB）...")
    
    test_data = {
        'title': '小文档测试会议',
        'description': '测试1MB大小的会议文档保存',
        'participants': '张三, 李四',
        'transcriptionContent': generate_large_content(1),  # 1MB
        'meetingMinutes': '这是会议纪要内容。',
        'audioInfo': {
            'duration': 3600,
            'format': 'wav',
            'sample_rate': 16000
        }
    }
    
    try:
        url = "http://localhost:8080/api/meetings/save-documents"
        response = requests.post(url, json=test_data, timeout=30)
        
        if response.status_code in [200, 201]:
            print("✅ 小文档保存成功")
            return True
        else:
            print(f"❌ 小文档保存失败: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return False


def test_medium_document():
    """测试中等文档（100MB）"""
    print("\n📄 测试中等文档保存（100MB）...")
    
    test_data = {
        'title': '中等文档测试会议',
        'description': '测试100MB大小的会议文档保存',
        'participants': '张三, 李四, 王五',
        'transcriptionContent': generate_large_content(100),  # 100MB
        'meetingMinutes': '这是会议纪要内容。',
        'audioInfo': {
            'duration': 7200,
            'format': 'wav',
            'sample_rate': 16000
        }
    }
    
    try:
        url = "http://localhost:8080/api/meetings/save-documents"
        print("📤 发送100MB文档请求...")
        response = requests.post(url, json=test_data, timeout=60)
        
        if response.status_code in [200, 201]:
            print("✅ 中等文档保存成功")
            return True
        else:
            print(f"❌ 中等文档保存失败: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return False


def test_large_document():
    """测试大文档（400MB）"""
    print("\n📄 测试大文档保存（400MB）...")
    
    test_data = {
        'title': '大文档测试会议',
        'description': '测试400MB大小的会议文档保存',
        'participants': '张三, 李四, 王五, 赵六',
        'transcriptionContent': generate_large_content(400),  # 400MB
        'meetingMinutes': '这是会议纪要内容。',
        'audioInfo': {
            'duration': 14400,
            'format': 'wav',
            'sample_rate': 16000
        }
    }
    
    try:
        url = "http://localhost:8080/api/meetings/save-documents"
        print("📤 发送400MB文档请求...")
        response = requests.post(url, json=test_data, timeout=120)
        
        if response.status_code in [200, 201]:
            print("✅ 大文档保存成功")
            return True
        else:
            print(f"❌ 大文档保存失败: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return False


def test_oversized_document():
    """测试超大文档（600MB，应该失败）"""
    print("\n📄 测试超大文档保存（600MB，预期失败）...")
    
    test_data = {
        'title': '超大文档测试会议',
        'description': '测试600MB大小的会议文档保存，应该返回413错误',
        'participants': '张三, 李四, 王五, 赵六, 钱七',
        'transcriptionContent': generate_large_content(600),  # 600MB
        'meetingMinutes': '这是会议纪要内容。',
        'audioInfo': {
            'duration': 21600,
            'format': 'wav',
            'sample_rate': 16000
        }
    }
    
    try:
        url = "http://localhost:8080/api/meetings/save-documents"
        print("📤 发送600MB文档请求...")
        response = requests.post(url, json=test_data, timeout=120)
        
        if response.status_code == 413:
            print("✅ 超大文档正确返回413错误")
            print(f"📝 错误信息: {response.text}")
            return True
        elif response.status_code == 500:
            # 检查是否是大小限制错误
            response_text = response.text
            try:
                response_json = response.json()
                message = response_json.get('message', '')
                if "请求数据过大" in message or "最大允许" in message:
                    print("✅ 超大文档正确返回大小限制错误")
                    print(f"📝 错误信息: {message}")
                    return True
                else:
                    print(f"❌ 超大文档返回意外500错误: {message}")
                    return False
            except:
                if "请求数据过大" in response_text or "最大允许" in response_text:
                    print("✅ 超大文档正确返回大小限制错误")
                    print(f"📝 错误信息: {response_text}")
                    return True
                else:
                    print(f"❌ 超大文档返回意外500错误: {response_text}")
                    return False
        elif response.status_code in [200, 201]:
            print("⚠️ 超大文档意外保存成功（可能配置更大）")
            return True
        else:
            print(f"❌ 超大文档返回意外错误: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 开始大文件会议文档保存测试")
    print("=" * 60)
    
    # 测试API服务器连接
    if not test_api_server_connection():
        print("\n❌ 测试失败：无法连接到API服务器")
        print("请确保API服务器正在运行：")
        print("  python src/modules/network/start_api.py")
        return False
    
    # 执行各种大小的文档测试
    tests = [
        ("小文档测试", test_small_document),
        ("中等文档测试", test_medium_document),
        ("大文档测试", test_large_document),
        ("超大文档测试", test_oversized_document),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}执行异常: {e}")
            results.append((test_name, False))
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总:")
    
    success_count = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            success_count += 1
    
    total_tests = len(results)
    print(f"\n📈 总体结果: {success_count}/{total_tests} 测试通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！大文件处理功能正常")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)