#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试完整会议保存功能

测试综合保存会议API的功能，包括：
1. 音频文件上传和保存
2. 语音转录内容保存
3. 会议纪要保存
4. 数据库记录创建

作者: WYL ASR Team
创建时间: 2024年
"""

import os
import sys
import json
import tempfile
import requests
from io import BytesIO
import wave
import numpy as np

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.database.database_manager import get_database_manager


def create_test_audio_file():
    """创建一个测试用的WAV音频文件"""
    # 生成1秒的正弦波音频（440Hz，A音）
    sample_rate = 16000
    duration = 1.0  # 1秒
    frequency = 440  # A音
    
    # 生成音频数据
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = np.sin(2 * np.pi * frequency * t)
    
    # 转换为16位整数
    audio_data = (audio_data * 32767).astype(np.int16)
    
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    
    # 写入WAV文件
    with wave.open(temp_file.name, 'wb') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16位
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())
    
    return temp_file.name


def test_save_complete_meeting_api():
    """测试综合保存会议API"""
    print("开始测试综合保存会议API...")
    
    # API端点
    api_url = "http://localhost:8080/api/meetings/save-complete"
    
    # 创建测试音频文件
    audio_file_path = create_test_audio_file()
    
    try:
        # 准备测试数据
        test_data = {
            'title': '测试会议 - 综合保存功能',
            'description': '这是一个测试会议，用于验证综合保存功能',
            'participants': '张三, 李四, 王五',
            'location': '会议室A',
            'transcriptionContent': '这是测试的语音转录内容。会议讨论了项目进展和下一步计划。',
            'meetingMinutes': '会议纪要：\n1. 项目进展顺利\n2. 需要加强测试\n3. 下周进行代码审查',
            'summary': '会议总结：项目按计划进行，团队协作良好。',
            'keyPoints': ['项目进展', '测试计划', '代码审查'],
            'actionItems': ['完成单元测试', '准备代码审查', '更新文档'],
            'decisions': ['采用新的测试框架', '增加自动化测试'],
            'audioFormat': 'wav',
            'sampleRate': 16000,
            'channels': 1,
            'confidence': 0.95,
            'language': 'zh-CN',
            'recognitionMode': 'offline'
        }
        
        # 准备文件上传
        files = {}
        data = {}
        
        # 添加音频文件
        with open(audio_file_path, 'rb') as f:
            files['audioFile'] = ('test_audio.wav', f, 'audio/wav')
            
            # 添加其他数据
            for key, value in test_data.items():
                if isinstance(value, list):
                    data[key] = json.dumps(value)
                else:
                    data[key] = str(value)
            
            # 发送请求
            print(f"发送请求到: {api_url}")
            response = requests.post(api_url, data=data, files=files)
        
        # 检查响应
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 201:
            result = response.json()
            print("✅ 会议保存成功!")
            print(f"会议ID: {result['data']['meeting_id']}")
            print(f"音频ID: {result['data']['audio_id']}")
            print(f"转录结果ID: {result['data']['speech_result_id']}")
            print(f"会议纪要ID: {result['data']['minutes_id']}")
            return True
        else:
            print(f"❌ 会议保存失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False
    finally:
        # 清理临时文件
        if os.path.exists(audio_file_path):
            os.unlink(audio_file_path)


def test_database_records():
    """测试数据库记录是否正确创建"""
    print("\n检查数据库记录...")
    
    try:
        db = get_database_manager()
        
        # 获取最新的会议记录
        meetings = db.get_all_meetings()
        if meetings:
            meeting = meetings[0]
            print(f"✅ 找到会议记录: {meeting['title']}")
            
            # 检查音频文件记录
            audio_files = db.get_meeting_audio_files(meeting['id'])
            if audio_files:
                print(f"✅ 找到音频文件记录: {len(audio_files)} 个")
            else:
                print("⚠️ 未找到音频文件记录")
            
            # 检查转录结果
            speech_results = db.get_meeting_speech_results(meeting['id'])
            if speech_results:
                print(f"✅ 找到转录结果: {len(speech_results)} 个")
            else:
                print("⚠️ 未找到转录结果")
            
            # 检查会议纪要
            minutes = db.get_meeting_minutes(meeting['id'])
            if minutes:
                print(f"✅ 找到会议纪要")
            else:
                print("⚠️ 未找到会议纪要")
            
            return True
        else:
            print("❌ 未找到会议记录")
            return False
            
    except Exception as e:
        print(f"❌ 检查数据库记录时发生错误: {e}")
        return False


def test_audio_file_storage():
    """测试音频文件是否正确保存到磁盘"""
    print("\n检查音频文件存储...")
    
    try:
        audio_dir = os.path.join(os.getcwd(), 'data', 'audio')
        
        if not os.path.exists(audio_dir):
            print(f"❌ 音频存储目录不存在: {audio_dir}")
            return False
        
        # 检查目录中的文件
        audio_files = [f for f in os.listdir(audio_dir) if f.endswith(('.wav', '.mp3', '.mp4'))]
        
        if audio_files:
            print(f"✅ 找到音频文件: {len(audio_files)} 个")
            for file in audio_files[-3:]:  # 显示最新的3个文件
                file_path = os.path.join(audio_dir, file)
                file_size = os.path.getsize(file_path)
                print(f"  - {file} ({file_size} bytes)")
            return True
        else:
            print("⚠️ 音频存储目录为空")
            return False
            
    except Exception as e:
        print(f"❌ 检查音频文件存储时发生错误: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("会议综合保存功能测试")
    print("=" * 60)
    
    # 检查服务器是否运行
    try:
        response = requests.get("http://localhost:8080/api/health", timeout=5)
        if response.status_code != 200:
            print("❌ API服务器未运行或不可访问")
            print("请先启动主程序: python main.py")
            return False
    except requests.exceptions.RequestException:
        print("❌ 无法连接到API服务器")
        print("请先启动主程序: python main.py")
        return False
    
    print("✅ API服务器运行正常")
    
    # 运行测试
    tests = [
        ("API接口测试", test_save_complete_meeting_api),
        ("数据库记录测试", test_database_records),
        ("音频文件存储测试", test_audio_file_storage)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        result = test_func()
        results.append((test_name, result))
    
    # 输出测试结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有测试通过！会议综合保存功能正常工作。")
    else:
        print("\n⚠️ 部分测试失败，请检查相关功能。")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)