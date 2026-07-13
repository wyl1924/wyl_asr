#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的WebSocket连接测试
"""

import asyncio
import websockets
import json

async def test_connection():
    """测试WebSocket连接"""
    server_url = "ws://localhost:10095"
    
    try:
        print(f"🔄 正在连接到服务器: {server_url}")
        
        # 尝试不同的连接方式
        print("\n📋 测试1: 使用 binary 子协议")
        try:
            async with websockets.connect(server_url, subprotocols=["binary"]) as websocket:
                print("✅ 连接成功!")
                print(f"📡 协议: {websocket.subprotocol}")
                
                # 发送配置消息
                config = {
                    "mode": "online",
                    "chunk_interval": 10,
                    "wav_name": "test"
                }
                await websocket.send(json.dumps(config))
                print("📤 发送配置消息成功")
                
                # 等待响应
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    print(f"📨 收到响应: {response}")
                except asyncio.TimeoutError:
                    print("⚠️ 未收到响应 (5秒超时)")
                    
        except Exception as e:
            print(f"❌ binary 子协议连接失败: {e}")
            
        print("\n📋 测试2: 不使用子协议")
        try:
            async with websockets.connect(server_url) as websocket:
                print("✅ 无子协议连接成功!")
                
        except Exception as e:
            print(f"❌ 无子协议连接失败: {e}")
            
        print("\n📋 测试3: 使用 text 子协议")
        try:
            async with websockets.connect(server_url, subprotocols=["text"]) as websocket:
                print("✅ text 子协议连接成功!")
                print(f"📡 协议: {websocket.subprotocol}")
                
        except Exception as e:
            print(f"❌ text 子协议连接失败: {e}")
            
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())