#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会议文档保存功能演示

演示如何使用新的文档保存API将转录内容和会议纪要保存为本地文档文件

作者: WYL ASR Team
创建时间: 2024年
"""

import requests
import json
from datetime import datetime

def demo_save_meeting_documents():
    """演示会议文档保存功能"""
    print("=" * 60)
    print("会议文档保存功能演示")
    print("=" * 60)
    
    # 模拟会议数据
    meeting_data = {
        'title': '产品规划会议',
        'description': '讨论2024年第四季度产品规划和技术路线',
        'participants': '张经理, 李工程师, 王设计师, 陈产品经理',
        'transcriptionContent': (
            "张经理：大家好，今天我们来讨论一下第四季度的产品规划。\n\n"
            "李工程师：从技术角度来看，我们需要重点关注以下几个方面：\n"
            "1. 系统性能优化，目标是响应时间减少30%\n"
            "2. 新功能模块的开发，包括AI智能推荐系统\n"
            "3. 移动端适配和用户体验提升\n\n"
            "王设计师：UI设计方面，我建议采用更现代化的设计语言，\n"
            "提升用户界面的美观性和易用性。同时需要考虑无障碍设计。\n\n"
            "陈产品经理：市场调研显示，用户对个性化功能的需求很强烈，\n"
            "我们应该在这方面加大投入。另外，竞品分析表明我们在某些\n"
            "功能上还有提升空间。\n\n"
            "张经理：好的，那我们来总结一下今天的讨论内容，\n"
            "制定具体的行动计划和时间节点。"
        ),
        'meetingMinutes': (
            "## 会议背景\n"
            "本次会议旨在制定2024年第四季度产品发展规划，\n"
            "确保产品能够满足市场需求并保持竞争优势。\n\n"
            "## 主要讨论内容\n"
            "### 技术发展方向\n"
            "- 系统性能优化：目标响应时间减少30%\n"
            "- AI智能推荐系统开发\n"
            "- 移动端适配优化\n\n"
            "### 设计改进计划\n"
            "- 采用现代化设计语言\n"
            "- 提升用户界面美观性\n"
            "- 加强无障碍设计\n\n"
            "### 产品功能规划\n"
            "- 增强个性化功能\n"
            "- 补齐竞品功能差距\n"
            "- 提升用户体验"
        ),
        'summary': (
            "会议确定了第四季度产品发展的三个重点方向：\n"
            "技术性能优化、用户界面升级和个性化功能增强。\n"
            "各部门将按照制定的时间节点推进相关工作。"
        ),
        'keyPoints': [
            '系统性能优化，响应时间减少30%',
            'AI智能推荐系统开发',
            '移动端适配和用户体验提升',
            '采用现代化设计语言',
            '加强个性化功能开发',
            '补齐竞品功能差距'
        ],
        'actionItems': [
            '李工程师负责性能优化方案设计（截止日期：10月15日）',
            '王设计师完成新UI设计稿（截止日期：10月20日）',
            '陈产品经理整理用户需求文档（截止日期：10月10日）',
            '张经理协调各部门资源配置（截止日期：10月8日）'
        ],
        'decisions': [
            '确定第四季度产品发展三大重点方向',
            '批准AI智能推荐系统开发预算',
            '同意UI设计语言升级方案',
            '决定加大个性化功能投入'
        ],
        'audioFileName': 'product_planning_meeting_20240904.wav',
        'audioFilePath': '/data/audio/product_planning_meeting_20240904.wav',
        'audioFileSize': 15728640,  # 15MB
        'audioFormat': 'wav',
        'sampleRate': 16000,
        'channels': 1
    }
    
    try:
        # 调用文档保存API
        api_url = "http://localhost:8080/api/meetings/save-documents"
        
        print(f"📝 开始保存会议文档...")
        print(f"会议标题: {meeting_data['title']}")
        print(f"参与人员: {meeting_data['participants']}")
        print(f"转录内容长度: {len(meeting_data['transcriptionContent'])} 字符")
        print(f"会议纪要长度: {len(meeting_data['meetingMinutes'])} 字符")
        
        response = requests.post(
            api_url,
            json=meeting_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 201:
            result = response.json()
            data = result['data']
            
            print(f"\n✅ 会议文档保存成功！")
            print(f"时间戳: {data['timestamp']}")
            print(f"文档目录: {data['documents_directory']}")
            print(f"保存文件数量: {data['total_files']}")
            
            print(f"\n📁 保存的文件列表:")
            for i, file_info in enumerate(data['saved_files'], 1):
                file_type_names = {
                    'transcription': '转录内容',
                    'minutes': '会议纪要',
                    'audio_info': '音频信息'
                }
                type_name = file_type_names.get(file_info['type'], file_info['type'])
                
                print(f"  {i}. {type_name}")
                print(f"     文件名: {file_info['filename']}")
                print(f"     大小: {file_info['size']} 字节")
                print(f"     路径: {file_info['path']}")
                print()
            
            # 显示文件内容预览
            print(f"📄 文件内容预览:")
            import os
            for file_info in data['saved_files']:
                if os.path.exists(file_info['path']):
                    print(f"\n--- {file_info['filename']} ---")
                    with open(file_info['path'], 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 显示前200个字符
                        preview = content[:200] + "..." if len(content) > 200 else content
                        print(preview)
            
            print(f"\n🎉 演示完成！")
            print(f"\n💡 使用说明:")
            print(f"- 转录内容和会议纪要已保存为Markdown格式")
            print(f"- 文件包含完整的会议信息和结构化数据")
            print(f"- 支持中文内容和特殊字符")
            print(f"- 文件自动按时间戳命名，避免重复")
            print(f"- 可直接用Markdown编辑器打开查看")
            
            return True
            
        else:
            print(f"❌ 保存失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 演示失败: {e}")
        return False


if __name__ == "__main__":
    success = demo_save_meeting_documents()
    if success:
        print(f"\n✨ 会议文档保存功能演示成功完成！")
    else:
        print(f"\n❌ 演示失败，请检查API服务器状态。")