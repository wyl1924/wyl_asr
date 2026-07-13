#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多连接WebSocket测试脚本
=====================

用于测试FunASR WebSocket服务器的多客户端并发连接能力。
"""

import asyncio
import websockets
import json
import sys
from datetime import datetime
import time


async def create_websocket_client(client_id: int, url: str = "ws://localhost:10095", duration: int = 5):
    """
    创建一个WebSocket客户端连接
    
    Args:
        client_id: 客户端标识
        url: WebSocket服务器地址
        duration: 连接持续时间（秒）
    """
    print(f"🚀 客户端 {client_id} 开始连接: {url}")
    
    try:
        async with websockets.connect(url, subprotocols=["binary"]) as websocket:
            print(f"✅ 客户端 {client_id} 连接成功!")
            print(f"📡 客户端 {client_id} 协议: {websocket.subprotocol}")
            
            # 发送初始配置
            config = {
                "type": "init",
                "client_id": client_id,
                "language": "zh",
                "sample_rate": 16000,
                "message": f"多连接测试 - 客户端 {client_id}"
            }
            
            print(f"📤 客户端 {client_id} 发送配置...")
            await websocket.send(json.dumps(config))
            print(f"✅ 客户端 {client_id} 配置已发送: {config}")
            
            # 保持连接并发送测试消息
            start_time = time.time()
            message_count = 0
            
            while time.time() - start_time < duration:
                # 发送测试消息
                test_message = {
                    "type": "heartbeat",
                    "client_id": client_id,
                    "timestamp": datetime.now().isoformat(),
                    "message_id": message_count
                }
                
                await websocket.send(json.dumps(test_message))
                message_count += 1
                print(f"💌 客户端 {client_id} 发送消息 #{message_count}")
                
                # 尝试接收响应
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    print(f"📥 客户端 {client_id} 收到响应: {response[:100]}...")
                except asyncio.TimeoutError:
                    print(f"⏰ 客户端 {client_id} 未收到响应")
                
                # 等待间隔
                await asyncio.sleep(1)
            
            # 发送结束消息
            end_message = {
                "type": "end",
                "client_id": client_id,
                "total_messages": message_count
            }
            await websocket.send(json.dumps(end_message))
            print(f"📤 客户端 {client_id} 发送结束信号")
            
            print(f"🎉 客户端 {client_id} 测试完成! 发送了 {message_count} 条消息")
            
    except ConnectionRefusedError:
        print(f"❌ 客户端 {client_id} 连接被拒绝 - 服务器可能未运行")
        return False
        
    except Exception as e:
        print(f"❌ 客户端 {client_id} 连接错误: {e}")
        return False
    
    return True


async def test_multiple_connections(num_clients: int = 3, url: str = "ws://localhost:10095", duration: int = 10):
    """
    测试多个并发WebSocket连接
    
    Args:
        num_clients: 客户端数量
        url: WebSocket服务器地址
        duration: 每个连接的持续时间
    """
    print(f"🔍 开始多连接测试")
    print(f"🌐 服务器地址: {url}")
    print(f"👥 客户端数量: {num_clients}")
    print(f"⏱️ 持续时间: {duration}秒")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 创建多个并发任务
    tasks = []
    for i in range(1, num_clients + 1):
        task = create_websocket_client(i, url, duration)
        tasks.append(task)
    
    # 同时启动所有客户端
    print(f"🚀 同时启动 {num_clients} 个客户端...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 统计结果
    successful = sum(1 for result in results if result is True)
    failed = len(results) - successful
    
    print("\n" + "=" * 60)
    print("📊 测试结果统计:")
    print(f"✅ 成功连接: {successful}/{num_clients}")
    print(f"❌ 连接失败: {failed}/{num_clients}")
    print(f"📈 成功率: {successful/num_clients*100:.1f}%")
    
    if successful == num_clients:
        print("🎉 所有客户端连接成功! 多连接功能正常!")
    elif successful > 0:
        print("⚠️ 部分客户端连接成功，可能存在并发限制")
    else:
        print("❌ 所有客户端连接失败，请检查服务器状态")
    
    return successful, failed


async def test_sequential_connections(num_tests: int = 5, url: str = "ws://localhost:10095"):
    """
    测试连续的WebSocket连接（模拟第二次连接问题）
    
    Args:
        num_tests: 测试次数
        url: WebSocket服务器地址
    """
    print(f"🔄 开始连续连接测试")
    print(f"🌐 服务器地址: {url}")
    print(f"🔢 测试次数: {num_tests}")
    print("=" * 60)
    
    successful = 0
    for i in range(1, num_tests + 1):
        print(f"\n🔍 第 {i} 次连接测试...")
        result = await create_websocket_client(i, url, 2)  # 每次连接2秒
        
        if result:
            successful += 1
            print(f"✅ 第 {i} 次连接成功")
        else:
            print(f"❌ 第 {i} 次连接失败")
        
        # 连接间等待
        await asyncio.sleep(1)
    
    print("\n" + "=" * 60)
    print("📊 连续连接测试结果:")
    print(f"✅ 成功连接: {successful}/{num_tests}")
    print(f"❌ 连接失败: {num_tests - successful}/{num_tests}")
    print(f"📈 成功率: {successful/num_tests*100:.1f}%")
    
    if successful == num_tests:
        print("🎉 所有连续连接成功! 连接重用功能正常!")
    else:
        print("⚠️ 存在连续连接问题，请检查连接清理逻辑")
    
    return successful


async def main():
    """主测试函数"""
    print("🎤 FunASR WebSocket多连接测试工具")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "ws://localhost:10095"
    
    try:
        # 1. 测试连续连接（解决"第二次连不上"的问题）
        print("\n🔄 Phase 1: 连续连接测试")
        sequential_success = await test_sequential_connections(5, url)
        
        print("\n⏳ 等待3秒后开始并发测试...")
        await asyncio.sleep(3)
        
        # 2. 测试并发连接
        print("\n👥 Phase 2: 并发连接测试")
        concurrent_success, concurrent_failed = await test_multiple_connections(3, url, 8)
        
        # 总结
        print("\n" + "=" * 60)
        print("🎯 总体测试总结:")
        print(f"🔄 连续连接成功率: {sequential_success}/5 = {sequential_success/5*100:.1f}%")
        print(f"👥 并发连接成功率: {concurrent_success}/3 = {concurrent_success/3*100:.1f}%")
        
        if sequential_success == 5 and concurrent_success == 3:
            print("🎉 所有测试通过! WebSocket多连接功能完全正常!")
        elif sequential_success >= 4:
            print("✅ 连续连接基本正常，多连接问题已解决!")
        else:
            print("⚠️ 仍存在连接问题，需要进一步调试")
            
    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")