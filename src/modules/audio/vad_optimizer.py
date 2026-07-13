#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VAD优化器模块 - 集成WebRTC VAD和FunASR VAD

提供统一的VAD优化接口，集成WebRTC VAD实时检测和FunASR VAD精确验证。
"""

import logging
from typing import Optional, Dict, Tuple
import asyncio

from .webrtc_vad_detector import WebRTCVADDetector, get_webrtc_vad_detector
from .speech_activity_accumulator import SpeechActivityAccumulator
from .smart_speaker_trigger import SmartSpeakerTrigger

logger = logging.getLogger(__name__)


class VADOptimizer:
    """VAD优化器
    
    集成WebRTC VAD和FunASR VAD，提供两层VAD检测架构：
    - 第一层：WebRTC VAD（轻量快速）- 实时检测语音活动
    - 第二层：FunASR VAD（精确但较重）- 验证有效语音段
    
    主要功能:
    1. 智能触发说话人识别（仅在有效语音时）
    2. 降低CPU占用（静音段跳过处理）
    3. 提高识别准确率（过滤噪音）
    4. 动态调整触发策略
    
    使用示例:
        optimizer = VADOptimizer(enable_webrtc_vad=True)
        
        # 处理音频
        should_trigger = optimizer.process_frame(audio_frame)
        
        if should_trigger:
            accumulated_audio = optimizer.get_accumulated_audio()
            # 执行说话人识别
            optimizer.reset()
    """
    
    def __init__(
        self,
        enable_webrtc_vad: bool = True,
        vad_mode: int = 2,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        trigger_duration_ms: int = 2000,
        max_duration_ms: int = 10000,
        silence_tolerance_ms: int = 500,
        min_speech_ratio: float = 0.6
    ):
        """初始化VAD优化器
        
        Args:
            enable_webrtc_vad: 是否启用WebRTC VAD优化
            vad_mode: WebRTC VAD灵敏度模式 (0-3)
            sample_rate: 采样率
            frame_duration_ms: 帧长度（毫秒）
            trigger_duration_ms: 触发识别的最小语音时长
            max_duration_ms: 最大累积时长
            silence_tolerance_ms: 静音容忍时间
            min_speech_ratio: 最小语音占比
        """
        self.enable_webrtc_vad = enable_webrtc_vad
        self.smart_trigger: Optional[SmartSpeakerTrigger] = None
        
        if enable_webrtc_vad:
            try:
                self.smart_trigger = SmartSpeakerTrigger(
                    vad_mode=vad_mode,
                    sample_rate=sample_rate,
                    frame_duration_ms=frame_duration_ms,
                    trigger_duration_ms=trigger_duration_ms,
                    max_duration_ms=max_duration_ms,
                    silence_tolerance_ms=silence_tolerance_ms,
                    min_speech_ratio=min_speech_ratio
                )
                
                if self.smart_trigger.is_enabled():
                    logger.info("✅ VAD优化器启用: WebRTC VAD + 智能触发")
                else:
                    logger.warning("⚠️ WebRTC VAD不可用，VAD优化器降级为传统模式")
                    self.enable_webrtc_vad = False
                    
            except Exception as e:
                logger.error(f"❌ 初始化智能触发器失败: {e}")
                self.enable_webrtc_vad = False
        else:
            logger.info("ℹ️ VAD优化器未启用，使用传统模式")
    
    def is_enabled(self) -> bool:
        """检查VAD优化器是否已启用
        
        Returns:
            bool: True表示已启用，False表示未启用
        """
        return self.enable_webrtc_vad and self.smart_trigger is not None
    
    async def process_audio_chunk(
        self,
        audio_chunk: bytes,
        callback=None
    ) -> Optional[Dict]:
        """处理音频块
        
        Args:
            audio_chunk: PCM音频数据
            callback: 触发时的回调函数（可选）
        
        Returns:
            Optional[Dict]: 如果触发了识别，返回结果；否则返回None
        """
        if not self.is_enabled() or self.smart_trigger is None:
            return None
        
        return await self.smart_trigger.process_audio_chunk(
            audio_chunk,
            callback=callback
        )
    
    def should_skip_processing(self, audio_chunk: bytes) -> bool:
        """判断是否应该跳过处理（静音段）
        
        这是一个快速检测方法，用于提前判断是否可以跳过某些处理。
        
        Args:
            audio_chunk: PCM音频数据
        
        Returns:
            bool: True表示应该跳过，False表示应该处理
        """
        if not self.is_enabled() or self.smart_trigger is None:
            return False
        
        # 快速检测：计算语音占比
        speech_ratio = self.smart_trigger.vad_detector.get_speech_ratio(audio_chunk)
        
        # 如果语音占比很低，可以跳过
        return speech_ratio < 0.1
    
    def get_statistics(self) -> Dict:
        """获取统计信息
        
        Returns:
            dict: 统计信息
        """
        if not self.is_enabled() or self.smart_trigger is None:
            return {
                "enabled": False,
                "mode": "traditional"
            }
        
        return {
            "enabled": True,
            "mode": "optimized",
            "statistics": self.smart_trigger.get_statistics()
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        if self.smart_trigger:
            self.smart_trigger.reset_statistics()
    
    def update_config(self, **kwargs):
        """动态更新配置
        
        接受的参数:
        - vad_mode: WebRTC VAD灵敏度模式
        - trigger_duration_ms: 触发识别的最小语音时长
        - max_duration_ms: 最大累积时长
        - silence_tolerance_ms: 静音容忍时间
        - min_speech_ratio: 最小语音占比
        """
        if self.smart_trigger:
            self.smart_trigger.update_config(**kwargs)


# 全局单例
_global_optimizer: Optional[VADOptimizer] = None


def get_vad_optimizer(
    enable_webrtc_vad: bool = True,
    force_new: bool = False
) -> VADOptimizer:
    """获取VAD优化器实例（单例模式）
    
    Args:
        enable_webrtc_vad: 是否启用WebRTC VAD
        force_new: 是否强制创建新实例
    
    Returns:
        VADOptimizer: 优化器实例
    """
    global _global_optimizer
    
    if force_new or _global_optimizer is None:
        _global_optimizer = VADOptimizer(enable_webrtc_vad=enable_webrtc_vad)
    
    return _global_optimizer


def check_webrtc_vad_availability() -> Dict[str, any]:
    """检查WebRTC VAD可用性
    
    Returns:
        dict: 包含可用性信息的字典
    """
    try:
        from .webrtc_vad_detector import WEBRTC_VAD_AVAILABLE
        
        if WEBRTC_VAD_AVAILABLE:
            # 尝试创建实例
            try:
                detector = WebRTCVADDetector(mode=2)
                return {
                    "available": True,
                    "status": "ready",
                    "message": "WebRTC VAD可用且正常工作",
                    "detector": detector
                }
            except Exception as e:
                return {
                    "available": False,
                    "status": "error",
                    "message": f"WebRTC VAD初始化失败: {e}",
                    "detector": None
                }
        else:
            return {
                "available": False,
                "status": "not_installed",
                "message": "webrtcvad未安装，请运行: pip install webrtcvad",
                "detector": None
            }
            
    except Exception as e:
        return {
            "available": False,
            "status": "error",
            "message": f"检查WebRTC VAD时出错: {e}",
            "detector": None
        }

