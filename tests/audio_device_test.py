#!/usr/bin/env python3
"""
音频设备诊断和测试工具
帮助诊断和选择正确的音频输入设备
"""

import pyaudio
import numpy as np
import time
import threading
import queue

class AudioDeviceTester:
    def __init__(self):
        self.audio = None
        self.stream = None
        self.is_recording = False
        self.audio_queue = queue.Queue()
        
    def list_audio_devices(self):
        """列出所有音频设备"""
        self.audio = pyaudio.PyAudio()
        
        print("🎤 所有音频设备列表:")
        print("=" * 80)
        
        device_count = self.audio.get_device_count()
        input_devices = []
        
        for i in range(device_count):
            try:
                info = self.audio.get_device_info_by_index(i)
                print(f"设备 {i}:")
                print(f"  名称: {info['name']}")
                print(f"  输入通道: {info['maxInputChannels']}")
                print(f"  输出通道: {info['maxOutputChannels']}")
                print(f"  默认采样率: {info['defaultSampleRate']}Hz")
                print(f"  主机API: {self.audio.get_host_api_info_by_index(info['hostApi'])['name']}")
                
                if info['maxInputChannels'] > 0:
                    input_devices.append(i)
                    print(f"  ✅ 可用作输入设备")
                else:
                    print(f"  ❌ 不支持音频输入")
                print()
            except Exception as e:
                print(f"  ❌ 获取设备信息失败: {e}")
                print()
        
        # 显示默认设备
        try:
            default_input = self.audio.get_default_input_device_info()
            print(f"🎯 默认输入设备: {default_input['name']} (设备 {default_input['index']})")
        except Exception as e:
            print(f"❌ 无法获取默认输入设备: {e}")
        
        try:
            default_output = self.audio.get_default_output_device_info()
            print(f"🔊 默认输出设备: {default_output['name']} (设备 {default_output['index']})")
        except Exception as e:
            print(f"❌ 无法获取默认输出设备: {e}")
        
        print(f"\n📊 总共找到 {len(input_devices)} 个可用的输入设备")
        return input_devices
    
    def test_device_formats(self, device_id: int):
        """测试设备支持的音频格式"""
        print(f"\n🔍 测试设备 {device_id} 的音频格式支持:")
        print("-" * 50)
        
        device_info = self.audio.get_device_info_by_index(device_id)
        print(f"设备名称: {device_info['name']}")
        
        # 测试不同的采样率
        sample_rates = [8000, 16000, 22050, 44100, 48000]
        formats = [
            (pyaudio.paInt16, "16-bit PCM"),
            (pyaudio.paInt24, "24-bit PCM"),
            (pyaudio.paInt32, "32-bit PCM"),
            (pyaudio.paFloat32, "32-bit Float")
        ]
        channels = [1, 2]
        
        supported_configs = []
        
        for rate in sample_rates:
            for format_val, format_name in formats:
                for ch in channels:
                    try:
                        if self.audio.is_format_supported(
                            rate=rate,
                            input_device=device_id,
                            input_channels=ch,
                            input_format=format_val
                        ):
                            config = f"{rate}Hz, {format_name}, {ch}通道"
                            supported_configs.append((rate, format_val, ch, config))
                            print(f"  ✅ {config}")
                    except Exception:
                        pass
        
        if not supported_configs:
            print("  ❌ 未找到支持的音频格式")
        else:
            print(f"\n📊 总共支持 {len(supported_configs)} 种音频格式")
        
        return supported_configs
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """音频回调函数"""
        if self.is_recording:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    def test_device_recording(self, device_id: int, duration: float = 3.0):
        """测试设备录音功能"""
        print(f"\n🎤 测试设备 {device_id} 的录音功能 ({duration}秒):")
        print("-" * 50)
        
        device_info = self.audio.get_device_info_by_index(device_id)
        print(f"设备名称: {device_info['name']}")
        
        # 使用16kHz, 16-bit, 单声道（FunASR要求的格式）
        sample_rate = 16000
        channels = 1
        format_type = pyaudio.paInt16
        chunk_size = 1600  # 100ms
        
        try:
            # 检查格式支持
            if not self.audio.is_format_supported(
                rate=sample_rate,
                input_device=device_id,
                input_channels=channels,
                input_format=format_type
            ):
                print(f"❌ 设备不支持 {sample_rate}Hz, 16-bit, {channels}通道格式")
                return False
            
            print(f"✅ 设备支持目标格式: {sample_rate}Hz, 16-bit, {channels}通道")
            
            # 开始录音
            self.stream = self.audio.open(
                format=format_type,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=chunk_size,
                stream_callback=self.audio_callback
            )
            
            self.is_recording = True
            self.stream.start_stream()
            
            print(f"🎤 开始录音 {duration} 秒，请说话或制造声音...")
            
            # 收集音频数据并分析
            start_time = time.time()
            audio_chunks = []
            max_amplitude = 0
            total_amplitude = 0
            chunk_count = 0
            
            while time.time() - start_time < duration:
                try:
                    audio_data = self.audio_queue.get(timeout=0.1)
                    audio_chunks.append(audio_data)
                    
                    # 分析音频
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    amplitude = np.abs(audio_array).astype(np.float32)
                    max_amp = np.max(amplitude)
                    avg_amp = np.mean(amplitude)
                    
                    max_amplitude = max(max_amplitude, max_amp)
                    total_amplitude += avg_amp
                    chunk_count += 1
                    
                    # 实时显示音频级别
                    if chunk_count % 10 == 0:  # 每秒显示一次
                        level_bar = "█" * min(20, int(max_amp / 1000))
                        print(f"🔊 音频级别: {max_amp:6.0f} |{level_bar:<20}|")
                    
                except queue.Empty:
                    continue
            
            # 停止录音
            self.is_recording = False
            self.stream.stop_stream()
            self.stream.close()
            
            # 分析结果
            avg_amplitude = total_amplitude / max(1, chunk_count)
            
            print(f"\n📊 录音分析结果:")
            print(f"  录音时长: {duration:.1f} 秒")
            print(f"  音频块数: {chunk_count}")
            print(f"  最大振幅: {max_amplitude:.0f}")
            print(f"  平均振幅: {avg_amplitude:.0f}")
            
            if max_amplitude > 1000:
                print(f"  ✅ 检测到音频信号，设备工作正常")
                return True
            elif max_amplitude > 100:
                print(f"  ⚠️ 检测到微弱音频信号，可能需要调整音量")
                return True
            else:
                print(f"  ❌ 未检测到音频信号，设备可能有问题")
                return False
                
        except Exception as e:
            print(f"❌ 录音测试失败: {e}")
            return False
    
    def interactive_device_test(self):
        """交互式设备测试"""
        print("🎤 音频设备交互式测试")
        print("=" * 60)
        
        # 列出设备
        input_devices = self.list_audio_devices()
        
        if not input_devices:
            print("❌ 未找到可用的音频输入设备")
            return
        
        while True:
            print("\n请选择要测试的设备:")
            for device_id in input_devices:
                device_info = self.audio.get_device_info_by_index(device_id)
                print(f"  {device_id}: {device_info['name']}")
            
            print("  q: 退出")
            
            choice = input("\n请输入设备编号: ").strip()
            
            if choice.lower() == 'q':
                break
            
            try:
                device_id = int(choice)
                if device_id not in input_devices:
                    print(f"❌ 无效的设备编号: {device_id}")
                    continue
                
                # 测试格式支持
                self.test_device_formats(device_id)
                
                # 测试录音
                self.test_device_recording(device_id)
                
            except ValueError:
                print("❌ 请输入有效的数字")
            except Exception as e:
                print(f"❌ 测试过程中出错: {e}")
    
    def cleanup(self):
        """清理资源"""
        if self.stream:
            self.stream.close()
        if self.audio:
            self.audio.terminate()

def main():
    """主函数"""
    tester = AudioDeviceTester()
    
    try:
        tester.interactive_device_test()
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
    finally:
        tester.cleanup()
        print("\n👋 测试结束")

if __name__ == "__main__":
    main()