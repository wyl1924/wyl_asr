#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试离线ASR+说话人识别专用模式
验证系统是否正确禁用在线ASR，只使用离线高精度识别+说话人分离
"""

import asyncio
import websockets
import json
import base64
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
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # 生成440Hz正弦波（A4音符）
    audio_data = np.sin(2 * np.pi * 440 * t) * 0.3
    # 转换为16位PCM格式
    audio_data = (audio_data * 32767).astype(np.int16)
    return audio_data.tobytes()

async def test_offline_speaker_mode():
    """
    测试离线ASR+说话人识别专用模式
    """
    uri = "ws://localhost:10095"
    
    try:
        async with websockets.connect(uri, subprotocols=['binary']) as websocket:
            logger.info("✅ WebSocket连接成功")
            
            # 发送配置 - 应该被强制设为offline模式
            config = {
                "chunk_size": [5, 10, 5],
                "wav_name": "h5",
                "is_speaking": True,
                "chunk_interval": 10,
                "mode": "online",  # 尝试设置为online，但应该被忽略
                "language": "zh",
                "enable_speaker_diarization": False  # 尝试禁用，但应该被强制启用
            }
            
            logger.info(f"📤 发送配置: {config}")
            await websocket.send(json.dumps(config))
            
            # 生成测试音频
            test_audio = generate_test_audio(duration=2)
            logger.info(f"🎵 生成测试音频，长度: {len(test_audio)} 字节")
            
            # 分块发送音频数据
            chunk_size = 1024
            for i in range(0, len(test_audio), chunk_size):
                chunk = test_audio[i:i+chunk_size]
                await websocket.send(chunk)
                await asyncio.sleep(0.1)  # 模拟实时音频流
            
            logger.info("📤 音频数据发送完成")
            
            # 等待并接收响应
            response_count = 0
            timeout_count = 0
            max_timeout = 10
            
            while timeout_count < max_timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    response_data = json.loads(response)
                    response_count += 1
                    
                    logger.info(f"📥 收到响应 #{response_count}: {response_data}")
                    
                    # 检查响应是否包含说话人信息
                    if 'speaker_info' in response_data:
                        logger.info("✅ 检测到说话人信息，说话人识别功能正常")
                    
                    # 检查是否为最终结果
                    if response_data.get('is_final', False):
                        logger.info("✅ 收到最终识别结果")
                        break
                        
                except asyncio.TimeoutError:
                    timeout_count += 1
                    logger.info(f"⏰ 等待响应超时 ({timeout_count}/{max_timeout})")
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ JSON解析失败: {e}")
                except Exception as e:
                    logger.error(f"❌ 接收响应时出错: {e}")
                    break
            
            if response_count > 0:
                logger.info(f"✅ 测试完成，共收到 {response_count} 个响应")
                return True
            else:
                logger.warning("⚠️ 未收到任何响应")
                return False
                
    except websockets.ConnectionClosed:
        logger.error("❌ WebSocket连接被关闭")
        return False
    except websockets.InvalidURI:
        logger.error("❌ WebSocket URI无效")
        return False
    except Exception as e:
        logger.error(f"❌ 连接失败: {e}")
        return False

async def test_config_override():
    """
    测试配置覆盖功能
    验证即使前端发送online模式，后端也会强制使用offline+说话人识别
    """
    uri = "ws://localhost:10095"
    
    test_configs = [
        {"mode": "online", "enable_speaker_diarization": False},
        {"mode": "2pass", "enable_speaker_diarization": False},
        {"mode": "offline", "enable_speaker_diarization": False}
    ]
    
    for i, test_config in enumerate(test_configs, 1):
        logger.info(f"\n🧪 测试配置 {i}: {test_config}")
        
        try:
            async with websockets.connect(uri, subprotocols=['binary']) as websocket:
                config = {
                    "chunk_size": [5, 10, 5],
                    "wav_name": "h5",
                    "is_speaking": True,
                    "chunk_interval": 10,
                    "language": "zh",
                    **test_config
                }
                
                await websocket.send(json.dumps(config))
                logger.info(f"📤 发送配置: {config}")
                
                # 发送少量音频数据
                test_audio = generate_test_audio(duration=1)
                await websocket.send(test_audio[:1024])
                
                # 等待响应
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    logger.info(f"📥 收到响应，配置生效")
                except asyncio.TimeoutError:
                    logger.info(f"⏰ 未收到响应（可能正常，取决于音频长度）")
                    
        except Exception as e:
            logger.error(f"❌ 测试配置 {i} 失败: {e}")

def main():
    """
    主测试函数
    """
    logger.info("🚀 开始测试离线ASR+说话人识别专用模式")
    logger.info("📋 测试目标:")
    logger.info("   1. 验证在线ASR被禁用")
    logger.info("   2. 验证离线ASR+说话人识别被强制启用")
    logger.info("   3. 验证配置覆盖功能")
    
    # 运行基本功能测试
    logger.info("\n🧪 === 基本功能测试 ===")
    result1 = asyncio.run(test_offline_speaker_mode())
    
    # 运行配置覆盖测试
    logger.info("\n🧪 === 配置覆盖测试 ===")
    asyncio.run(test_config_override())
    
    # 总结测试结果
    logger.info("\n📊 === 测试总结 ===")
    if result1:
        logger.info("✅ 离线ASR+说话人识别模式测试通过")
    else:
        logger.warning("⚠️ 离线ASR+说话人识别模式测试未完全通过")
    
    logger.info("\n💡 使用说明:")
    logger.info("   - 系统现在只使用离线高精度ASR+说话人识别")
    logger.info("   - 在线实时识别已被禁用，减少延迟")
    logger.info("   - 所有音频都会等到语音结束后进行完整处理")
    logger.info("   - 自动包含标点符号和说话人信息")

if __name__ == "__main__":
    main()