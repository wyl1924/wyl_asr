#!/usr/bin/env python3
"""
简单的 WebSocket 测试服务器
用于测试语音识别显示应用
"""

import asyncio
import websockets
import json
from datetime import datetime

async def handle_client(websocket, path):
    """处理客户端连接"""
    print(f"客户端已连接: {websocket.remote_address}")
    
    try:
        # 发送测试消息
        test_messages = [
            {
                "type": "transcription",
                "speaker": {
                    "id": "speaker_001",
                    "name": "张三",
                    "icon": "avatar_001.png"
                },
                "content": {
                    "chinese": "你好，欢迎使用语音识别显示应用！",
                    "english": "Hello, welcome to the voice recognition display app!"
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            {
                "type": "transcription",
                "speaker": {
                    "id": "speaker_002",
                    "name": "李四",
                    "icon": "avatar_002.png"
                },
                "content": {
                    "chinese": "这是一个测试消息，用于验证应用功能。",
                    "english": "This is a test message to verify the application functionality."
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            {
                "type": "transcription",
                "speaker": {
                    "id": "speaker_001",
                    "name": "张三",
                    "icon": "avatar_001.png"
                },
                "content": {
                    "chinese": "应用支持实时显示语音转录内容。",
                    "english": "The app supports real-time display of voice transcription content."
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        ]
        
        # 每隔3秒发送一条消息
        for message in test_messages:
            await asyncio.sleep(3)
            json_message = json.dumps(message, ensure_ascii=False)
            await websocket.send(json_message)
            print(f"已发送消息: {message['speaker']['name']}: {message['content']['chinese']}")
        
        # 保持连接
        await websocket.wait_closed()
        
    except websockets.exceptions.ConnectionClosed:
        print(f"客户端已断开: {websocket.remote_address}")
    except Exception as e:
        print(f"错误: {e}")

async def main():
    """启动 WebSocket 服务器"""
    print("启动 WebSocket 测试服务器...")
    print("监听地址: ws://localhost:8080")
    print("按 Ctrl+C 停止服务器")
    
    async with websockets.serve(handle_client, "localhost", 8080):
        await asyncio.Future()  # 永久运行

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务器已停止")
