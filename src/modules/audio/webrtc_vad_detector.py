#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebRTC VAD检测器模块

提供基于WebRTC VAD的轻量级实时语音活动检测功能。
"""

import logging
from typing import Optional, List
import numpy as np

logger = logging.getLogger(__name__)

# 尝试导入webrtcvad，如果未安装则提供优雅降级
try:
    import webrtcvad
    WEBRTC_VAD_AVAILABLE = True
except ImportError:
    WEBRTC_VAD_AVAILABLE = False
    logger.warning("webrtcvad未安装，WebRTC VAD功能将不可用。安装方法: pip install webrtcvad")


class WebRTCVADDetector:
    """WebRTC VAD检测器
    
    提供实时语音活动检测功能，支持30ms帧级检测。
    
    特性:
    - 超低延迟 (< 10ms)
    - 低CPU占用 (< 1%)
    - 支持多种灵敏度模式
    - 支持多种采样率
    
    使用示例:
        detector = WebRTCVADDetector(mode=2, sample_rate=16000)
        is_speech = detector.detect_frame(audio_frame)
    """
    
    # 支持的采样率
    SUPPORTED_SAMPLE_RATES = [8000, 16000, 32000, 48000]
    
    # 支持的帧长度 (毫秒)
    SUPPORTED_FRAME_DURATIONS = [10, 20, 30]
    
    def __init__(
        self,
        mode: int = 2,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30
    ):
        """初始化WebRTC VAD检测器
        
        Args:
            mode: VAD灵敏度模式 (0-3)
                  0: 质量优先（最不激进，误报率最低）
                  1: 低延迟
                  2: 激进模式（推荐）
                  3: 超激进（最敏感，适合嘈杂环境）
            sample_rate: 采样率，必须是 8000, 16000, 32000, 48000 之一
            frame_duration_ms: 帧长度（毫秒），必须是 10, 20, 30 之一
            
        Raises:
            ValueError: 参数不在支持范围内
            RuntimeError: webrtcvad未安装
        """
        if not WEBRTC_VAD_AVAILABLE:
            raise RuntimeError(
                "webrtcvad未安装，无法使用WebRTC VAD功能。\n"
                "请安装: pip install webrtcvad"
            )
        
        # 验证参数
        if mode not in [0, 1, 2, 3]:
            raise ValueError(f"mode必须是0-3之间的整数，当前值: {mode}")
        
        if sample_rate not in self.SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                f"sample_rate必须是{self.SUPPORTED_SAMPLE_RATES}之一，"
                f"当前值: {sample_rate}"
            )
        
        if frame_duration_ms not in self.SUPPORTED_FRAME_DURATIONS:
            raise ValueError(
                f"frame_duration_ms必须是{self.SUPPORTED_FRAME_DURATIONS}之一，"
                f"当前值: {frame_duration_ms}"
            )
        
        self.mode = mode
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        
        # 计算每帧的样本数和字节数
        self.frame_samples = int(sample_rate * frame_duration_ms / 1000)
        self.frame_bytes = self.frame_samples * 2  # 16-bit PCM = 2 bytes per sample
        
        # 创建WebRTC VAD实例
        self.vad = webrtcvad.Vad(mode)
        
        # 统计信息
        self.total_frames = 0
        self.speech_frames = 0
        self.silence_frames = 0
        
        logger.info(
            f"✅ WebRTC VAD初始化成功: "
            f"mode={mode}, sample_rate={sample_rate}Hz, "
            f"frame_duration={frame_duration_ms}ms, "
            f"frame_bytes={self.frame_bytes}"
        )
    
    def detect_frame(self, audio_frame: bytes) -> bool:
        """检测单个音频帧是否包含语音
        
        Args:
            audio_frame: PCM音频数据（16-bit，单声道）
                        长度必须等于 frame_bytes
        
        Returns:
            bool: True表示检测到语音，False表示静音
            
        Raises:
            ValueError: 音频帧长度不正确
        """
        # 验证音频帧长度
        if len(audio_frame) != self.frame_bytes:
            raise ValueError(
                f"音频帧长度不正确: 期望{self.frame_bytes}字节，"
                f"实际{len(audio_frame)}字节"
            )
        
        # 调用WebRTC VAD进行检测
        is_speech = self.vad.is_speech(audio_frame, self.sample_rate)
        
        # 更新统计信息
        self.total_frames += 1
        if is_speech:
            self.speech_frames += 1
        else:
            self.silence_frames += 1
        
        return is_speech
    
    def detect_buffer(self, audio_buffer: bytes) -> List[bool]:
        """检测音频缓冲区中的所有帧
        
        将长音频缓冲区分割为固定长度的帧，逐帧检测。
        
        Args:
            audio_buffer: PCM音频数据（16-bit，单声道）
                         长度可以是任意值，会自动分帧
        
        Returns:
            List[bool]: 每帧的检测结果列表
        """
        results = []
        
        # 计算完整帧的数量
        num_frames = len(audio_buffer) // self.frame_bytes
        
        # 逐帧检测
        for i in range(num_frames):
            frame_start = i * self.frame_bytes
            frame_end = frame_start + self.frame_bytes
            frame = audio_buffer[frame_start:frame_end]
            
            is_speech = self.detect_frame(frame)
            results.append(is_speech)
        
        # 如果有剩余数据（不足一帧），记录警告
        remaining_bytes = len(audio_buffer) % self.frame_bytes
        if remaining_bytes > 0:
            logger.debug(
                f"音频缓冲区有{remaining_bytes}字节剩余数据（不足一帧），已忽略"
            )
        
        return results
    
    def get_speech_ratio(self, audio_buffer: bytes) -> float:
        """计算音频缓冲区中的语音占比
        
        Args:
            audio_buffer: PCM音频数据（16-bit，单声道）
        
        Returns:
            float: 语音帧占比 (0.0-1.0)
        """
        results = self.detect_buffer(audio_buffer)
        
        if not results:
            return 0.0
        
        speech_count = sum(1 for is_speech in results if is_speech)
        return speech_count / len(results)
    
    def reset_statistics(self):
        """重置统计信息"""
        self.total_frames = 0
        self.speech_frames = 0
        self.silence_frames = 0
    
    def get_statistics(self) -> dict:
        """获取统计信息
        
        Returns:
            dict: 包含统计信息的字典
        """
        speech_ratio = (
            self.speech_frames / self.total_frames
            if self.total_frames > 0
            else 0.0
        )
        
        return {
            "total_frames": self.total_frames,
            "speech_frames": self.speech_frames,
            "silence_frames": self.silence_frames,
            "speech_ratio": speech_ratio,
            "mode": self.mode,
            "sample_rate": self.sample_rate,
            "frame_duration_ms": self.frame_duration_ms,
        }
    
    def set_mode(self, mode: int):
        """动态设置VAD灵敏度模式
        
        Args:
            mode: 新的灵敏度模式 (0-3)
            
        Raises:
            ValueError: mode不在有效范围内
        """
        if mode not in [0, 1, 2, 3]:
            raise ValueError(f"mode必须是0-3之间的整数，当前值: {mode}")
        
        self.mode = mode
        self.vad.set_mode(mode)
        logger.info(f"WebRTC VAD模式已更新: mode={mode}")
    
    @classmethod
    def is_available(cls) -> bool:
        """检查WebRTC VAD是否可用
        
        Returns:
            bool: True表示可用，False表示未安装
        """
        return WEBRTC_VAD_AVAILABLE


# 全局单例实例（可选）
_global_detector: Optional[WebRTCVADDetector] = None


def get_webrtc_vad_detector(
    mode: int = 2,
    sample_rate: int = 16000,
    frame_duration_ms: int = 30,
    force_new: bool = False
) -> Optional[WebRTCVADDetector]:
    """获取WebRTC VAD检测器实例（单例模式）
    
    Args:
        mode: VAD灵敏度模式 (0-3)
        sample_rate: 采样率
        frame_duration_ms: 帧长度（毫秒）
        force_new: 是否强制创建新实例
    
    Returns:
        WebRTCVADDetector: 检测器实例，如果不可用则返回None
    """
    global _global_detector
    
    if not WebRTCVADDetector.is_available():
        logger.warning("WebRTC VAD不可用")
        return None
    
    if force_new or _global_detector is None:
        try:
            _global_detector = WebRTCVADDetector(
                mode=mode,
                sample_rate=sample_rate,
                frame_duration_ms=frame_duration_ms
            )
        except Exception as e:
            logger.error(f"创建WebRTC VAD检测器失败: {e}")
            return None
    
    return _global_detector

