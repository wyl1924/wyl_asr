#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket 测试脚本
用于测试字幕显示应用的 WebSocket 连接和消息接收功能
"""

import asyncio
import websockets
import json
import time

async def test_subtitle_display():
    """测试字幕显示应用"""
    
    # 连接到 WebSocket 服务器
    uri = "ws://localhost:10095/"
    
    print(f"正在连接到 {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ 连接成功！")
            print("\n开始发送测试消息...\n")
            
            # 测试消息列表
            test_messages = [
                {
                    "speaker_name": "张三",
                    "text": "大家好，",
                    "is_final": False
                },
                {
                    "speaker_name": "张三",
                    "text": "今天我们来讨论一下人工智能的发展趋势。",
                    "is_final": True
                },
                {
                    "speaker_name": "李四",
                    "text": "我认为人工智能在未来会有更广泛的应用。",
                    "is_final": True
                },
                {
                    "speaker_name": "张三",
                    "text": "是的，",
                    "is_final": False
                },
                {
                    "speaker_name": "张三",
                    "text": "特别是在医疗和教育领域。",
                    "is_final": True
                },
                {
                    "speaker_name": "王五",
                    "text": "人工智能可以帮助医生更准确地诊断疾病，",
                    "is_final": False
                },
                {
                    "speaker_name": "王五",
                    "text": "也可以为学生提供个性化的学习方案。",
                    "is_final": True
                },
                {
                    "speaker_name": "李四",
                    "text": "这确实是一个很有前景的领域。我们应该继续关注和研究。",
                    "is_final": True
                },
            ]
            
            # 逐条发送测试消息
            for i, message in enumerate(test_messages, 1):
                # 添加额外的字段以模拟真实的 ASR 消息
                full_message = {
                    "mode": "test",
                    "wav_name": "test_audio",
                    **message
                }
                
                # 发送消息
                await websocket.send(json.dumps(full_message, ensure_ascii=False))
                
                print(f"[{i}/{len(test_messages)}] 发送: [{message['speaker_name']}] {message['text']}")
                
                # 等待一段时间，模拟实时语音识别
                await asyncio.sleep(1.5)
            
            print("\n✅ 所有测试消息发送完成！")
            print("请检查字幕显示应用是否正确显示了所有消息。")
            
    except ConnectionRefusedError:
        print("❌ 连接失败：无法连接到 WebSocket 服务器")
        print("请确保：")
        print("1. ASR 服务器正在运行")
        print("2. WebSocket 端口为 9002")
        print("3. 防火墙未阻止连接")
    except Exception as e:
        print(f"❌ 发生错误: {e}")

def main():
    """主函数"""
    print("=" * 60)
    print("字幕显示应用 - WebSocket 测试脚本")
    print("=" * 60)
    print()
    print("此脚本将向 WebSocket 服务器发送测试消息")
    print("用于验证字幕显示应用是否正常工作")
    print()
    print("使用方法:")
    print("1. 启动 ASR 服务器: python main.py (默认端口 10095)")
    print("2. 启动字幕显示应用: cd subtitle_display && dotnet run")
    print("3. 在字幕应用中点击'连接'按钮")
    print("4. 运行此测试脚本: python test_websocket.py")
    print()
    print("=" * 60)
    print()
    
    # 运行测试
    asyncio.run(test_subtitle_display())

if __name__ == "__main__":
    main()
