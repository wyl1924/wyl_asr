#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""比较和录制不同音频源的质量"""

import pyaudio
import wave
import numpy as np
import time
import sys
from datetime import datetime

def record_and_analyze(device_index, duration=5):
    """
    录制音频并分析质量
    
    Args:
        device_index: 设备索引
        duration: 录制时长（秒）
    """
    print(f"\n{'='*70}")
    print(f"音频录制与分析 - 设备 {device_index}")
    print(f"{'='*70}\n")
    
    p = pyaudio.PyAudio()
    
    try:
        # 获取设备信息
        device_info = p.get_device_info_by_index(device_index)
        print(f"📱 设备名称: {device_info['name']}")
        print(f"📊 输入声道: {device_info['maxInputChannels']}")
        print(f"🎵 采样率: 16000 Hz")
        print(f"🎚️  格式: 16-bit PCM")
        print()
        
        if device_info['maxInputChannels'] == 0:
            print("❌ 错误: 此设备不支持音频输入")
            return
        
        # 配置音频参数
        CHUNK = 960
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        # 打开音频流
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK
        )
        
        print(f"🎤 开始录音 {duration} 秒...")
        print("请对着麦克风清晰地说话！")
        print()
        
        frames = []
        levels = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # 读取音频数据
            audio_data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(audio_data)
            
            # 计算实时电平
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_array**2))
            if rms > 0:
                db = 20 * np.log10(rms)
            else:
                db = -100
            
            levels.append(db)
            
            # 显示进度
            elapsed = time.time() - start_time
            bars = int((db + 60) / 3)
            bars = max(0, min(20, bars))
            bar_str = '█' * bars + '░' * (20 - bars)
            print(f"\r[{elapsed:4.1f}s] {bar_str} {db:6.1f} dB", end='', flush=True)
        
        print("\n")
        
        # 关闭流
        stream.stop_stream()
        stream.close()
        
        # 保存录音文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_recording_device{device_index}_{timestamp}.wav"
        
        wf = wave.open(filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        print(f"💾 录音已保存: {filename}")
        print()
        
        # 分析录音质量
        all_samples = np.frombuffer(b''.join(frames), dtype=np.int16)
        levels = np.array(levels)
        
        avg_level = np.mean(levels)
        max_level = np.max(levels)
        min_level = np.min(levels)
        
        # 计算动态范围
        dynamic_range = max_level - min_level
        
        # 计算有效语音段（电平高于阈值）
        speech_threshold = avg_level - 10  # 平均电平以下10dB作为阈值
        speech_ratio = np.sum(levels > speech_threshold) / len(levels) * 100
        
        # 计算频谱特征
        fft = np.fft.rfft(all_samples)
        freqs = np.fft.rfftfreq(len(all_samples), 1/RATE)
        magnitude = np.abs(fft)
        
        # 找到主要频率成分
        peak_freq_idx = np.argmax(magnitude[1:]) + 1  # 跳过DC分量
        peak_freq = freqs[peak_freq_idx]
        
        # 计算能量分布
        low_freq_energy = np.sum(magnitude[freqs < 500])
        mid_freq_energy = np.sum(magnitude[(freqs >= 500) & (freqs < 2000)])
        high_freq_energy = np.sum(magnitude[freqs >= 2000])
        total_energy = low_freq_energy + mid_freq_energy + high_freq_energy
        
        print(f"{'='*70}")
        print("📊 录音质量分析")
        print(f"{'='*70}")
        
        print(f"\n🔊 电平分析:")
        print(f"  平均电平:   {avg_level:6.1f} dB")
        print(f"  峰值电平:   {max_level:6.1f} dB")
        print(f"  最低电平:   {min_level:6.1f} dB")
        print(f"  动态范围:   {dynamic_range:6.1f} dB")
        print(f"  语音占比:   {speech_ratio:5.1f}%")
        
        print(f"\n🎵 频谱分析:")
        print(f"  主频率:     {peak_freq:6.1f} Hz")
        print(f"  低频能量:   {low_freq_energy/total_energy*100:5.1f}% (< 500 Hz)")
        print(f"  中频能量:   {mid_freq_energy/total_energy*100:5.1f}% (500-2000 Hz)")
        print(f"  高频能量:   {high_freq_energy/total_energy*100:5.1f}% (> 2000 Hz)")
        
        print(f"\n{'='*70}")
        print("💡 质量评估")
        print(f"{'='*70}")
        
        # 综合评估
        score = 0
        issues = []
        
        # 电平评分
        if -30 <= avg_level <= -10:
            score += 30
            print("✅ 电平: 优秀")
        elif -40 <= avg_level < -30 or -10 < avg_level <= 0:
            score += 20
            print("⚠️  电平: 可接受")
            if avg_level < -30:
                issues.append("音量偏低")
            else:
                issues.append("音量偏高")
        else:
            score += 10
            print("❌ 电平: 不佳")
            if avg_level < -40:
                issues.append("音量太低")
            else:
                issues.append("音量过高，可能削波")
        
        # 动态范围评分
        if dynamic_range > 20:
            score += 25
            print("✅ 动态范围: 良好")
        elif dynamic_range > 10:
            score += 15
            print("⚠️  动态范围: 一般")
        else:
            score += 5
            print("❌ 动态范围: 不足")
            issues.append("动态范围太小，可能是静音或噪音")
        
        # 语音占比评分
        if speech_ratio > 30:
            score += 25
            print("✅ 语音检测: 良好")
        elif speech_ratio > 10:
            score += 15
            print("⚠️  语音检测: 一般")
        else:
            score += 5
            print("❌ 语音检测: 不足")
            issues.append("检测到的语音太少")
        
        # 频谱评分
        if 0.3 < mid_freq_energy/total_energy < 0.7:
            score += 20
            print("✅ 频谱分布: 正常")
        else:
            score += 10
            print("⚠️  频谱分布: 异常")
            if low_freq_energy/total_energy > 0.5:
                issues.append("低频能量过高，可能是噪音")
            if high_freq_energy/total_energy > 0.5:
                issues.append("高频能量过高，可能是噪音或失真")
        
        print(f"\n📈 总体评分: {score}/100")
        
        if score >= 80:
            print("✅ 音频质量: 优秀 - 非常适合语音识别")
        elif score >= 60:
            print("✅ 音频质量: 良好 - 适合语音识别")
        elif score >= 40:
            print("⚠️  音频质量: 一般 - 可能影响识别准确率")
        else:
            print("❌ 音频质量: 差 - 不适合语音识别")
        
        if issues:
            print(f"\n⚠️  发现的问题:")
            for issue in issues:
                print(f"  • {issue}")
        
        print(f"\n💡 下一步:")
        print(f"  1. 播放录音文件检查质量:")
        print(f"     afplay {filename}")
        print(f"  2. 如果音质不佳，尝试其他音频设备")
        print(f"  3. 调整麦克风音量后重新测试")
        
        print(f"\n{'='*70}\n")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        p.terminate()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python compare_audio_sources.py <device_index> [duration]")
        print("\n可用设备:")
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"  {i}: {info['name']}")
        p.terminate()
        sys.exit(1)
    
    device_index = int(sys.argv[1])
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    record_and_analyze(device_index, duration)
