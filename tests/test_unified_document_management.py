#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一文档管理功能测试

测试修改后的统一文档管理系统，包括：
1. 数据库与文件系统关联
2. 统一的存储机制
3. 集中的文档管理入口
4. 完整的CRUD操作

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

from src.modules.database.database_manager import get_database_manager


def test_unified_document_save():
    """测试统一文档保存功能"""
    print("\n=== 统一文档保存测试 ===")
    
    try:
        # 检查API服务器
        health_url = "http://localhost:8080/api/health"
        response = requests.get(health_url, timeout=5)
        if response.status_code != 200:
            print("❌ API服务器未运行")
            return False, None
        
        print("✅ API服务器运行正常")
        
        # 测试数据
        test_data = {
            'title': '统一管理测试会议',
            'description': '测试数据库与文件系统统一管理功能',
            'participants': '测试用户A, 测试用户B, 测试用户C',
            'transcriptionContent': (
                "这是统一文档管理系统的测试内容。\n\n"
                "测试用户A：我们正在测试新的统一文档管理功能。\n"
                "测试用户B：这个功能将数据库和文件系统完美结合。\n"
                "测试用户C：现在文档管理更加统一和高效了。\n\n"
                "系统特点：\n"
                "1. 数据库记录与文件路径关联\n"
                "2. 统一的命名规则\n"
                "3. 集中的管理接口\n"
                "4. 完整的CRUD操作支持"
            ),
            'meetingMinutes': (
                "## 会议背景\n"
                "本次会议旨在测试统一文档管理系统的功能。\n\n"
                "## 测试内容\n"
                "### 核心功能验证\n"
                "- 数据库与文件系统关联 ✓\n"
                "- 统一存储机制 ✓\n"
                "- 集中管理入口 ✓\n"
                "- 完整CRUD操作 ✓\n\n"
                "### 改进效果\n"
                "- 消除了双重存储机制不统一的问题\n"
                "- 实现了文件路径的集中管理\n"
                "- 提供了统一的文档管理入口\n"
                "- 建立了数据库与文件系统的关联"
            ),
            'summary': '统一文档管理系统测试成功，解决了之前存在的四个核心问题。',
            'keyPoints': [
                '数据库与文件系统成功关联',
                '存储机制实现统一',
                '文档管理入口集中化',
                'CRUD操作功能完整'
            ],
            'actionItems': [
                '完成功能测试验证',
                '确认数据一致性',
                '验证文件路径管理',
                '测试删除功能'
            ],
            'decisions': [
                '采用统一的文档管理架构',
                '建立数据库文件关联机制',
                '实现集中化管理接口'
            ]
        }
        
        # 调用统一文档保存API
        api_url = "http://localhost:8080/api/meetings/save-documents"
        
        print("\n开始保存会议文档...")
        response = requests.post(
            api_url,
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"API响应状态码: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            data = result['data']
            
            print("✅ 统一文档保存成功")
            print(f"会议ID: {data['meeting_id']}")
            print(f"会议标题: {data['title']}")
            print(f"时间戳: {data['timestamp']}")
            print(f"保存文件数量: {data['total_files']}")
            
            print("\n保存的文件列表:")
            for file_info in data['saved_files']:
                print(f"  - 类型: {file_info['type']}")
                print(f"    文件名: {file_info['filename']}")
                print(f"    数据库ID: {file_info['document_id']}")
                print(f"    文件大小: {file_info['size']} 字节")
                print()
            
            return True, data
        else:
            print(f"❌ 文档保存失败: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ 统一文档保存测试失败: {e}")
        return False, None


def test_database_file_association(saved_data):
    """测试数据库与文件关联"""
    print("\n=== 数据库文件关联测试 ===")
    
    if not saved_data:
        print("❌ 没有保存数据可测试")
        return False
    
    try:
        db = get_database_manager()
        meeting_id = saved_data['meeting_id']
        
        print(f"检查会议ID {meeting_id} 的文档记录...")
        
        # 从数据库获取文档记录
        documents = db.get_meeting_documents(meeting_id)
        
        if not documents:
            print("❌ 数据库中没有找到文档记录")
            return False
        
        print(f"✅ 数据库中找到 {len(documents)} 个文档记录")
        
        # 验证每个文档记录
        all_valid = True
        for doc in documents:
            print(f"\n验证文档: {doc['file_name']}")
            print(f"  - 数据库ID: {doc['id']}")
            print(f"  - 文档类型: {doc['document_type']}")
            print(f"  - 文件路径: {doc['file_path']}")
            print(f"  - 文件大小: {doc['file_size']} 字节")
            
            # 检查文件是否存在
            if os.path.exists(doc['file_path']):
                actual_size = os.path.getsize(doc['file_path'])
                if actual_size == doc['file_size']:
                    print(f"  ✅ 文件存在且大小匹配")
                else:
                    print(f"  ⚠️ 文件大小不匹配: 数据库 {doc['file_size']}, 实际 {actual_size}")
                    all_valid = False
            else:
                print(f"  ❌ 文件不存在: {doc['file_path']}")
                all_valid = False
        
        return all_valid
        
    except Exception as e:
        print(f"❌ 数据库文件关联测试失败: {e}")
        return False


def test_unified_document_list(saved_data):
    """测试统一文档列表功能"""
    print("\n=== 统一文档列表测试 ===")
    
    if not saved_data:
        print("❌ 没有保存数据可测试")
        return False
    
    try:
        meeting_id = saved_data['meeting_id']
        
        # 测试获取指定会议的文档列表
        print(f"\n1. 获取会议ID {meeting_id} 的文档列表...")
        list_url = f"http://localhost:8080/api/meetings/documents/list?meeting_id={meeting_id}"
        response = requests.get(list_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            documents = result['data']['documents']
            
            print(f"✅ 获取到 {len(documents)} 个文档")
            
            for doc in documents:
                print(f"  - {doc['filename']} (类型: {doc['type']}, ID: {doc['id']})")
        else:
            print(f"❌ 获取文档列表失败: {response.text}")
            return False
        
        # 测试获取所有文档列表
        print("\n2. 获取所有文档列表...")
        all_list_url = "http://localhost:8080/api/meetings/documents/list"
        response = requests.get(all_list_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            all_documents = result['data']['documents']
            
            print(f"✅ 系统中共有 {len(all_documents)} 个文档")
            
            # 查找我们刚创建的文档
            our_docs = [doc for doc in all_documents if doc['meeting_id'] == meeting_id]
            print(f"✅ 其中 {len(our_docs)} 个属于测试会议")
        else:
            print(f"❌ 获取所有文档列表失败: {response.text}")
            return False
        
        # 测试按类型过滤
        print("\n3. 测试按类型过滤 (转录内容)...")
        filter_url = "http://localhost:8080/api/meetings/documents/list?document_type=transcription"
        response = requests.get(filter_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            transcription_docs = result['data']['documents']
            print(f"✅ 找到 {len(transcription_docs)} 个转录文档")
        else:
            print(f"❌ 按类型过滤失败: {response.text}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 统一文档列表测试失败: {e}")
        return False


def test_document_deletion(saved_data):
    """测试文档删除功能"""
    print("\n=== 文档删除功能测试 ===")
    
    if not saved_data:
        print("❌ 没有保存数据可测试")
        return False
    
    try:
        # 获取一个文档进行删除测试
        meeting_id = saved_data['meeting_id']
        
        # 先获取文档列表
        list_url = f"http://localhost:8080/api/meetings/documents/list?meeting_id={meeting_id}"
        response = requests.get(list_url, timeout=10)
        
        if response.status_code != 200:
            print("❌ 无法获取文档列表")
            return False
        
        documents = response.json()['data']['documents']
        if not documents:
            print("❌ 没有文档可删除")
            return False
        
        # 选择第一个文档进行删除测试
        test_doc = documents[0]
        document_id = test_doc['id']
        file_path = test_doc['file_path']
        
        print(f"准备删除文档: {test_doc['filename']} (ID: {document_id})")
        
        # 确认文件存在
        if not os.path.exists(file_path):
            print(f"⚠️ 文件不存在: {file_path}")
        else:
            print(f"✅ 确认文件存在: {file_path}")
        
        # 调用删除API
        delete_url = f"http://localhost:8080/api/meetings/documents/{document_id}"
        response = requests.delete(delete_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ 文档删除API调用成功")
            
            # 验证文件是否被删除
            if not os.path.exists(file_path):
                print("✅ 物理文件已删除")
            else:
                print("❌ 物理文件未删除")
                return False
            
            # 验证数据库记录是否被删除
            db = get_database_manager()
            doc_record = db.get_meeting_document_by_id(document_id)
            
            if not doc_record:
                print("✅ 数据库记录已删除")
            else:
                print("❌ 数据库记录未删除")
                return False
            
            return True
        else:
            print(f"❌ 文档删除失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 文档删除测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("统一文档管理功能测试")
    print("=" * 60)
    
    # 运行测试
    tests = [
        ("统一文档保存", test_unified_document_save),
    ]
    
    results = []
    saved_data = None
    
    # 运行主要测试
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_name == "统一文档保存":
                result, data = test_func()
                saved_data = data
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
    # 运行关联测试
    if saved_data:
        additional_tests = [
            ("数据库文件关联", lambda: test_database_file_association(saved_data)),
            ("统一文档列表", lambda: test_unified_document_list(saved_data)),
            ("文档删除功能", lambda: test_document_deletion(saved_data))
        ]
        
        for test_name, test_func in additional_tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name}测试异常: {e}")
                results.append((test_name, False))
    
    # 输出测试结果汇总
    print("\n" + "="*60)
    print("统一文档管理测试结果汇总")
    print("="*60)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有统一文档管理测试通过！")
        print("\n📋 解决的问题:")
        print("✅ 数据库与文件系统成功关联")
        print("✅ 两套存储机制实现统一")
        print("✅ 文件路径管理集中化")
        print("✅ 提供统一的文档管理入口")
        print("\n🔧 新增功能:")
        print("- 会议ID与文档文件关联")
        print("- 统一的文件命名规则")
        print("- 基于数据库的文档列表")
        print("- 完整的CRUD操作支持")
        print("- 数据一致性保证")
    else:
        print("\n⚠️ 部分测试失败，请检查统一文档管理功能。")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)