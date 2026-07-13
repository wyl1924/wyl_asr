#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""智能说话人识别触发器模块

集成WebRTC VAD和语音活动累积器，实现智能的说话人识别触发逻辑。
"""

import logging
import asyncio
from typing import Optional, Callable, Awaitable, Dict
import time

from .webrtc_vad_detector import WebRTCVADDetector, get_webrtc_vad_detector
from .speech_activity_accumulator import SpeechActivityAccumulator, SpeechState

logger = logging.getLogger(__name__)


class SmartSpeakerTrigger:
    """智能说话人识别触发器
    
    整合WebRTC VAD检测和语音活动累积，提供智能的说话人识别触发机制。
    
    工作流程:
    1. 接收音频帧
    2. WebRTC VAD实时检测语音活动
    3. 累积有效语音片段
    4. 根据策略智能触发说话人识别
    
    使用示例:
        trigger = SmartSpeakerTrigger()
        
        async def handle_speaker_recognition(audio_data):
            # 执行说话人识别
            result = await async_asr_with_speaker(...)
            return result
        
        # 处理音频流
        async for audio_chunk in audio_stream:
            await trigger.process_audio_chunk(
                audio_chunk,
                callback=handle_speaker_recognition
            )
    """
    
    def __init__(
        self,
        vad_mode: int = 2,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        trigger_duration_ms: int = 2000,
        max_duration_ms: int = 10000,
        silence_tolerance_ms: int = 500,
        min_speech_ratio: float = 0.6,
        min_trigger_interval_ms: int = 1000,
        enable_funasr_vad_verification: bool = True
    ):
        """初始化智能说话人识别触发器
        
        Args:
            vad_mode: WebRTC VAD灵敏度模式 (0-3)
            sample_rate: 采样率
            frame_duration_ms: 帧长度（毫秒）
            trigger_duration_ms: 触发识别的最小语音时长
            max_duration_ms: 最大累积时长
            silence_tolerance_ms: 静音容忍时间
            min_speech_ratio: 最小语音占比
            min_trigger_interval_ms: 两次触发的最小间隔
            enable_funasr_vad_verification: 是否启用FunASR VAD二次验证
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.enable_funasr_vad_verification = enable_funasr_vad_verification
        
        # 初始化WebRTC VAD检测器
        self.vad_detector = get_webrtc_vad_detector(
            mode=vad_mode,
            sample_rate=sample_rate,
            frame_duration_ms=frame_duration_ms
        )
        
        if self.vad_detector is None:
            logger.warning("⚠️ WebRTC VAD不可用，智能触发器将降级为传统模式")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("✅ WebRTC VAD检测器初始化成功")
        
        # 初始化语音活动累积器
        self.accumulator = SpeechActivityAccumulator(
            trigger_duration_ms=trigger_duration_ms,
            max_duration_ms=max_duration_ms,
            silence_tolerance_ms=silence_tolerance_ms,
            min_speech_ratio=min_speech_ratio,
            min_trigger_interval_ms=min_trigger_interval_ms,
            frame_duration_ms=frame_duration_ms
        )
        
        # 计算每帧的字节数
        self.frame_bytes = int(sample_rate * frame_duration_ms / 1000) * 2
        
        # 统计信息
        self.total_chunks_processed = 0
        self.total_triggers = 0
        self.total_skipped = 0
        
        logger.info(
            f"✅ 智能说话人识别触发器初始化完成: "
            f"enabled={self.enabled}, "
            f"frame_bytes={self.frame_bytes}"
        )
    
    async def process_audio_chunk(
        self,
        audio_chunk: bytes,
        callback: Optional[Callable[[bytes], Awaitable[Dict]]] = None
    ) -> Optional[Dict]:
        """处理音频块，并在满足条件时触发回调
        
        Args:
            audio_chunk: PCM音频数据（16-bit，单声道）
            callback: 触发时的异步回调函数，接收累积的音频数据
        
        Returns:
            Optional[Dict]: 如果触发了识别，返回识别结果；否则返回None
        """
        self.total_chunks_processed += 1
        
        # 如果未启用，直接返回
        if not self.enabled:
            return None
        
        # 将音频块分割为固定长度的帧
        num_frames = len(audio_chunk) // self.frame_bytes
        
        for i in range(num_frames):
            frame_start = i * self.frame_bytes
            frame_end = frame_start + self.frame_bytes
            audio_frame = audio_chunk[frame_start:frame_end]
            
            # WebRTC VAD检测
            is_speech = self.vad_detector.detect_frame(audio_frame)
            
            # 累积语音片段
            self.accumulator.add_frame(audio_frame, is_speech)
            
            # 记录详细日志（每10帧记录一次，避免日志过多）
            if i % 10 == 0:
                logger.debug(
                    f"🎤 VAD检测: frame={i}, is_speech={is_speech}, "
                    f"{self.accumulator.get_debug_info()}"
                )
        
        # 检查是否应该触发识别
        if self.accumulator.should_trigger():
            accumulated_audio = self.accumulator.get_accumulated_audio()
            duration_ms = self.accumulator.get_duration_ms()
            stats = self.accumulator.get_statistics()
            
            logger.info(
                f"🎯 触发说话人识别: "
                f"duration={duration_ms}ms, "
                f"speech_ratio={stats['speech_ratio']:.2f}, "
                f"buffer_size={len(accumulated_audio)}bytes"
            )
            
            # 标记为处理中
            self.accumulator.mark_as_processing()
            self.total_triggers += 1
            
            # 执行回调
            result = None
            if callback:
                try:
                    result = await callback(accumulated_audio)
                    logger.info(f"✅ 说话人识别完成")
                except Exception as e:
                    logger.error(f"❌ 说话人识别回调失败: {e}")
            
            # 重置累积器
            self.accumulator.reset()
            
            return result
        
        return None
    
    async def process_audio_stream(
        self,
        audio_stream,
        callback: Callable[[bytes], Awaitable[Dict]]
    ):
        """处理音频流（生成器）
        
        Args:
            audio_stream: 音频流生成器，yield bytes
            callback: 触发时的异步回调函数
        """
        async for audio_chunk in audio_stream:
            await self.process_audio_chunk(audio_chunk, callback)
    
    def get_statistics(self) -> Dict:
        """获取统计信息
        
        Returns:
            dict: 统计信息
        """
        vad_stats = (
            self.vad_detector.get_statistics()
            if self.vad_detector
            else {}
        )
        acc_stats = self.accumulator.get_statistics()
        
        return {
            "enabled": self.enabled,
            "total_chunks_processed": self.total_chunks_processed,
            "total_triggers": self.total_triggers,
            "total_skipped": self.total_skipped,
            "vad_detector": vad_stats,
            "accumulator": acc_stats,
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.total_chunks_processed = 0
        self.total_triggers = 0
        self.total_skipped = 0
        
        if self.vad_detector:
            self.vad_detector.reset_statistics()
        
        # 累积器的统计由其内部管理
    
    def update_config(
        self,
        vad_mode: Optional[int] = None,
        trigger_duration_ms: Optional[int] = None,
        max_duration_ms: Optional[int] = None,
        silence_tolerance_ms: Optional[int] = None,
        min_speech_ratio: Optional[float] = None
    ):
        """动态更新配置
        
        Args:
            vad_mode: WebRTC VAD灵敏度模式
            trigger_duration_ms: 触发识别的最小语音时长
            max_duration_ms: 最大累积时长
            silence_tolerance_ms: 静音容忍时间
            min_speech_ratio: 最小语音占比
        """
        if vad_mode is not None and self.vad_detector:
            self.vad_detector.set_mode(vad_mode)
        
        self.accumulator.update_config(
            trigger_duration_ms=trigger_duration_ms,
            max_duration_ms=max_duration_ms,
            silence_tolerance_ms=silence_tolerance_ms,
            min_speech_ratio=min_speech_ratio
        )
        
        logger.info("🔧 智能触发器配置已更新")
    
    def is_enabled(self) -> bool:
        """检查触发器是否已启用
        
        Returns:
            bool: True表示已启用，False表示未启用
        """
        return self.enabled
    
    def get_current_state(self) -> SpeechState:
        """获取当前累积器状态
        
        Returns:
            SpeechState: 当前状态
        """
        return self.accumulator.get_state()


# 全局单例（可选）
_global_trigger: Optional[SmartSpeakerTrigger] = None


def get_smart_speaker_trigger(
    vad_mode: int = 2,
    trigger_duration_ms: int = 2000,
    force_new: bool = False
) -> Optional[SmartSpeakerTrigger]:
    """获取智能说话人识别触发器实例（单例模式）
    
    Args:
        vad_mode: WebRTC VAD灵敏度模式
        trigger_duration_ms: 触发识别的最小语音时长
        force_new: 是否强制创建新实例
    
    Returns:
        SmartSpeakerTrigger: 触发器实例
    """
    global _global_trigger
    
    if force_new or _global_trigger is None:
        _global_trigger = SmartSpeakerTrigger(
            vad_mode=vad_mode,
            trigger_duration_ms=trigger_duration_ms
        )
    
    return _global_trigger

