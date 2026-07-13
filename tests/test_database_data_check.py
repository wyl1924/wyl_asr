#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from src.modules.database.database_manager import get_database_manager

def check_database_data():
    db = get_database_manager()
    
    # 获取所有会议
    meetings = db.get_all_meetings()
    print(f"数据库中共有 {len(meetings)} 个会议记录")
    
    # 查找测试相关的会议
    test_meetings = []
    for m in meetings:
        if '大文本' in m['title'] or '测试会议' in m['title']:
            test_meetings.append(m)
    
    print(f"\n找到 {len(test_meetings)} 个测试会议:")
    
    for meeting in test_meetings[-5:]:  # 显示最近5个
        print(f"\n会议ID: {meeting['id']}")
        print(f"标题: {meeting['title']}")
        print(f"创建时间: {meeting['start_time']}")
        
        # 检查转录结果
        speech_results = db.get_meeting_speech_results(meeting['id'])
        print(f"转录结果数量: {len(speech_results)}")
        
        if speech_results:
            text_length = len(speech_results[0]['text_content'])
            print(f"转录内容长度: {text_length} 字符")
            
            # 显示前100个字符作为预览
            preview = speech_results[0]['text_content'][:100]
            print(f"内容预览: {preview}...")
        
        # 检查会议纪要
        minutes = db.get_meeting_minutes(meeting['id'])
        if minutes:
            summary_length = len(minutes['summary'])
            print(f"会议纪要长度: {summary_length} 字符")
            
            # 显示前100个字符作为预览
            preview = minutes['summary'][:100]
            print(f"纪要预览: {preview}...")
        else:
            print("会议纪要: 不存在")
        
        print("-" * 50)

if __name__ == "__main__":
    check_database_data()