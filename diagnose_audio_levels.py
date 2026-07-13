#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断音频设备的电平和质量"""

import pyaudio
import numpy as np
import time
import sys

def diagnose_audio_levels(device_index, duration=5):
    """
    诊断音频设备的电平和质量
    
    Args:
        device_index: 设备索引
        duration: 测试时长（秒）
    """
    print(f"\n{'='*70}")
    print(f"音频设备诊断 - 设备 {device_index}")
    print(f"{'='*70}\n")
    
    p = pyaudio.PyAudio()
    
    try:
        # 获取设备信息
        device_info = p.get_device_info_by_index(device_index)
        print(f"📱 设备名称: {device_info['name']}")
        print(f"📊 输入声道: {device_info['maxInputChannels']}")
        print(f"🎵 默认采样率: {int(device_info['defaultSampleRate'])}Hz")
        print(f"⚙️  主机API: {p.get_host_api_info_by_index(device_info['hostApi'])['name']}")
        print()
        
        if device_info['maxInputChannels'] == 0:
            print("❌ 错误: 此设备不支持音频输入")
            return
        
        # 打开音频流
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=960
        )
        
        print(f"🎤 开始录音 {duration} 秒...")
        print("请对着麦克风说话以测试音频质量！")
        print()
        
        start_time = time.time()
        all_levels = []
        all_zcr = []
        all_samples = []
        
        while time.time() - start_time < duration:
            # 读取音频数据
            audio_data = stream.read(960, exception_on_overflow=False)
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            all_samples.extend(audio_array)
            
            # 计算音频电平 (RMS)
            rms = np.sqrt(np.mean(audio_array**2))
            if rms > 0:
                db = 20 * np.log10(rms)
            else:
                db = -100
            
            all_levels.append(db)
            
            # 计算零交叉率 (Zero Crossing Rate)
            zcr = np.sum(np.abs(np.diff(np.sign(audio_array)))) / (2 * len(audio_array))
            all_zcr.append(zcr)
            
            # 显示实时电平
            bars = int((db + 60) / 3)  # -60dB 到 0dB 映射到 0-20 个字符
            bars = max(0, min(20, bars))
            bar_str = '█' * bars + '░' * (20 - bars)
            
            elapsed = time.time() - start_time
            print(f"\r[{elapsed:4.1f}s] 电平: {bar_str} {db:6.1f} dB | ZCR: {zcr:.3f}", 
                  end='', flush=True)
            
        print("\n")
        
        # 关闭流
        stream.stop_stream()
        stream.close()
        
        # 统计分析
        levels = np.array(all_levels)
        zcr_values = np.array(all_zcr)
        samples = np.array(all_samples)
        
        avg_level = np.mean(levels)
        max_level = np.max(levels)
        min_level = np.min(levels)
        std_level = np.std(levels)
        
        avg_zcr = np.mean(zcr_values)
        
        # 计算信噪比估计
        # 假设最低的20%电平是噪音
        sorted_levels = np.sort(levels)
        noise_floor = np.mean(sorted_levels[:len(sorted_levels)//5])
        snr = avg_level - noise_floor
        
        # 计算削波率
        max_amplitude = np.max(np.abs(samples))
        clipping_threshold = 32767 * 0.95  # 95% of max int16
        clipping_rate = np.sum(np.abs(samples) > clipping_threshold) / len(samples) * 100
        
        print(f"\n{'='*70}")
        print("📊 详细音频分析")
        print(f"{'='*70}")
        print(f"\n🔊 电平统计:")
        print(f"  平均电平: {avg_level:6.1f} dB")
        print(f"  峰值电平: {max_level:6.1f} dB")
        print(f"  最低电平: {min_level:6.1f} dB")
        print(f"  标准差:   {std_level:6.1f} dB")
        print(f"  噪音底限: {noise_floor:6.1f} dB")
        print(f"  信噪比:   {snr:6.1f} dB")
        
        print(f"\n🎵 音频特征:")
        print(f"  平均零交叉率: {avg_zcr:.3f}")
        print(f"  最大振幅:     {max_amplitude} / 32767")
        print(f"  削波率:       {clipping_rate:.2f}%")
        
        print(f"\n{'='*70}")
        print("💡 诊断结果")
        print(f"{'='*70}")
        
        # 评估音频质量
        issues = []
        recommendations = []
        
        # 检查电平
        if avg_level < -40:
            issues.append("❌ 音量太低")
            recommendations.append("• 提高麦克风音量（系统设置 > 声音 > 输入）")
        elif avg_level < -30:
            issues.append("⚠️  音量偏低")
            recommendations.append("• 建议适当提高麦克风音量")
        elif avg_level > -10:
            issues.append("⚠️  音量过高")
            recommendations.append("• 降低麦克风音量以避免削波")
        else:
            print("✅ 音量水平: 良好 (-30dB 到 -10dB)")
        
        # 检查信噪比
        if snr < 10:
            issues.append("❌ 信噪比太低")
            recommendations.append("• 在更安静的环境中测试")
            recommendations.append("• 检查是否使用了正确的麦克风设备")
        elif snr < 20:
            issues.append("⚠️  信噪比偏低")
            recommendations.append("• 建议减少环境噪音")
        else:
            print(f"✅ 信噪比: 良好 ({snr:.1f} dB)")
        
        # 检查削波
        if clipping_rate > 1:
            issues.append("❌ 音频削波严重")
            recommendations.append("• 降低麦克风音量")
        elif clipping_rate > 0.1:
            issues.append("⚠️  检测到轻微削波")
            recommendations.append("• 建议稍微降低麦克风音量")
        else:
            print("✅ 削波检测: 无削波")
        
        # 检查零交叉率
        if avg_zcr < 0.05:
            issues.append("⚠️  零交叉率过低")
            recommendations.append("• 可能是静音或音量太低")
        elif avg_zcr > 0.5:
            issues.append("⚠️  零交叉率过高")
            recommendations.append("• 可能是噪音或设备问题")
        else:
            print(f"✅ 零交叉率: 正常 ({avg_zcr:.3f})")
        
        # 输出问题和建议
        if issues:
            print(f"\n⚠️  发现的问题:")
            for issue in issues:
                print(f"  {issue}")
        
        if recommendations:
            print(f"\n💡 建议:")
            for rec in recommendations:
                print(f"  {rec}")
        
        if not issues:
            print("\n✅ 音频质量优秀，适合语音识别！")
        
        print(f"\n{'='*70}\n")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        p.terminate()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python diagnose_audio_levels.py <device_index> [duration]")
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
    
    diagnose_audio_levels(device_index, duration)
