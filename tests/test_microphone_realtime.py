#!/usr/bin/env python3
"""
实时话筒语音转写测试
从话筒获取音频数据并实时发送给FunASR WebSocket服务器进行语音识别
"""

import asyncio
import websockets
import json
import pyaudio
import threading
import time
from typing import Optional
import queue
import signal
import sys

class MicrophoneRealtimeASR:
    def __init__(self, server_url: str = "ws://localhost:10095"):
        self.server_url = server_url
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.is_recording = False
        self.audio_queue = queue.Queue()
        
        # 音频参数
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = 1600  # 100ms at 16kHz
        self.format = pyaudio.paInt16
        
        # PyAudio对象
        self.audio = None
        self.stream = None
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """处理Ctrl+C信号"""
        print("\n⚠️ 收到中断信号，正在停止录音...")
        self.stop_recording()
        sys.exit(0)
    
    def init_audio(self) -> bool:
        """初始化音频设备"""
        try:
            self.audio = pyaudio.PyAudio()
            
            # 检查可用的音频设备
            print("🎤 可用的音频输入设备:")
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    print(f"  设备 {i}: {info['name']} (输入通道: {info['maxInputChannels']})")
            
            # 获取默认输入设备
            default_device = self.audio.get_default_input_device_info()
            print(f"\n🎯 使用默认输入设备: {default_device['name']}")
            
            return True
        except Exception as e:
            print(f"❌ 初始化音频设备失败: {e}")
            return False
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """音频回调函数"""
        if self.is_recording:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    def start_recording(self) -> bool:
        """开始录音"""
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self.audio_callback
            )
            
            self.is_recording = True
            self.stream.start_stream()
            print("🎤 开始录音...")
            return True
        except Exception as e:
            print(f"❌ 开始录音失败: {e}")
            return False
    
    def stop_recording(self):
        """停止录音"""
        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            print("🛑 录音已停止")
        if self.audio:
            self.audio.terminate()
    
    async def connect_websocket(self) -> bool:
        """连接到WebSocket服务器"""
        try:
            print(f"🔄 正在连接到服务器: {self.server_url}")
            self.websocket = await websockets.connect(
                self.server_url,
                subprotocols=["binary"]
            )
            self.is_connected = True
            print("✅ WebSocket连接成功!")
            return True
        except Exception as e:
            print(f"❌ WebSocket连接失败: {e}")
            return False
    
    async def disconnect_websocket(self):
        """断开WebSocket连接"""
        if self.websocket and self.is_connected:
            await self.websocket.close()
            self.is_connected = False
            print("🔌 WebSocket连接已断开")
    
    async def send_config(self, mode: str = "online") -> bool:
        """发送配置信息"""
        try:
            config = {
                "type": "init",
                "mode": mode,
                "language": "zh",
                "sample_rate": self.sample_rate,
                "chunk_size": self.chunk_size,
                "enable_vad": True,
                "enable_punc": True,
                "vad_threshold": 0.3
            }
            
            print(f"📤 发送{mode}模式配置...")
            await self.websocket.send(json.dumps(config))
            print(f"✅ 配置已发送")
            return True
        except Exception as e:
            print(f"❌ 发送配置失败: {e}")
            return False
    
    async def send_audio_data(self):
        """发送音频数据到服务器"""
        print("📡 开始发送音频数据...")
        audio_count = 0
        
        try:
            while self.is_recording and self.is_connected:
                try:
                    # 从队列获取音频数据（非阻塞）
                    audio_data = self.audio_queue.get_nowait()
                    await self.websocket.send(audio_data)
                    audio_count += 1
                    
                    if audio_count % 10 == 0:  # 每秒显示一次
                        print(f"📤 已发送 {audio_count} 个音频块")
                    
                except queue.Empty:
                    # 队列为空，稍等片刻
                    await asyncio.sleep(0.01)
                except Exception as e:
                    print(f"❌ 发送音频数据失败: {e}")
                    break
        except Exception as e:
            print(f"❌ 音频发送过程出错: {e}")
        
        print(f"📊 总共发送了 {audio_count} 个音频块")
    
    async def listen_responses(self):
        """监听服务器响应"""
        print("👂 开始监听服务器响应...")
        response_count = 0
        
        try:
            while self.is_connected:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    response_count += 1
                    
                    if isinstance(response, str):
                        try:
                            result = json.loads(response)
                            print(f"\n📥 收到响应 #{response_count}:")
                            
                            # 解析识别结果
                            if "text" in result and result["text"]:
                                print(f"🗣️ 识别文本: '{result['text']}'")
                            if "vad" in result:
                                vad_status = "🟢 检测到语音" if result["vad"] else "🔴 静音"
                                print(f"🎤 VAD状态: {vad_status}")
                            if "timestamp" in result:
                                print(f"⏰ 时间戳: {result['timestamp']}")
                            if "mode" in result:
                                print(f"🔧 识别模式: {result['mode']}")
                            if "is_final" in result:
                                final_status = "✅ 最终结果" if result["is_final"] else "⏳ 临时结果"
                                print(f"📋 结果状态: {final_status}")
                            
                            print()  # 空行分隔
                            
                        except json.JSONDecodeError:
                            print(f"📥 收到非JSON响应: {response}")
                    else:
                        print(f"📥 收到二进制响应，长度: {len(response)} 字节")
                        
                except asyncio.TimeoutError:
                    # 超时是正常的，继续监听
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("⚠️ WebSocket连接已关闭")
                    break
                except Exception as e:
                    print(f"❌ 接收响应时出错: {e}")
                    break
                    
        except Exception as e:
            print(f"❌ 监听响应过程出错: {e}")
        
        print(f"📊 总共收到 {response_count} 个响应")
    
    async def send_end_signal(self):
        """发送结束信号"""
        try:
            end_signal = {"type": "end"}
            await self.websocket.send(json.dumps(end_signal))
            print("📤 已发送结束信号")
        except Exception as e:
            print(f"❌ 发送结束信号失败: {e}")
    
    async def run_realtime_asr(self, mode: str = "online", duration: Optional[float] = None):
        """运行实时语音识别"""
        print(f"\n🎯 开始实时话筒语音转写 (模式: {mode})")
        print("=" * 60)
        
        # 初始化音频设备
        if not self.init_audio():
            return False
        
        # 连接WebSocket服务器
        if not await self.connect_websocket():
            return False
        
        try:
            # 发送配置
            if not await self.send_config(mode):
                return False
            
            # 开始录音
            if not self.start_recording():
                return False
            
            print("\n🎤 正在录音，请开始说话...")
            if duration:
                print(f"⏰ 录音时长: {duration}秒")
            else:
                print("⏰ 按 Ctrl+C 停止录音")
            
            # 创建并发任务
            send_task = asyncio.create_task(self.send_audio_data())
            listen_task = asyncio.create_task(self.listen_responses())
            
            # 如果指定了时长，则定时停止
            if duration:
                await asyncio.sleep(duration)
                self.stop_recording()
            else:
                # 等待用户中断
                try:
                    await asyncio.gather(send_task, listen_task)
                except KeyboardInterrupt:
                    print("\n⚠️ 用户中断录音")
                    self.stop_recording()
            
            # 等待任务完成
            await asyncio.sleep(1)
            
            # 发送结束信号
            await self.send_end_signal()
            
            # 等待最终响应
            print("⏳ 等待最终响应...")
            await asyncio.sleep(3)
            
            # 取消任务
            send_task.cancel()
            listen_task.cancel()
            
            print("✅ 实时语音转写完成")
            return True
            
        except Exception as e:
            print(f"❌ 实时语音转写过程中出错: {e}")
            return False
        finally:
            self.stop_recording()
            await self.disconnect_websocket()
    
    async def test_microphone(self):
        """测试麦克风功能"""
        print("🎤 麦克风测试")
        print("=" * 40)
        
        if not self.init_audio():
            return False
        
        print("🎤 开始5秒钟麦克风测试...")
        if not self.start_recording():
            return False
        
        # 记录5秒钟的音频
        start_time = time.time()
        audio_data_count = 0
        
        while time.time() - start_time < 5.0:
            try:
                self.audio_queue.get_nowait()
                audio_data_count += 1
            except queue.Empty:
                await asyncio.sleep(0.01)
        
        self.stop_recording()
        
        print(f"✅ 麦克风测试完成，收到 {audio_data_count} 个音频块")
        if audio_data_count > 0:
            print("🎉 麦克风工作正常！")
            return True
        else:
            print("❌ 麦克风可能有问题，未收到音频数据")
            return False

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="实时话筒语音转写测试")
    parser.add_argument("--server", default="ws://localhost:10095", help="WebSocket服务器地址")
    parser.add_argument("--mode", choices=["online", "offline", "2pass"], default="online", help="识别模式")
    parser.add_argument("--duration", type=float, help="录音时长（秒），不指定则手动停止")
    parser.add_argument("--test-mic", action="store_true", help="仅测试麦克风功能")
    
    args = parser.parse_args()
    
    # 检查PyAudio是否可用
    try:
        import pyaudio
    except ImportError:
        print("❌ 缺少pyaudio库，请安装: pip install pyaudio")
        return
    
    # 创建实时语音转写器
    asr = MicrophoneRealtimeASR(args.server)
    
    if args.test_mic:
        # 仅测试麦克风
        await asr.test_microphone()
    else:
        # 运行实时语音转写
        print("🚀 FunASR 实时话筒语音转写")
        print("=" * 60)
        print(f"🌐 服务器地址: {args.server}")
        print(f"🔧 识别模式: {args.mode}")
        print(f"⏰ 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        await asr.run_realtime_asr(args.mode, args.duration)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")