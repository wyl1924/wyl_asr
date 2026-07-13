#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket重连测试脚本
===================

专门测试WebSocket连接断开后重连的问题，帮助诊断和解决重连失败的情况。
"""

import asyncio
import websockets
import json
import sys
import time
from datetime import datetime


async def test_single_connection(url: str = "ws://localhost:10095", duration: int = 3):
    """
    测试单个WebSocket连接
    
    Args:
        url: WebSocket服务器地址
        duration: 连接持续时间（秒）
    
    Returns:
        bool: 连接是否成功
    """
    try:
        print(f"🔗 尝试连接: {url}")
        
        async with websockets.connect(
            url, 
            subprotocols=["binary"],
            ping_interval=None,  # 禁用ping/pong
            close_timeout=5      # 设置关闭超时
        ) as websocket:
            print(f"✅ 连接成功! 协议: {websocket.subprotocol}")
            
            # 发送初始配置
            config = {
                "type": "init",
                "language": "zh",
                "sample_rate": 16000,
                "test_time": datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(config))
            print(f"📤 配置已发送: {config}")
            
            # 保持连接指定时间
            await asyncio.sleep(duration)
            
            print(f"⏰ 连接保持 {duration} 秒，准备关闭")
            return True
            
    except websockets.ConnectionClosed as e:
        print(f"🔌 连接被关闭: {e}")
        return False
    except websockets.InvalidURI as e:
        print(f"❌ 无效的URI: {e}")
        return False
    except websockets.InvalidHandshake as e:
        print(f"❌ 握手失败: {e}")
        return False
    except ConnectionRefusedError as e:
        print(f"❌ 连接被拒绝: {e}")
        return False
    except OSError as e:
        print(f"❌ 网络错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return False


async def test_reconnection_sequence(url: str = "ws://localhost:10095", num_tests: int = 5, interval: int = 2):
    """
    测试连续重连序列
    
    Args:
        url: WebSocket服务器地址
        num_tests: 测试次数
        interval: 连接间隔（秒）
    """
    print(f"🔄 开始重连测试序列")
    print(f"🌐 服务器: {url}")
    print(f"🔢 测试次数: {num_tests}")
    print(f"⏱️ 间隔时间: {interval}秒")
    print("=" * 60)
    
    results = []
    
    for i in range(1, num_tests + 1):
        print(f"\n🧪 第 {i}/{num_tests} 次连接测试")
        print(f"⏰ 时间: {datetime.now().strftime('%H:%M:%S')}")
        
        start_time = time.time()
        success = await test_single_connection(url, 2)
        end_time = time.time()
        
        duration = end_time - start_time
        results.append({
            'test_num': i,
            'success': success,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        })
        
        if success:
            print(f"✅ 第 {i} 次连接成功 (耗时: {duration:.2f}秒)")
        else:
            print(f"❌ 第 {i} 次连接失败 (耗时: {duration:.2f}秒)")
        
        # 连接间等待
        if i < num_tests:
            print(f"⏳ 等待 {interval} 秒后进行下一次测试...")
            await asyncio.sleep(interval)
    
    # 统计结果
    successful = sum(1 for r in results if r['success'])
    failed = num_tests - successful
    success_rate = successful / num_tests * 100
    avg_duration = sum(r['duration'] for r in results) / num_tests
    
    print("\n" + "=" * 60)
    print("📊 重连测试结果统计:")
    print(f"✅ 成功连接: {successful}/{num_tests}")
    print(f"❌ 连接失败: {failed}/{num_tests}")
    print(f"📈 成功率: {success_rate:.1f}%")
    print(f"⏱️ 平均耗时: {avg_duration:.2f}秒")
    
    # 详细结果
    print("\n📋 详细测试结果:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"  {status} 测试 {result['test_num']}: {result['duration']:.2f}秒 - {result['timestamp']}")
    
    # 问题诊断
    if success_rate < 100:
        print("\n🔍 问题诊断建议:")
        if success_rate == 0:
            print("  • 服务器可能未启动或端口被占用")
            print("  • 检查防火墙设置")
            print("  • 验证服务器地址和端口")
        elif success_rate < 50:
            print("  • 服务器连接清理可能存在问题")
            print("  • 检查服务器日志中的错误信息")
            print("  • 可能存在资源泄漏或状态管理问题")
        else:
            print("  • 偶发性连接问题")
            print("  • 可能是网络延迟或服务器负载导致")
    else:
        print("\n🎉 所有重连测试成功! 连接功能正常!")
    
    return results


async def test_rapid_reconnection(url: str = "ws://localhost:10095", num_tests: int = 10):
    """
    测试快速重连（无间隔）
    
    Args:
        url: WebSocket服务器地址
        num_tests: 测试次数
    """
    print(f"\n⚡ 开始快速重连测试 (无间隔)")
    print(f"🔢 测试次数: {num_tests}")
    print("=" * 40)
    
    successful = 0
    
    for i in range(1, num_tests + 1):
        print(f"🔄 快速测试 {i}/{num_tests}", end=" ")
        success = await test_single_connection(url, 1)
        if success:
            successful += 1
            print("✅")
        else:
            print("❌")
    
    success_rate = successful / num_tests * 100
    print(f"\n⚡ 快速重连结果: {successful}/{num_tests} ({success_rate:.1f}%)")
    
    return successful


async def main():
    """主测试函数"""
    print("🔌 WebSocket重连测试工具")
    print("=" * 60)
    
    # 获取服务器地址
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "ws://localhost:10095"
    
    print(f"🎯 目标服务器: {url}")
    print(f"⏰ 测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1. 基础连接测试
        print("\n🧪 步骤1: 基础连接测试")
        basic_result = await test_single_connection(url, 3)
        
        if not basic_result:
            print("❌ 基础连接失败，请检查服务器状态")
            return
        
        # 2. 重连序列测试
        print("\n🧪 步骤2: 重连序列测试")
        await test_reconnection_sequence(url, 5, 2)
        
        # 3. 快速重连测试
        print("\n🧪 步骤3: 快速重连测试")
        await test_rapid_reconnection(url, 10)
        
        print("\n" + "=" * 60)
        print("🏁 所有测试完成!")
        print(f"⏰ 测试结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")