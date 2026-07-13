#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档保存功能测试

测试会议文档保存到本地文件夹的功能，包括：
1. 转录内容保存为Markdown文件
2. 会议纪要保存为Markdown文件
3. 音频信息保存为文本文件
4. 文件格式和内容验证

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


def test_save_meeting_documents():
    """测试会议文档保存API"""
    print("\n=== 会议文档保存API测试 ===")
    
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
        
        # 准备测试数据
        test_data = {
            'title': '文档保存测试会议',
            'description': '测试会议文档保存到本地文件夹的功能',
            'participants': '张三, 李四, 王五',
            'transcriptionContent': (
                "这是一段测试的语音转录内容。\n\n"
                "会议讨论了以下几个重要议题：\n"
                "1. 项目进展情况汇报\n"
                "2. 技术方案讨论\n"
                "3. 下一步工作安排\n\n"
                "张三：项目目前进展顺利，已完成70%的开发工作。\n"
                "李四：建议采用新的技术架构来提升性能。\n"
                "王五：同意李四的建议，需要进一步评估技术风险。\n\n"
                "经过充分讨论，大家达成了一致意见。"
            ),
            'meetingMinutes': (
                "## 会议纪要\n\n"
                "### 主要议题\n"
                "1. 项目进展汇报\n"
                "2. 技术方案讨论\n"
                "3. 工作安排\n\n"
                "### 讨论结果\n"
                "- 项目进展良好，按计划推进\n"
                "- 技术方案需要进一步优化\n"
                "- 下周安排技术评审会议"
            ),
            'summary': '会议总结：项目进展顺利，技术方案需要优化，下周进行技术评审。',
            'keyPoints': [
                '项目完成70%开发工作',
                '采用新技术架构提升性能',
                '需要评估技术风险',
                '下周安排技术评审会议'
            ],
            'actionItems': [
                '完成剩余30%的开发工作',
                '准备技术评审材料',
                '评估新技术架构的风险',
                '安排下周技术评审会议'
            ],
            'decisions': [
                '采用新的技术架构方案',
                '下周三举行技术评审会议',
                '项目按原计划推进'
            ],
            'audioFileName': 'test_meeting_audio.wav',
            'audioFilePath': '/path/to/audio/test_meeting_audio.wav',
            'audioFileSize': 1024000,
            'audioFormat': 'wav',
            'sampleRate': 16000,
            'channels': 1
        }
        
        # 调用文档保存API
        api_url = "http://localhost:8080/api/meetings/save-documents"
        
        print(f"开始保存会议文档...")
        
        response = requests.post(
            api_url,
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"API响应状态码: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            print("✅ 会议文档保存成功")
            
            data = result['data']
            print(f"会议标题: {data['title']}")
            print(f"时间戳: {data['timestamp']}")
            print(f"文档目录: {data['documents_directory']}")
            print(f"保存文件数量: {data['total_files']}")
            
            print("\n保存的文件列表:")
            for file_info in data['saved_files']:
                print(f"  - 类型: {file_info['type']}")
                print(f"    文件名: {file_info['filename']}")
                print(f"    路径: {file_info['path']}")
                print(f"    大小: {file_info['size']} 字节")
                print()
            
            return True, data
        else:
            print(f"❌ 文档保存失败: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ 文档保存测试失败: {e}")
        return False, None


def test_verify_saved_files(saved_data):
    """验证保存的文件内容"""
    print("\n=== 文件内容验证测试 ===")
    
    if not saved_data:
        print("❌ 没有保存数据可验证")
        return False
    
    try:
        documents_dir = saved_data['documents_directory']
        
        if not os.path.exists(documents_dir):
            print(f"❌ 文档目录不存在: {documents_dir}")
            return False
        
        print(f"✅ 文档目录存在: {documents_dir}")
        
        # 验证每个保存的文件
        all_files_valid = True
        
        for file_info in saved_data['saved_files']:
            file_path = file_info['path']
            file_type = file_info['type']
            
            print(f"\n验证文件: {file_info['filename']}")
            
            if not os.path.exists(file_path):
                print(f"❌ 文件不存在: {file_path}")
                all_files_valid = False
                continue
            
            # 检查文件大小
            actual_size = os.path.getsize(file_path)
            expected_size = file_info['size']
            
            if actual_size != expected_size:
                print(f"❌ 文件大小不匹配: 期望 {expected_size}, 实际 {actual_size}")
                all_files_valid = False
                continue
            
            # 读取文件内容进行验证
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 验证文件内容格式
                if file_type == 'transcription':
                    if '# 文档保存测试会议 - 转录内容' not in content:
                        print(f"❌ 转录文件格式不正确")
                        all_files_valid = False
                        continue
                    if '## 转录内容' not in content:
                        print(f"❌ 转录文件缺少内容标题")
                        all_files_valid = False
                        continue
                
                elif file_type == 'minutes':
                    if '# 文档保存测试会议 - 会议纪要' not in content:
                        print(f"❌ 纪要文件格式不正确")
                        all_files_valid = False
                        continue
                    if '## 关键要点' not in content:
                        print(f"❌ 纪要文件缺少关键要点")
                        all_files_valid = False
                        continue
                    if '## 行动项' not in content:
                        print(f"❌ 纪要文件缺少行动项")
                        all_files_valid = False
                        continue
                
                elif file_type == 'audio_info':
                    if '音频文件信息' not in content:
                        print(f"❌ 音频信息文件格式不正确")
                        all_files_valid = False
                        continue
                    if 'test_meeting_audio.wav' not in content:
                        print(f"❌ 音频信息文件缺少文件名")
                        all_files_valid = False
                        continue
                
                print(f"✅ 文件验证通过: {file_info['filename']}")
                print(f"   内容长度: {len(content)} 字符")
                print(f"   文件大小: {actual_size} 字节")
                
            except Exception as e:
                print(f"❌ 读取文件失败: {e}")
                all_files_valid = False
        
        return all_files_valid
        
    except Exception as e:
        print(f"❌ 文件验证失败: {e}")
        return False


def test_file_cleanup(saved_data):
    """清理测试文件"""
    print("\n=== 测试文件清理 ===")
    
    if not saved_data:
        return True
    
    try:
        cleaned_files = 0
        
        for file_info in saved_data['saved_files']:
            file_path = file_info['path']
            
            if os.path.exists(file_path):
                os.remove(file_path)
                cleaned_files += 1
                print(f"✅ 已删除: {file_info['filename']}")
        
        print(f"\n✅ 清理完成，共删除 {cleaned_files} 个测试文件")
        return True
        
    except Exception as e:
        print(f"❌ 文件清理失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("会议文档保存功能测试")
    print("=" * 60)
    
    tests = [
        ("文档保存API", test_save_meeting_documents),
    ]
    
    results = []
    saved_data = None
    
    # 运行主要测试
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_name == "文档保存API":
                result, data = test_func()
                saved_data = data
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
    # 运行文件验证测试
    if saved_data:
        print(f"\n{'='*20} 文件内容验证 {'='*20}")
        file_verification_result = test_verify_saved_files(saved_data)
        results.append(("文件内容验证", file_verification_result))
        
        # 询问是否清理测试文件
        print(f"\n{'='*20} 测试文件清理 {'='*20}")
        cleanup_result = test_file_cleanup(saved_data)
        results.append(("测试文件清理", cleanup_result))
    
    # 输出测试结果汇总
    print("\n" + "="*60)
    print("文档保存测试结果汇总")
    print("="*60)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有文档保存测试通过！")
        print("\n📁 功能说明:")
        print("- 转录内容保存为Markdown格式")
        print("- 会议纪要包含结构化信息")
        print("- 音频信息保存为文本格式")
        print("- 文件自动按时间戳命名")
        print("- 支持中文文件名和内容")
    else:
        print("\n⚠️ 部分测试失败，请检查文档保存功能。")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)