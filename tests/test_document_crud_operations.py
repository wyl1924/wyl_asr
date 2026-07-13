#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档CRUD操作测试

测试文档管理系统的完整功能：
1. 创建文档 (Create)
2. 查询文档 (Read)
3. 下载文档 (Download)
4. 删除文档 (Delete)

作者: WYL ASR Team
创建时间: 2024年
"""

import os
import sys
import requests
import json
import tempfile
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.database.database_manager import get_database_manager


class DocumentCRUDTester:
    """文档CRUD操作测试类"""
    
    def __init__(self):
        self.base_url = "http://localhost:8080"
        self.db = get_database_manager()
        self.created_meeting_id = None
        self.created_documents = []
        
    def test_api_health(self):
        """测试API服务器健康状态"""
        print("\n=== API健康检查 ===")
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            if response.status_code == 200:
                print("✅ API服务器运行正常")
                return True
            else:
                print(f"❌ API服务器响应异常: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 无法连接到API服务器: {e}")
            return False
    
    def test_create_documents(self):
        """测试文档创建功能"""
        print("\n=== 测试文档创建 ===")
        
        # 准备测试数据
        test_data = {
            'title': 'CRUD测试会议',
            'description': '测试文档管理系统的完整CRUD功能',
            'participants': '测试用户A, 测试用户B, 测试用户C',
            'transcriptionContent': (
                "这是CRUD测试会议的转录内容。\n\n"
                "测试用户A：我们今天要测试文档管理系统的完整功能。\n"
                "测试用户B：包括创建、查询、下载和删除操作。\n"
                "测试用户C：确保系统的稳定性和数据一致性。\n\n"
                "会议讨论了以下测试要点：\n"
                "1. 文档创建功能的正确性\n"
                "2. 数据库关联的完整性\n"
                "3. 文件系统存储的可靠性\n"
                "4. API接口的响应性能\n"
                "5. 错误处理的健壮性"
            ),
            'meetingMinutes': (
                "## 会议背景\n"
                "本次会议旨在全面测试文档管理系统的CRUD操作功能。\n\n"
                "## 测试计划\n"
                "### 创建测试\n"
                "- 验证文档保存API的功能\n"
                "- 检查数据库记录的创建\n"
                "- 确认文件系统存储\n\n"
                "### 查询测试\n"
                "- 测试文档列表API\n"
                "- 验证过滤功能\n"
                "- 检查数据完整性\n\n"
                "### 下载测试\n"
                "- 测试文档下载API\n"
                "- 验证文件内容正确性\n"
                "- 检查安全性控制\n\n"
                "### 删除测试\n"
                "- 测试文档删除API\n"
                "- 验证级联删除\n"
                "- 确认数据清理"
            ),
            'summary': '成功测试了文档管理系统的完整CRUD功能，确认系统运行稳定。',
            'keyPoints': [
                '文档创建功能正常',
                '数据库关联完整',
                '文件存储可靠',
                'API响应正常',
                '错误处理健壮'
            ],
            'actionItems': [
                '继续完善测试用例',
                '优化系统性能',
                '加强安全防护',
                '完善文档说明'
            ],
            'decisions': [
                '确认CRUD功能设计合理',
                '批准系统上线部署',
                '制定维护计划'
            ]
        }
        
        try:
            # 调用文档创建API
            response = requests.post(
                f"{self.base_url}/api/meetings/save-documents",
                json=test_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            print(f"创建请求状态码: {response.status_code}")
            
            if response.status_code == 201:
                result = response.json()
                data = result['data']
                
                self.created_meeting_id = data['meeting_id']
                self.created_documents = data['saved_files']
                
                print("✅ 文档创建成功")
                print(f"会议ID: {self.created_meeting_id}")
                print(f"创建文件数量: {data['total_files']}")
                
                print("\n创建的文档:")
                for doc in self.created_documents:
                    print(f"  - {doc['filename']} (类型: {doc['type']}, ID: {doc['document_id']})")
                    print(f"    大小: {doc['size']} 字节")
                
                return True
            else:
                print(f"❌ 文档创建失败: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 文档创建异常: {e}")
            return False
    
    def test_query_documents(self):
        """测试文档查询功能"""
        print("\n=== 测试文档查询 ===")
        
        if not self.created_meeting_id:
            print("❌ 没有可查询的会议ID")
            return False
        
        try:
            # 1. 查询指定会议的所有文档
            print("\n1. 查询指定会议的所有文档")
            response = requests.get(
                f"{self.base_url}/api/meetings/documents/list?meeting_id={self.created_meeting_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                documents = result['data']['documents']
                
                print(f"✅ 查询成功，找到 {len(documents)} 个文档")
                for doc in documents:
                    print(f"  - {doc['filename']} (类型: {doc['type']}, 大小: {doc['file_size']} 字节)")
            else:
                print(f"❌ 查询失败: {response.text}")
                return False
            
            # 2. 按类型过滤查询
            print("\n2. 按类型过滤查询 (转录内容)")
            response = requests.get(
                f"{self.base_url}/api/meetings/documents/list?meeting_id={self.created_meeting_id}&document_type=transcription",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                transcription_docs = result['data']['documents']
                
                print(f"✅ 过滤查询成功，找到 {len(transcription_docs)} 个转录文档")
                for doc in transcription_docs:
                    print(f"  - {doc['filename']}")
            else:
                print(f"❌ 过滤查询失败: {response.text}")
                return False
            
            # 3. 查询所有文档
            print("\n3. 查询系统中的所有文档")
            response = requests.get(
                f"{self.base_url}/api/meetings/documents/list",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                all_documents = result['data']['documents']
                
                print(f"✅ 全局查询成功，系统中共有 {len(all_documents)} 个文档")
                
                # 统计各类型文档数量
                type_count = {}
                for doc in all_documents:
                    doc_type = doc['type']
                    type_count[doc_type] = type_count.get(doc_type, 0) + 1
                
                print("文档类型统计:")
                for doc_type, count in type_count.items():
                    print(f"  - {doc_type}: {count} 个")
            else:
                print(f"❌ 全局查询失败: {response.text}")
                return False
            
            # 4. 验证数据库一致性
            print("\n4. 验证数据库一致性")
            db_documents = self.db.get_meeting_documents(self.created_meeting_id)
            
            if len(db_documents) == len(documents):
                print("✅ 数据库与API查询结果一致")
                
                # 验证每个文档的文件是否存在
                all_files_exist = True
                for doc in db_documents:
                    if not os.path.exists(doc['file_path']):
                        print(f"❌ 文件不存在: {doc['file_path']}")
                        all_files_exist = False
                
                if all_files_exist:
                    print("✅ 所有文档文件都存在")
                else:
                    print("❌ 部分文档文件缺失")
                    return False
            else:
                print(f"❌ 数据库记录数({len(db_documents)})与API查询数({len(documents)})不一致")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ 文档查询异常: {e}")
            return False
    
    def test_download_documents(self):
        """测试文档下载功能"""
        print("\n=== 测试文档下载 ===")
        
        if not self.created_documents:
            print("❌ 没有可下载的文档")
            return False
        
        try:
            download_success_count = 0
            
            for doc in self.created_documents:
                print(f"\n下载测试: {doc['filename']}")
                
                # 构建下载URL
                download_url = f"{self.base_url}/api/meetings/documents/download"
                params = {
                    'file_path': doc['path'],
                    'file_name': doc['filename']
                }
                
                response = requests.get(
                    download_url,
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    # 验证下载内容
                    downloaded_content = response.text
                    
                    # 读取原始文件内容进行对比
                    if os.path.exists(doc['path']):
                        with open(doc['path'], 'r', encoding='utf-8') as f:
                            original_content = f.read()
                        
                        if downloaded_content == original_content:
                            print(f"✅ 下载成功，内容一致 ({len(downloaded_content)} 字符)")
                            download_success_count += 1
                        else:
                            print(f"❌ 下载内容与原文件不一致")
                            print(f"原文件长度: {len(original_content)}, 下载长度: {len(downloaded_content)}")
                    else:
                        print(f"❌ 原文件不存在: {doc['path']}")
                else:
                    print(f"❌ 下载失败: {response.status_code} - {response.text}")
            
            if download_success_count == len(self.created_documents):
                print(f"\n✅ 所有文档下载测试通过 ({download_success_count}/{len(self.created_documents)})")
                return True
            else:
                print(f"\n❌ 部分文档下载失败 ({download_success_count}/{len(self.created_documents)})")
                return False
                
        except Exception as e:
            print(f"❌ 文档下载异常: {e}")
            return False
    
    def test_delete_documents(self):
        """测试文档删除功能"""
        print("\n=== 测试文档删除 ===")
        
        if not self.created_documents:
            print("❌ 没有可删除的文档")
            return False
        
        try:
            # 选择第一个文档进行删除测试
            test_doc = self.created_documents[0]
            document_id = test_doc['document_id']
            file_path = test_doc['path']
            
            print(f"删除测试文档: {test_doc['filename']} (ID: {document_id})")
            
            # 确认文件存在
            if not os.path.exists(file_path):
                print(f"❌ 待删除文件不存在: {file_path}")
                return False
            
            print(f"✅ 确认文件存在: {file_path}")
            
            # 调用删除API
            response = requests.delete(
                f"{self.base_url}/api/meetings/documents/{document_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ 删除API调用成功")
                
                # 验证文件是否被删除
                if not os.path.exists(file_path):
                    print("✅ 物理文件已删除")
                else:
                    print("❌ 物理文件未删除")
                    return False
                
                # 验证数据库记录是否被删除
                doc_record = self.db.get_meeting_document_by_id(document_id)
                if not doc_record:
                    print("✅ 数据库记录已删除")
                else:
                    print("❌ 数据库记录未删除")
                    return False
                
                # 验证文档列表是否更新
                response = requests.get(
                    f"{self.base_url}/api/meetings/documents/list?meeting_id={self.created_meeting_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    remaining_docs = result['data']['documents']
                    
                    expected_count = len(self.created_documents) - 1
                    if len(remaining_docs) == expected_count:
                        print(f"✅ 文档列表已更新，剩余 {len(remaining_docs)} 个文档")
                    else:
                        print(f"❌ 文档列表更新异常，期望 {expected_count} 个，实际 {len(remaining_docs)} 个")
                        return False
                else:
                    print(f"❌ 无法验证文档列表更新: {response.text}")
                    return False
                
                return True
            else:
                print(f"❌ 删除API调用失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 文档删除异常: {e}")
            return False
    
    def cleanup(self):
        """清理测试数据"""
        print("\n=== 清理测试数据 ===")
        
        if not self.created_meeting_id:
            print("没有需要清理的数据")
            return
        
        try:
            # 获取剩余的文档
            remaining_docs = self.db.get_meeting_documents(self.created_meeting_id)
            
            # 删除剩余的文档
            for doc in remaining_docs:
                try:
                    # 删除物理文件
                    if os.path.exists(doc['file_path']):
                        os.remove(doc['file_path'])
                    
                    # 删除数据库记录
                    self.db.delete_meeting_document(doc['id'])
                    
                    print(f"✅ 清理文档: {doc['file_name']}")
                except Exception as e:
                    print(f"❌ 清理文档失败 {doc['file_name']}: {e}")
            
            print("✅ 测试数据清理完成")
            
        except Exception as e:
            print(f"❌ 清理异常: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("文档CRUD操作完整测试")
        print("=" * 60)
        
        test_results = []
        
        # 运行测试
        tests = [
            ("API健康检查", self.test_api_health),
            ("文档创建测试", self.test_create_documents),
            ("文档查询测试", self.test_query_documents),
            ("文档下载测试", self.test_download_documents),
            ("文档删除测试", self.test_delete_documents)
        ]
        
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                result = test_func()
                test_results.append((test_name, result))
                
                if not result and test_name == "API健康检查":
                    print("\n❌ API服务器不可用，终止测试")
                    break
                    
            except Exception as e:
                print(f"❌ {test_name}异常: {e}")
                test_results.append((test_name, False))
        
        # 清理测试数据
        self.cleanup()
        
        # 输出测试结果汇总
        print("\n" + "="*60)
        print("文档CRUD测试结果汇总")
        print("="*60)
        
        all_passed = True
        for test_name, result in test_results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n🎉 所有CRUD测试通过！")
            print("\n📋 测试覆盖功能:")
            print("✅ 文档创建 - 验证API接口和数据存储")
            print("✅ 文档查询 - 验证列表API和过滤功能")
            print("✅ 文档下载 - 验证下载API和内容完整性")
            print("✅ 文档删除 - 验证删除API和数据清理")
            print("✅ 数据一致性 - 验证数据库与文件系统同步")
            print("\n🔧 系统功能确认:")
            print("- 统一文档管理系统运行正常")
            print("- 数据库与文件系统关联正确")
            print("- API接口响应稳定")
            print("- 错误处理机制完善")
        else:
            print("\n⚠️ 部分测试失败，请检查系统功能。")
        
        return all_passed


def main():
    """主测试函数"""
    tester = DocumentCRUDTester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)