#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
说话人WebSocket接口测试
测试通过WebSocket进行说话人注册、识别、验证等功能
"""

import asyncio
import websockets
import json
import base64
import logging
import os
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpeakerWebSocketTester:
    def __init__(self, server_url="ws://localhost:10095"):
        self.server_url = server_url
        self.websocket = None
        
    async def connect(self):
        """连接到WebSocket服务器"""
        try:
            self.websocket = await websockets.connect(
                self.server_url,
                subprotocols=["binary"]
            )
            logger.info(f"✅ 已连接到服务器: {self.server_url}")
            return True
        except Exception as e:
            logger.error(f"❌ 连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开WebSocket连接"""
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 已断开连接")
    
    async def send_message(self, message):
        """发送消息并接收响应"""
        if not self.websocket:
            raise Exception("WebSocket未连接")
        
        await self.websocket.send(json.dumps(message, ensure_ascii=False))
        response = await self.websocket.recv()
        return json.loads(response)
    
    def load_audio_file(self, file_path):
        """加载音频文件并转换为base64"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"音频文件不存在: {file_path}")
        
        with open(file_path, 'rb') as f:
            audio_data = f.read()
        
        return base64.b64encode(audio_data).decode('utf-8')
    
    async def test_speaker_register(self, speaker_name, audio_file, description="", overwrite=False):
        """测试说话人注册"""
        logger.info(f"🔄 测试说话人注册: {speaker_name}")
        
        try:
            audio_data = self.load_audio_file(audio_file)
            
            message = {
                "action": "speaker_register",
                "speaker_name": speaker_name,
                "audio_data": audio_data,
                "description": description,
                "overwrite": overwrite
            }
            
            response = await self.send_message(message)
            
            if response.get("success"):
                logger.info(f"✅ 注册成功: {response.get('message')}")
            else:
                logger.error(f"❌ 注册失败: {response.get('message')}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ 注册测试失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def test_speaker_identify(self, audio_file, top_k=3):
        """测试说话人识别"""
        logger.info("🔄 测试说话人识别")
        
        try:
            audio_data = self.load_audio_file(audio_file)
            
            message = {
                "action": "speaker_identify",
                "audio_data": audio_data,
                "top_k": top_k
            }
            
            response = await self.send_message(message)
            
            if response.get("success"):
                best_match = response.get("best_match")
                if best_match:
                    logger.info(f"✅ 识别成功: {best_match['speaker_name']} (相似度: {best_match['similarity']:.4f})")
                else:
                    logger.info("✅ 识别完成，但未找到匹配的说话人")
                
                candidates = response.get("candidates", [])
                logger.info(f"📊 候选人数量: {len(candidates)}")
                for i, candidate in enumerate(candidates[:3]):
                    logger.info(f"  {i+1}. {candidate['speaker_name']}: {candidate['similarity']:.4f}")
            else:
                logger.error(f"❌ 识别失败: {response.get('message')}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ 识别测试失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def test_speaker_verify(self, speaker_name, audio_file):
        """测试说话人验证"""
        logger.info(f"🔄 测试说话人验证: {speaker_name}")
        
        try:
            audio_data = self.load_audio_file(audio_file)
            
            message = {
                "action": "speaker_verify",
                "speaker_name": speaker_name,
                "audio_data": audio_data
            }
            
            response = await self.send_message(message)
            
            if response.get("success"):
                is_verified = response.get("is_verified")
                similarity = response.get("similarity", 0.0)
                
                if is_verified:
                    logger.info(f"✅ 验证成功: {speaker_name} (相似度: {similarity:.4f})")
                else:
                    logger.info(f"❌ 验证失败: 不是 {speaker_name} (相似度: {similarity:.4f})")
            else:
                logger.error(f"❌ 验证失败: {response.get('message')}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ 验证测试失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def test_speaker_list(self):
        """测试获取说话人列表"""
        logger.info("🔄 测试获取说话人列表")
        
        try:
            message = {
                "action": "speaker_list"
            }
            
            response = await self.send_message(message)
            
            if response.get("success"):
                speakers = response.get("speakers", [])
                total_count = response.get("total_count", 0)
                
                logger.info(f"✅ 获取成功，共 {total_count} 个说话人:")
                for speaker in speakers:
                    logger.info(f"  - {speaker.get('speaker_name')}: {speaker.get('description')}")
            else:
                logger.error(f"❌ 获取失败: {response.get('message')}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ 列表测试失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def test_speaker_info(self, speaker_name):
        """测试获取说话人信息"""
        logger.info(f"🔄 测试获取说话人信息: {speaker_name}")
        
        try:
            message = {
                "action": "speaker_info",
                "speaker_name": speaker_name
            }
            
            response = await self.send_message(message)
            
            if response.get("success"):
                speaker_info = response.get("speaker_info")
                logger.info(f"✅ 获取成功:")
                logger.info(f"  ID: {speaker_info.get('speaker_id')}")
                logger.info(f"  姓名: {speaker_info.get('speaker_name')}")
                logger.info(f"  描述: {speaker_info.get('description')}")
                logger.info(f"  注册时间: {speaker_info.get('registration_time')}")
                logger.info(f"  音频样本数: {speaker_info.get('audio_samples')}")
            else:
                logger.error(f"❌ 获取失败: {response.get('message')}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ 信息测试失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def test_speaker_delete(self, speaker_name):
        """测试删除说话人"""
        logger.info(f"🔄 测试删除说话人: {speaker_name}")
        
        try:
            message = {
                "action": "speaker_delete",
                "speaker_name": speaker_name
            }
            
            response = await self.send_message(message)
            
            if response.get("success"):
                logger.info(f"✅ 删除成功: {response.get('message')}")
            else:
                logger.error(f"❌ 删除失败: {response.get('message')}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ 删除测试失败: {e}")
            return {"success": False, "message": str(e)}


async def run_comprehensive_test():
    """运行综合测试"""
    logger.info("🚀 开始说话人WebSocket接口综合测试")
    
    tester = SpeakerWebSocketTester()
    
    # 连接到服务器
    if not await tester.connect():
        logger.error("❌ 无法连接到服务器，测试终止")
        return
    
    try:
        # 注意：这里需要实际的音频文件路径
        # 你需要准备一些测试音频文件
        test_audio_dir = Path("test_audio")
        
        if not test_audio_dir.exists():
            logger.warning("⚠️  测试音频目录不存在，创建示例测试...")
            
            # 测试获取空列表
            await tester.test_speaker_list()
            
            # 测试获取不存在的说话人信息
            await tester.test_speaker_info("不存在的说话人")
            
            # 测试删除不存在的说话人
            await tester.test_speaker_delete("不存在的说话人")
            
        else:
            # 如果有测试音频文件，运行完整测试
            audio_files = list(test_audio_dir.glob("*.wav"))
            
            if len(audio_files) >= 2:
                # 注册第一个说话人
                await tester.test_speaker_register(
                    "张三", 
                    str(audio_files[0]), 
                    "测试说话人1"
                )
                
                # 注册第二个说话人
                await tester.test_speaker_register(
                    "李四", 
                    str(audio_files[1]), 
                    "测试说话人2"
                )
                
                # 获取说话人列表
                await tester.test_speaker_list()
                
                # 获取说话人信息
                await tester.test_speaker_info("张三")
                
                # 识别说话人
                await tester.test_speaker_identify(str(audio_files[0]))
                
                # 验证说话人
                await tester.test_speaker_verify("张三", str(audio_files[0]))
                await tester.test_speaker_verify("李四", str(audio_files[0]))  # 应该验证失败
                
                # 删除说话人
                await tester.test_speaker_delete("张三")
                await tester.test_speaker_delete("李四")
                
                # 再次获取列表确认删除
                await tester.test_speaker_list()
            
            else:
                logger.warning("⚠️  测试音频文件不足，需要至少2个.wav文件")
    
    except Exception as e:
        logger.error(f"❌ 测试过程中出错: {e}")
    
    finally:
        await tester.disconnect()
    
    logger.info("🏁 测试完成")


if __name__ == "__main__":
    # 创建测试音频目录提示
    test_audio_dir = Path("test_audio")
    if not test_audio_dir.exists():
        print("📁 请在当前目录创建 'test_audio' 文件夹，并放入测试用的.wav音频文件")
        print("   例如: test_audio/speaker1.wav, test_audio/speaker2.wav")
        print("   音频文件应该包含不同说话人的语音")
        print()
    
    # 运行测试
    asyncio.run(run_comprehensive_test())