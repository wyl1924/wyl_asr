#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket连接测试脚本
===================

用于测试FunASR WebSocket服务器的连接状态和基本功能。
"""

import asyncio
import websockets
import json
import sys
from datetime import datetime


async def test_websocket_connection(url: str = "ws://localhost:10095"):
    """
    测试WebSocket连接
    
    Args:
        url: WebSocket服务器地址
    """
    print(f"🔍 正在测试WebSocket连接: {url}")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    try:
        # 尝试连接 (使用binary子协议)
        print("🔄 正在连接...")
        async with websockets.connect(url, subprotocols=["binary"]) as websocket:
            print("✅ 连接成功!")
            print(f"📡 协议: {websocket.subprotocol}")
            print(f"🌐 本地地址: {websocket.local_address}")
            print(f"🎯 远程地址: {websocket.remote_address}")
            
            # 发送测试配置消息
            test_config = {
                "type": "test",
                "language": "zh",
                "sample_rate": 16000,
                "message": "WebSocket连接测试"
            }
            
            print("\n📤 发送测试配置...")
            await websocket.send(json.dumps(test_config))
            print(f"✅ 配置已发送: {test_config}")
            
            # 等待响应 (设置超时)
            print("\n⏳ 等待服务器响应...")
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 收到响应: {response}")
            except asyncio.TimeoutError:
                print("⚠️ 未收到响应 (5秒超时)")
            
            # 发送结束消息
            end_config = {"type": "end"}
            await websocket.send(json.dumps(end_config))
            print("📤 发送结束信号")
            
            print("\n🎉 WebSocket连接测试完成!")
            
    except ConnectionRefusedError:
        print("❌ 连接被拒绝 - 服务器可能未运行")
        return False
        
    except Exception as ws_error:
        if "InvalidStatusCode" in str(type(ws_error)):
            print(f"❌ HTTP状态码错误: {ws_error}")
            print("💡 提示: 可能是协议升级失败，检查服务器WebSocket配置")
        elif "WebSocketException" in str(type(ws_error)):
            print(f"❌ WebSocket错误: {ws_error}")
        else:
            print(f"❌ WebSocket相关错误: {ws_error}")
        return False
        
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False
    
    return True


async def test_multiple_ports():
    """测试多个常用端口"""
    ports = [10095, 10095, 8765, 8080]
    
    print("🔍 扫描常用WebSocket端口...")
    print("=" * 50)
    
    for port in ports:
        url = f"ws://localhost:{port}"
        print(f"\n🔍 测试端口 {port}...")
        
        success = await test_websocket_connection(url)
        if success:
            print(f"✅ 端口 {port} 测试成功!")
            return port
        else:
            print(f"❌ 端口 {port} 测试失败")
    
    print("\n❌ 所有端口测试均失败")
    return None


async def main():
    """主函数"""
    print("🎤 FunASR WebSocket连接测试工具")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        # 如果提供了参数，测试指定的URL
        url = sys.argv[1]
        await test_websocket_connection(url)
    else:
        # 否则扫描常用端口
        working_port = await test_multiple_ports()
        
        if working_port:
            print(f"\n🎯 建议的WebSocket地址: ws://localhost:{working_port}")
            print("📝 请在HTML测试页面中使用这个地址")
        else:
            print("\n💡 故障排除建议:")
            print("1. 检查FunASR服务器是否正在运行")
            print("2. 确认端口号是否正确")
            print("3. 检查防火墙设置")
            print("4. 查看服务器日志")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试程序异常: {e}")