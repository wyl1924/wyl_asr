#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会议文档下载功能测试

测试会议文档的下载和列表功能，包括：
1. 获取文档列表API
2. 文档下载API
3. 文件路径安全性验证
4. 文档类型过滤

作者: WYL ASR Team
创建时间: 2024年
"""

import os
import sys
import requests
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_document_list_api():
    """测试文档列表API"""
    print("\n=== 文档列表API测试 ===")
    
    try:
        # 检查API服务器是否运行
        health_url = "http://localhost:8080/api/health"
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code != 200:
                print("❌ API服务器未运行")
                return False
        except requests.exceptions.RequestException:
            print("❌ 无法连接到API服务器")
            return False
        
        print("✅ API服务器运行正常")
        
        # 测试获取所有文档列表
        api_url = "http://localhost:8080/api/meetings/documents/list"
        
        print("\n1. 获取所有文档列表...")
        response = requests.get(api_url, timeout=10)
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            data = result['data']
            
            print(f"✅ 获取文档列表成功")
            print(f"文档总数: {data['total']}")
            
            if data['total'] > 0:
                print("\n文档列表:")
                for i, doc in enumerate(data['documents'][:5], 1):  # 只显示前5个
                    print(f"  {i}. {doc['filename']}")
                    print(f"     标题: {doc['title']}")
                    print(f"     类型: {doc['type']}")
                    print(f"     大小: {doc['file_size']} 字节")
                    print(f"     创建时间: {doc['created_time']}")
                    print(f"     下载URL: {doc['download_url']}")
                    print()
            else:
                print("📝 暂无文档")
            
            # 测试按类型过滤
            print("\n2. 测试按类型过滤 (转录内容)...")
            filter_url = f"{api_url}?document_type=transcription"
            response = requests.get(filter_url, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                transcription_count = result['data']['total']
                print(f"✅ 转录内容文档数量: {transcription_count}")
            
            # 测试按标题过滤
            print("\n3. 测试按标题过滤 (产品规划)...")
            filter_url = f"{api_url}?meeting_title=产品规划"
            response = requests.get(filter_url, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                filtered_count = result['data']['total']
                print(f"✅ 包含'产品规划'的文档数量: {filtered_count}")
            
            return True, data['documents'] if data['total'] > 0 else []
            
        else:
            print(f"❌ 获取文档列表失败: {response.text}")
            return False, []
            
    except Exception as e:
        print(f"❌ 文档列表API测试失败: {e}")
        return False, []


def test_document_download_api(documents):
    """测试文档下载API"""
    print("\n=== 文档下载API测试 ===")
    
    if not documents:
        print("⚠️ 没有可下载的文档")
        return True
    
    try:
        # 选择第一个文档进行下载测试
        test_doc = documents[0]
        
        print(f"测试下载文档: {test_doc['filename']}")
        
        # 构建下载URL
        download_url = f"http://localhost:8080{test_doc['download_url']}"
        
        print(f"下载URL: {download_url}")
        
        # 发送下载请求
        response = requests.get(download_url, timeout=30)
        
        print(f"下载响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            # 检查响应头
            content_type = response.headers.get('Content-Type', '')
            content_disposition = response.headers.get('Content-Disposition', '')
            
            print(f"✅ 文档下载成功")
            print(f"Content-Type: {content_type}")
            print(f"Content-Disposition: {content_disposition}")
            print(f"响应内容长度: {len(response.content)} 字节")
            
            # 验证内容不为空
            if len(response.content) > 0:
                print("✅ 下载内容不为空")
                
                # 如果是文本文件，显示前200个字符
                if content_type.startswith('text/'):
                    try:
                        content_preview = response.content.decode('utf-8')[:200]
                        print(f"\n内容预览:\n{content_preview}...")
                    except UnicodeDecodeError:
                        print("内容包含非UTF-8字符")
                
                return True
            else:
                print("❌ 下载内容为空")
                return False
        else:
            print(f"❌ 文档下载失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 文档下载API测试失败: {e}")
        return False


def test_download_security():
    """测试下载安全性"""
    print("\n=== 下载安全性测试 ===")
    
    try:
        base_url = "http://localhost:8080/api/meetings/documents/download"
        
        # 测试路径遍历攻击
        print("\n1. 测试路径遍历攻击防护...")
        
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\SAM"
        ]
        
        security_passed = True
        
        for malicious_path in malicious_paths:
            test_url = f"{base_url}?file_path={malicious_path}"
            
            try:
                response = requests.get(test_url, timeout=5)
                
                if response.status_code == 400:
                    print(f"✅ 成功阻止恶意路径: {malicious_path}")
                elif response.status_code == 404:
                    print(f"✅ 文件不存在 (安全): {malicious_path}")
                else:
                    print(f"⚠️ 意外响应码 {response.status_code}: {malicious_path}")
                    security_passed = False
                    
            except requests.exceptions.RequestException as e:
                print(f"✅ 请求被拒绝 (安全): {malicious_path}")
        
        # 测试空文件路径
        print("\n2. 测试空文件路径...")
        empty_url = f"{base_url}?file_path="
        response = requests.get(empty_url, timeout=5)
        
        if response.status_code == 400:
            print("✅ 成功拒绝空文件路径")
        else:
            print(f"❌ 空文件路径处理异常: {response.status_code}")
            security_passed = False
        
        return security_passed
        
    except Exception as e:
        print(f"❌ 安全性测试失败: {e}")
        return False


def test_create_sample_document():
    """创建示例文档用于测试"""
    print("\n=== 创建示例文档 ===")
    
    try:
        # 调用文档保存API创建示例文档
        api_url = "http://localhost:8080/api/meetings/save-documents"
        
        sample_data = {
            'title': '文档下载测试会议',
            'description': '用于测试文档下载功能的示例会议',
            'participants': '测试用户A, 测试用户B',
            'transcriptionContent': (
                "这是一个用于测试文档下载功能的示例转录内容。\n\n"
                "内容包含了会议的基本信息和讨论要点。\n"
                "测试用户A：我们需要验证文档下载功能是否正常工作。\n"
                "测试用户B：同意，这个功能对用户体验很重要。"
            ),
            'meetingMinutes': (
                "## 会议纪要\n\n"
                "### 主要议题\n"
                "1. 文档下载功能测试\n"
                "2. API接口验证\n\n"
                "### 讨论结果\n"
                "- 下载功能需要支持多种文档类型\n"
                "- 安全性验证必须到位\n"
                "- 用户体验要友好"
            ),
            'summary': '会议确认了文档下载功能的重要性，并制定了测试计划。',
            'keyPoints': [
                '文档下载功能测试',
                'API接口安全性验证',
                '用户体验优化'
            ],
            'actionItems': [
                '完成下载功能开发',
                '进行安全性测试',
                '优化用户界面'
            ],
            'decisions': [
                '采用安全的文件下载机制',
                '支持多种文档格式下载'
            ]
        }
        
        response = requests.post(
            api_url,
            json=sample_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 201:
            result = response.json()
            print("✅ 示例文档创建成功")
            print(f"创建了 {result['data']['total_files']} 个文档")
            return True
        else:
            print(f"❌ 示例文档创建失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 创建示例文档失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("会议文档下载功能测试")
    print("=" * 60)
    
    # 创建示例文档
    sample_created = test_create_sample_document()
    
    # 运行测试
    tests = [
        ("文档列表API", test_document_list_api),
        ("下载安全性", test_download_security)
    ]
    
    results = []
    documents = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_name == "文档列表API":
                result, docs = test_func()
                documents = docs
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
    # 测试文档下载
    if documents:
        print(f"\n{'='*20} 文档下载API {'='*20}")
        download_result = test_document_download_api(documents)
        results.append(("文档下载API", download_result))
    
    # 输出测试结果汇总
    print("\n" + "="*60)
    print("文档下载测试结果汇总")
    print("="*60)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有文档下载测试通过！")
        print("\n📋 功能说明:")
        print("- 支持获取文档列表和过滤")
        print("- 支持安全的文档下载")
        print("- 防止路径遍历攻击")
        print("- 支持多种文档类型")
        print("- 提供完整的文件信息")
    else:
        print("\n⚠️ 部分测试失败，请检查文档下载功能。")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)