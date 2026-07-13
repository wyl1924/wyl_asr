#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语音活动累积器模块

累积WebRTC VAD检测到的语音片段，并智能判断何时触发说话人识别。
"""

import logging
import time
from enum import Enum
from typing import Optional, Dict
from collections import deque

logger = logging.getLogger(__name__)


class SpeechState(Enum):
    """语音状态枚举"""
    IDLE = "idle"  # 空闲状态，无语音活动
    COLLECTING = "collecting"  # 正在收集语音
    READY = "ready"  # 准备就绪，可以触发识别
    PROCESSING = "processing"  # 正在处理识别


class SpeechActivityAccumulator:
    """语音活动累积器
    
    负责累积WebRTC VAD检测到的语音片段，并根据配置的策略
    智能判断何时应该触发说话人识别。
    
    核心功能:
    1. 累积连续的语音帧
    2. 容忍短暂的静音停顿
    3. 计算语音占比，过滤噪音
    4. 防止过度频繁触发
    5. 限制最大累积时长
    
    使用示例:
        accumulator = SpeechActivityAccumulator(
            trigger_duration_ms=2000,
            max_duration_ms=10000
        )
        
        # 每帧处理
        for audio_frame, is_speech in audio_stream:
            accumulator.add_frame(audio_frame, is_speech)
            
            if accumulator.should_trigger():
                audio = accumulator.get_accumulated_audio()
                # 执行说话人识别
                accumulator.reset()
    """
    
    def __init__(
        self,
        trigger_duration_ms: int = 2000,
        max_duration_ms: int = 10000,
        silence_tolerance_ms: int = 500,
        min_speech_ratio: float = 0.6,
        min_trigger_interval_ms: int = 1000,
        frame_duration_ms: int = 30
    ):
        """初始化语音活动累积器
        
        Args:
            trigger_duration_ms: 触发识别的最小语音累积时长（毫秒）
            max_duration_ms: 最大累积时长（毫秒），超过后强制触发
            silence_tolerance_ms: 静音容忍时间（毫秒），短暂停顿不中断累积
            min_speech_ratio: 最小语音占比（0.0-1.0），用于过滤噪音
            min_trigger_interval_ms: 两次触发的最小间隔（毫秒）
            frame_duration_ms: 每帧的时长（毫秒）
        """
        # 配置参数
        self.trigger_duration_ms = trigger_duration_ms
        self.max_duration_ms = max_duration_ms
        self.silence_tolerance_ms = silence_tolerance_ms
        self.min_speech_ratio = min_speech_ratio
        self.min_trigger_interval_ms = min_trigger_interval_ms
        self.frame_duration_ms = frame_duration_ms
        
        # 计算帧级参数
        self.trigger_frames = trigger_duration_ms // frame_duration_ms
        self.max_frames = max_duration_ms // frame_duration_ms
        self.silence_tolerance_frames = silence_tolerance_ms // frame_duration_ms
        
        # 状态变量
        self.state = SpeechState.IDLE
        self.audio_buffer = bytearray()
        self.frame_labels = deque()  # 每帧的语音标签 (True/False)
        self.total_frames = 0
        self.speech_frames = 0
        self.silence_frames = 0
        self.consecutive_silence_frames = 0
        
        # 时间戳
        self.accumulation_start_time = 0.0
        self.last_trigger_time = 0.0
        
        # 统计信息
        self.total_triggers = 0
        self.total_resets = 0
        
        logger.info(
            f"✅ 语音活动累积器初始化: "
            f"trigger={trigger_duration_ms}ms, "
            f"max={max_duration_ms}ms, "
            f"silence_tolerance={silence_tolerance_ms}ms, "
            f"min_ratio={min_speech_ratio}"
        )
    
    def add_frame(self, audio_frame: bytes, is_speech: bool):
        """添加一帧音频数据
        
        Args:
            audio_frame: PCM音频数据
            is_speech: WebRTC VAD检测结果，True表示语音，False表示静音
        """
        current_time = time.time()
        
        # 状态转换：IDLE -> COLLECTING
        if self.state == SpeechState.IDLE and is_speech:
            self.state = SpeechState.COLLECTING
            self.accumulation_start_time = current_time
            logger.debug("🎤 检测到语音开始，进入COLLECTING状态")
        
        # 如果不在收集状态，且当前是静音，直接返回
        if self.state == SpeechState.IDLE:
            return
        
        # 添加音频帧到缓冲区
        self.audio_buffer.extend(audio_frame)
        self.frame_labels.append(is_speech)
        self.total_frames += 1
        
        # 更新统计
        if is_speech:
            self.speech_frames += 1
            self.consecutive_silence_frames = 0
        else:
            self.silence_frames += 1
            self.consecutive_silence_frames += 1
        
        # 检查是否超过静音容忍时间（结束语音段）
        if self.consecutive_silence_frames > self.silence_tolerance_frames:
            if self.total_frames >= self.trigger_frames:
                # 足够长的语音段，标记为READY
                speech_ratio = self._calculate_speech_ratio()
                if speech_ratio >= self.min_speech_ratio:
                    self.state = SpeechState.READY
                    logger.debug(
                        f"✅ 语音段结束，准备触发: "
                        f"duration={self.get_duration_ms()}ms, "
                        f"ratio={speech_ratio:.2f}"
                    )
                else:
                    # 语音占比太低，重置
                    logger.debug(
                        f"⚠️ 语音占比过低 ({speech_ratio:.2f} < {self.min_speech_ratio})，重置累积器"
                    )
                    self.reset()
            else:
                # 语音段太短，重置
                logger.debug(f"⚠️ 语音段过短 ({self.total_frames} < {self.trigger_frames}帧)，重置累积器")
                self.reset()
        
        # 检查是否超过最大累积时长（强制触发）
        elif self.total_frames >= self.max_frames:
            speech_ratio = self._calculate_speech_ratio()
            if speech_ratio >= self.min_speech_ratio:
                self.state = SpeechState.READY
                logger.info(
                    f"⚠️ 达到最大累积时长，强制触发: "
                    f"duration={self.get_duration_ms()}ms, "
                    f"ratio={speech_ratio:.2f}"
                )
            else:
                # 即使达到最大时长，语音占比太低也不触发
                logger.warning(
                    f"⚠️ 达到最大时长但语音占比过低 ({speech_ratio:.2f})，重置累积器"
                )
                self.reset()
    
    def should_trigger(self) -> bool:
        """判断是否应该触发说话人识别
        
        Returns:
            bool: True表示应该触发，False表示不触发
        """
        if self.state != SpeechState.READY:
            return False
        
        # 检查是否满足最小触发间隔
        current_time = time.time()
        time_since_last_trigger = (current_time - self.last_trigger_time) * 1000
        
        if time_since_last_trigger < self.min_trigger_interval_ms:
            logger.debug(
                f"⏳ 距上次触发时间过短 ({time_since_last_trigger:.0f}ms < {self.min_trigger_interval_ms}ms)，"
                f"暂不触发"
            )
            return False
        
        return True
    
    def get_accumulated_audio(self) -> bytes:
        """获取累积的音频数据
        
        Returns:
            bytes: 累积的PCM音频数据
        """
        return bytes(self.audio_buffer)
    
    def get_duration_ms(self) -> int:
        """获取累积音频的时长（毫秒）
        
        Returns:
            int: 时长（毫秒）
        """
        return self.total_frames * self.frame_duration_ms
    
    def mark_as_processing(self):
        """标记为正在处理状态"""
        self.state = SpeechState.PROCESSING
        self.last_trigger_time = time.time()
        self.total_triggers += 1
        
        logger.debug(
            f"🔄 标记为PROCESSING状态，触发次数: {self.total_triggers}"
        )
    
    def reset(self):
        """重置累积器状态"""
        self.state = SpeechState.IDLE
        self.audio_buffer.clear()
        self.frame_labels.clear()
        self.total_frames = 0
        self.speech_frames = 0
        self.silence_frames = 0
        self.consecutive_silence_frames = 0
        self.accumulation_start_time = 0.0
        self.total_resets += 1
        
        logger.debug(f"🔄 累积器已重置，重置次数: {self.total_resets}")
    
    def _calculate_speech_ratio(self) -> float:
        """计算语音占比
        
        Returns:
            float: 语音帧占比 (0.0-1.0)
        """
        if self.total_frames == 0:
            return 0.0
        
        return self.speech_frames / self.total_frames
    
    def get_state(self) -> SpeechState:
        """获取当前状态
        
        Returns:
            SpeechState: 当前状态
        """
        return self.state
    
    def get_statistics(self) -> Dict:
        """获取统计信息
        
        Returns:
            dict: 统计信息
        """
        return {
            "state": self.state.value,
            "duration_ms": self.get_duration_ms(),
            "total_frames": self.total_frames,
            "speech_frames": self.speech_frames,
            "silence_frames": self.silence_frames,
            "speech_ratio": self._calculate_speech_ratio(),
            "total_triggers": self.total_triggers,
            "total_resets": self.total_resets,
            "buffer_size_bytes": len(self.audio_buffer),
        }
    
    def get_debug_info(self) -> str:
        """获取调试信息字符串
        
        Returns:
            str: 格式化的调试信息
        """
        stats = self.get_statistics()
        return (
            f"[Accumulator] state={stats['state']}, "
            f"duration={stats['duration_ms']}ms, "
            f"frames={stats['total_frames']}, "
            f"ratio={stats['speech_ratio']:.2f}, "
            f"triggers={stats['total_triggers']}"
        )
    
    def update_config(
        self,
        trigger_duration_ms: Optional[int] = None,
        max_duration_ms: Optional[int] = None,
        silence_tolerance_ms: Optional[int] = None,
        min_speech_ratio: Optional[float] = None,
        min_trigger_interval_ms: Optional[int] = None
    ):
        """动态更新配置参数
        
        Args:
            trigger_duration_ms: 触发识别的最小语音累积时长
            max_duration_ms: 最大累积时长
            silence_tolerance_ms: 静音容忍时间
            min_speech_ratio: 最小语音占比
            min_trigger_interval_ms: 两次触发的最小间隔
        """
        if trigger_duration_ms is not None:
            self.trigger_duration_ms = trigger_duration_ms
            self.trigger_frames = trigger_duration_ms // self.frame_duration_ms
        
        if max_duration_ms is not None:
            self.max_duration_ms = max_duration_ms
            self.max_frames = max_duration_ms // self.frame_duration_ms
        
        if silence_tolerance_ms is not None:
            self.silence_tolerance_ms = silence_tolerance_ms
            self.silence_tolerance_frames = silence_tolerance_ms // self.frame_duration_ms
        
        if min_speech_ratio is not None:
            self.min_speech_ratio = min_speech_ratio
        
        if min_trigger_interval_ms is not None:
            self.min_trigger_interval_ms = min_trigger_interval_ms
        
        logger.info(
            f"🔧 累积器配置已更新: "
            f"trigger={self.trigger_duration_ms}ms, "
            f"max={self.max_duration_ms}ms, "
            f"silence_tolerance={self.silence_tolerance_ms}ms, "
            f"min_ratio={self.min_speech_ratio}"
        )


# 全局单例（可选）
_global_accumulator: Optional[SpeechActivityAccumulator] = None


def get_speech_accumulator(
    trigger_duration_ms: int = 2000,
    max_duration_ms: int = 10000,
    force_new: bool = False
) -> SpeechActivityAccumulator:
    """获取语音活动累积器实例（单例模式）
    
    Args:
        trigger_duration_ms: 触发识别的最小语音累积时长
        max_duration_ms: 最大累积时长
        force_new: 是否强制创建新实例
    
    Returns:
        SpeechActivityAccumulator: 累积器实例
    """
    global _global_accumulator
    
    if force_new or _global_accumulator is None:
        _global_accumulator = SpeechActivityAccumulator(
            trigger_duration_ms=trigger_duration_ms,
            max_duration_ms=max_duration_ms
        )
    
    return _global_accumulator

