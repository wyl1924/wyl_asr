#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试2pass模式禁用online处理功能
验证2pass模式下只进行offline ASR处理，不进行online处理
"""

import asyncio
import websockets
import json
import wave
import numpy as np
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_test_audio(duration=3, sample_rate=16000):
    """
    生成测试音频数据
    """
    # 生成正弦波音频
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    frequency = 440  # A4音符
    audio = np.sin(2 * np.pi * frequency * t) * 0.3
    audio_int16 = (audio * 32767).astype(np.int16)
    return audio_int16.tobytes()

async def test_2pass_offline_only():
    """
    测试2pass模式只进行offline处理
    """
    uri = "ws://localhost:10095"
    
    try:
        async with websockets.connect(uri, subprotocols=['binary']) as websocket:
            logger.info("✅ WebSocket连接成功")
            
            # 发送2pass模式配置
            config = {
                "chunk_size": [5, 10, 5],
                "wav_name": "h5",
                "is_speaking": True,
                "chunk_interval": 10,
                "mode": "2pass",  # 使用2pass模式
                "language": "zh",
                "enable_speaker_diarization": False
            }
            
            logger.info(f"📤 发送2pass模式配置: {config}")
            await websocket.send(json.dumps(config))
            
            # 生成测试音频
            test_audio = generate_test_audio(duration=3)
            logger.info(f"🎵 生成测试音频，长度: {len(test_audio)} 字节")
            
            # 分块发送音频数据，模拟实时流
            chunk_size = 1024
            online_responses = []
            offline_responses = []
            
            for i in range(0, len(test_audio), chunk_size):
                chunk = test_audio[i:i+chunk_size]
                await websocket.send(chunk)
                
                # 尝试接收可能的online响应
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    response_data = json.loads(response)
                    
                    # 判断是否为online响应（通常is_final为False）
                    if not response_data.get('is_final', True):
                        online_responses.append(response_data)
                        logger.info(f"📥 收到online响应: {response_data.get('text', '')[:30]}...")
                    else:
                        offline_responses.append(response_data)
                        logger.info(f"📥 收到offline响应: {response_data.get('text', '')[:30]}...")
                        
                except asyncio.TimeoutError:
                    # 没有立即响应，继续发送
                    pass
                except json.JSONDecodeError:
                    # 非JSON响应，忽略
                    pass
                
                await asyncio.sleep(0.1)  # 模拟实时音频流间隔
            
            logger.info("📤 音频数据发送完成，等待最终响应")
            
            # 等待最终的offline响应
            timeout_count = 0
            max_timeout = 10
            
            while timeout_count < max_timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    response_data = json.loads(response)
                    
                    if response_data.get('is_final', False):
                        offline_responses.append(response_data)
                        logger.info(f"📥 收到最终offline响应: {response_data.get('text', '')}")
                        break
                    else:
                        online_responses.append(response_data)
                        logger.info(f"📥 收到online响应: {response_data.get('text', '')[:30]}...")
                        
                except asyncio.TimeoutError:
                    timeout_count += 1
                    logger.info(f"⏰ 等待响应超时 ({timeout_count}/{max_timeout})")
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ JSON解析失败: {e}")
                except Exception as e:
                    logger.error(f"❌ 接收响应时出错: {e}")
                    break
            
            # 分析结果
            logger.info(f"\n📊 测试结果分析:")
            logger.info(f"   Online响应数量: {len(online_responses)}")
            logger.info(f"   Offline响应数量: {len(offline_responses)}")
            
            if len(online_responses) == 0:
                logger.info("✅ 2pass模式成功禁用online处理")
                success = True
            else:
                logger.warning("⚠️ 2pass模式仍然有online响应，禁用可能未生效")
                success = False
                
            if len(offline_responses) > 0:
                logger.info("✅ Offline处理正常工作")
            else:
                logger.warning("⚠️ 未收到offline响应")
                success = False
                
            return success
                
    except websockets.ConnectionClosed:
        logger.error("❌ WebSocket连接被关闭")
        return False
    except websockets.InvalidURI:
        logger.error("❌ WebSocket URI无效")
        return False
    except Exception as e:
        logger.error(f"❌ 连接失败: {e}")
        return False

async def test_online_mode_comparison():
    """
    测试online模式作为对比，确保online模式仍然正常工作
    """
    uri = "ws://localhost:10095"
    
    try:
        async with websockets.connect(uri, subprotocols=['binary']) as websocket:
            logger.info("\n🔄 测试online模式作为对比")
            
            # 发送online模式配置
            config = {
                "chunk_size": [5, 10, 5],
                "wav_name": "h5",
                "is_speaking": True,
                "chunk_interval": 10,
                "mode": "online",  # 使用online模式
                "language": "zh"
            }
            
            logger.info(f"📤 发送online模式配置: {config}")
            await websocket.send(json.dumps(config))
            
            # 发送少量音频数据
            test_audio = generate_test_audio(duration=1)
            chunk_size = 1024
            online_responses = []
            
            for i in range(0, len(test_audio), chunk_size):
                chunk = test_audio[i:i+chunk_size]
                await websocket.send(chunk)
                
                # 尝试接收online响应
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                    response_data = json.loads(response)
                    online_responses.append(response_data)
                    logger.info(f"📥 Online模式响应: {response_data.get('text', '')[:30]}...")
                except asyncio.TimeoutError:
                    pass
                except json.JSONDecodeError:
                    pass
                
                await asyncio.sleep(0.1)
            
            logger.info(f"📊 Online模式响应数量: {len(online_responses)}")
            return len(online_responses) > 0
            
    except Exception as e:
        logger.error(f"❌ Online模式测试失败: {e}")
        return False

def main():
    """
    主测试函数
    """
    logger.info("🚀 开始测试2pass模式禁用online处理功能")
    logger.info("📋 测试目标:")
    logger.info("   1. 验证2pass模式不产生online响应")
    logger.info("   2. 验证2pass模式仍然产生offline响应")
    logger.info("   3. 对比验证online模式仍然正常工作")
    
    # 运行2pass模式测试
    logger.info("\n🧪 === 2pass模式测试 ===")
    result_2pass = asyncio.run(test_2pass_offline_only())
    
    # 运行online模式对比测试
    logger.info("\n🧪 === Online模式对比测试 ===")
    result_online = asyncio.run(test_online_mode_comparison())
    
    # 总结测试结果
    logger.info("\n📊 === 测试总结 ===")
    if result_2pass:
        logger.info("✅ 2pass模式禁用online处理测试通过")
    else:
        logger.warning("⚠️ 2pass模式禁用online处理测试未通过")
    
    if result_online:
        logger.info("✅ Online模式对比测试通过")
    else:
        logger.warning("⚠️ Online模式对比测试未通过")
    
    if result_2pass and result_online:
        logger.info("\n🎉 所有测试通过！2pass模式成功禁用online处理")
    else:
        logger.warning("\n⚠️ 部分测试未通过，请检查配置")
    
    logger.info("\n💡 使用说明:")
    logger.info("   - 2pass模式现在只进行offline高精度识别")
    logger.info("   - 减少了实时响应，但提高了最终识别精度")
    logger.info("   - Online模式仍然保持实时响应功能")

if __name__ == "__main__":
    main()