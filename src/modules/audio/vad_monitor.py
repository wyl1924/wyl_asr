#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VAD监控模块。

提供VAD性能监控和统计功能。
"""

import time
from typing import Dict, List, Any, Optional


class VADMonitor:
    """VAD监控器类。
    
    用于监控VAD处理的性能指标和统计信息。
    """
    
    def __init__(self):
        """初始化VAD监控器。"""
        self.requests = []
        self.total_requests = 0
        self.total_processing_time = 0.0
        self.total_audio_duration = 0.0
        self.success_count = 0
        self.error_count = 0
    
    def record_vad_request(
        self,
        audio_length: int,
        audio_duration: float,
        processing_time: float,
        segments_result: List[Any],
        speech_start: int,
        speech_end: int,
        vad_config: Dict[str, Any],
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """记录VAD请求的监控数据。
        
        Args:
            audio_length: 音频数据长度（字节）
            audio_duration: 音频时长（毫秒）
            processing_time: 处理耗时（毫秒）
            segments_result: VAD检测结果
            speech_start: 语音开始时间
            speech_end: 语音结束时间
            vad_config: VAD配置参数
            success: 是否成功
            error_message: 错误信息（如果有）
        """
        request_data = {
            'timestamp': time.time(),
            'audio_length': audio_length,
            'audio_duration': audio_duration,
            'processing_time': processing_time,
            'segments_result': segments_result,
            'speech_start': speech_start,
            'speech_end': speech_end,
            'vad_config': vad_config,
            'success': success,
            'error_message': error_message
        }
        
        self.requests.append(request_data)
        self.total_requests += 1
        self.total_processing_time += processing_time
        self.total_audio_duration += audio_duration
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        # 保持最近1000条记录
        if len(self.requests) > 1000:
            self.requests.pop(0)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取VAD监控统计信息。
        
        Returns:
            包含统计信息的字典
        """
        if self.total_requests == 0:
            return {
                'total_requests': 0,
                'success_rate': 0.0,
                'avg_processing_time': 0.0,
                'avg_audio_duration': 0.0,
                'total_processing_time': 0.0,
                'total_audio_duration': 0.0
            }
        
        return {
            'total_requests': self.total_requests,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': self.success_count / self.total_requests * 100,
            'avg_processing_time': self.total_processing_time / self.total_requests,
            'avg_audio_duration': self.total_audio_duration / self.total_requests,
            'total_processing_time': self.total_processing_time,
            'total_audio_duration': self.total_audio_duration
        }
    
    def reset(self) -> None:
        """重置监控统计。"""
        self.requests.clear()
        self.total_requests = 0
        self.total_processing_time = 0.0
        self.total_audio_duration = 0.0
        self.success_count = 0
        self.error_count = 0


# 全局VAD监控器实例
_vad_monitor = VADMonitor()


def get_vad_monitor() -> VADMonitor:
    """获取全局VAD监控器实例。
    
    Returns:
        VAD监控器实例
    """
    return _vad_monitor


def reset_vad_monitor() -> None:
    """重置全局VAD监控器。"""
    global _vad_monitor
    _vad_monitor.reset()