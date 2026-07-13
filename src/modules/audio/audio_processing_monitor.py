#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音频处理时间监控模块。

提供VAD、ASR识别和说话人识别的时间监控和统计功能。
"""

import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ProcessingTimeRecord:
    """处理时间记录数据类。"""
    timestamp: float
    session_id: str
    audio_length: int  # 音频数据长度（字节）
    audio_duration: float  # 音频时长（毫秒）
    
    # VAD时间记录
    vad_start_time: Optional[float] = None
    vad_end_time: Optional[float] = None
    vad_processing_time: Optional[float] = None
    vad_success: bool = True
    vad_error: Optional[str] = None
    
    # ASR时间记录
    asr_start_time: Optional[float] = None
    asr_end_time: Optional[float] = None
    asr_processing_time: Optional[float] = None
    asr_mode: Optional[str] = None  # 'online', 'offline', '2pass'
    asr_success: bool = True
    asr_error: Optional[str] = None
    
    # 说话人识别时间记录
    speaker_start_time: Optional[float] = None
    speaker_end_time: Optional[float] = None
    speaker_processing_time: Optional[float] = None
    speaker_mode: Optional[str] = None  # 'identification', 'diarization'
    speaker_success: bool = True
    speaker_error: Optional[str] = None
    
    # 总处理时间
    total_processing_time: Optional[float] = None
    
    def calculate_total_time(self) -> float:
        """计算总处理时间。"""
        total = 0.0
        if self.vad_processing_time:
            total += self.vad_processing_time
        if self.asr_processing_time:
            total += self.asr_processing_time
        if self.speaker_processing_time:
            total += self.speaker_processing_time
        self.total_processing_time = total
        return total


class AudioProcessingMonitor:
    """音频处理时间监控器类。
    
    用于监控VAD、ASR和说话人识别的处理时间和性能指标。
    """
    
    def __init__(self, max_records: int = 1000):
        """初始化音频处理监控器。
        
        Args:
            max_records: 最大记录数量，超过后删除最旧的记录
        """
        self.records: List[ProcessingTimeRecord] = []
        self.max_records = max_records
        self.current_sessions: Dict[str, ProcessingTimeRecord] = {}
        
        # 统计信息
        self.total_sessions = 0
        self.total_vad_time = 0.0
        self.total_asr_time = 0.0
        self.total_speaker_time = 0.0
        self.total_processing_time = 0.0
        
        # 成功/失败计数
        self.vad_success_count = 0
        self.vad_error_count = 0
        self.asr_success_count = 0
        self.asr_error_count = 0
        self.speaker_success_count = 0
        self.speaker_error_count = 0
    
    def start_session(self, session_id: str, audio_length: int, audio_duration: float) -> None:
        """开始一个新的处理会话。
        
        Args:
            session_id: 会话ID
            audio_length: 音频数据长度（字节）
            audio_duration: 音频时长（毫秒）
        """
        record = ProcessingTimeRecord(
            timestamp=time.time(),
            session_id=session_id,
            audio_length=audio_length,
            audio_duration=audio_duration
        )
        self.current_sessions[session_id] = record
    
    def start_vad(self, session_id: str) -> None:
        """开始VAD处理计时。
        
        Args:
            session_id: 会话ID
        """
        if session_id in self.current_sessions:
            self.current_sessions[session_id].vad_start_time = time.time()
    
    def end_vad(self, session_id: str, success: bool = True, error_message: Optional[str] = None) -> None:
        """结束VAD处理计时。
        
        Args:
            session_id: 会话ID
            success: 是否成功
            error_message: 错误信息（如果有）
        """
        if session_id in self.current_sessions:
            record = self.current_sessions[session_id]
            record.vad_end_time = time.time()
            if record.vad_start_time:
                record.vad_processing_time = (record.vad_end_time - record.vad_start_time) * 1000  # 转换为毫秒
            record.vad_success = success
            record.vad_error = error_message
            
            # 更新统计
            if success:
                self.vad_success_count += 1
            else:
                self.vad_error_count += 1
    
    def start_asr(self, session_id: str, mode: str = 'offline') -> None:
        """开始ASR处理计时。
        
        Args:
            session_id: 会话ID
            mode: ASR模式 ('online', 'offline', '2pass')
        """
        if session_id in self.current_sessions:
            record = self.current_sessions[session_id]
            record.asr_start_time = time.time()
            record.asr_mode = mode
    
    def end_asr(self, session_id: str, success: bool = True, error_message: Optional[str] = None) -> None:
        """结束ASR处理计时。
        
        Args:
            session_id: 会话ID
            success: 是否成功
            error_message: 错误信息（如果有）
        """
        if session_id in self.current_sessions:
            record = self.current_sessions[session_id]
            record.asr_end_time = time.time()
            if record.asr_start_time:
                record.asr_processing_time = (record.asr_end_time - record.asr_start_time) * 1000  # 转换为毫秒
            record.asr_success = success
            record.asr_error = error_message
            
            # 更新统计
            if success:
                self.asr_success_count += 1
            else:
                self.asr_error_count += 1
    
    def start_speaker(self, session_id: str, mode: str = 'identification') -> None:
        """开始说话人处理计时。
        
        Args:
            session_id: 会话ID
            mode: 说话人处理模式 ('identification', 'diarization')
        """
        if session_id in self.current_sessions:
            record = self.current_sessions[session_id]
            record.speaker_start_time = time.time()
            record.speaker_mode = mode
    
    def end_speaker(self, session_id: str, success: bool = True, error_message: Optional[str] = None) -> None:
        """结束说话人处理计时。
        
        Args:
            session_id: 会话ID
            success: 是否成功
            error_message: 错误信息（如果有）
        """
        if session_id in self.current_sessions:
            record = self.current_sessions[session_id]
            record.speaker_end_time = time.time()
            if record.speaker_start_time:
                record.speaker_processing_time = (record.speaker_end_time - record.speaker_start_time) * 1000  # 转换为毫秒
            record.speaker_success = success
            record.speaker_error = error_message
            
            # 更新统计
            if success:
                self.speaker_success_count += 1
            else:
                self.speaker_error_count += 1
    
    def end_session(self, session_id: str) -> Optional[ProcessingTimeRecord]:
        """结束处理会话并保存记录。
        
        Args:
            session_id: 会话ID
            
        Returns:
            完成的处理时间记录
        """
        if session_id in self.current_sessions:
            record = self.current_sessions[session_id]
            record.calculate_total_time()
            
            # 更新总统计
            self.total_sessions += 1
            if record.vad_processing_time:
                self.total_vad_time += record.vad_processing_time
            if record.asr_processing_time:
                self.total_asr_time += record.asr_processing_time
            if record.speaker_processing_time:
                self.total_speaker_time += record.speaker_processing_time
            if record.total_processing_time:
                self.total_processing_time += record.total_processing_time
            
            # 保存记录
            self.records.append(record)
            
            # 保持最大记录数限制
            if len(self.records) > self.max_records:
                self.records.pop(0)
            
            # 清理当前会话
            del self.current_sessions[session_id]
            
            return record
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取处理时间统计信息。
        
        Returns:
            包含统计信息的字典
        """
        if self.total_sessions == 0:
            return {
                'total_sessions': 0,
                'vad_stats': {'avg_time': 0.0, 'success_rate': 0.0, 'total_time': 0.0},
                'asr_stats': {'avg_time': 0.0, 'success_rate': 0.0, 'total_time': 0.0},
                'speaker_stats': {'avg_time': 0.0, 'success_rate': 0.0, 'total_time': 0.0},
                'overall_stats': {'avg_total_time': 0.0, 'total_processing_time': 0.0}
            }
        
        # VAD统计
        vad_total_requests = self.vad_success_count + self.vad_error_count
        vad_success_rate = (self.vad_success_count / vad_total_requests * 100) if vad_total_requests > 0 else 0.0
        vad_avg_time = (self.total_vad_time / vad_total_requests) if vad_total_requests > 0 else 0.0
        
        # ASR统计
        asr_total_requests = self.asr_success_count + self.asr_error_count
        asr_success_rate = (self.asr_success_count / asr_total_requests * 100) if asr_total_requests > 0 else 0.0
        asr_avg_time = (self.total_asr_time / asr_total_requests) if asr_total_requests > 0 else 0.0
        
        # 说话人统计
        speaker_total_requests = self.speaker_success_count + self.speaker_error_count
        speaker_success_rate = (self.speaker_success_count / speaker_total_requests * 100) if speaker_total_requests > 0 else 0.0
        speaker_avg_time = (self.total_speaker_time / speaker_total_requests) if speaker_total_requests > 0 else 0.0
        
        return {
            'total_sessions': self.total_sessions,
            'vad_stats': {
                'total_requests': vad_total_requests,
                'success_count': self.vad_success_count,
                'error_count': self.vad_error_count,
                'success_rate': vad_success_rate,
                'avg_time': vad_avg_time,
                'total_time': self.total_vad_time
            },
            'asr_stats': {
                'total_requests': asr_total_requests,
                'success_count': self.asr_success_count,
                'error_count': self.asr_error_count,
                'success_rate': asr_success_rate,
                'avg_time': asr_avg_time,
                'total_time': self.total_asr_time
            },
            'speaker_stats': {
                'total_requests': speaker_total_requests,
                'success_count': self.speaker_success_count,
                'error_count': self.speaker_error_count,
                'success_rate': speaker_success_rate,
                'avg_time': speaker_avg_time,
                'total_time': self.total_speaker_time
            },
            'overall_stats': {
                'avg_total_time': self.total_processing_time / self.total_sessions,
                'total_processing_time': self.total_processing_time
            }
        }
    
    def get_recent_records(self, count: int = 10) -> List[Dict[str, Any]]:
        """获取最近的处理记录。
        
        Args:
            count: 返回记录数量
            
        Returns:
            最近的处理记录列表
        """
        recent_records = self.records[-count:] if len(self.records) >= count else self.records
        return [asdict(record) for record in recent_records]
    
    def export_to_json(self, filepath: str) -> None:
        """导出统计数据到JSON文件。
        
        Args:
            filepath: 导出文件路径
        """
        export_data = {
            'export_time': datetime.now().isoformat(),
            'statistics': self.get_statistics(),
            'recent_records': self.get_recent_records(100)  # 导出最近100条记录
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    def reset(self) -> None:
        """重置监控统计。"""
        self.records.clear()
        self.current_sessions.clear()
        self.total_sessions = 0
        self.total_vad_time = 0.0
        self.total_asr_time = 0.0
        self.total_speaker_time = 0.0
        self.total_processing_time = 0.0
        self.vad_success_count = 0
        self.vad_error_count = 0
        self.asr_success_count = 0
        self.asr_error_count = 0
        self.speaker_success_count = 0
        self.speaker_error_count = 0


# 全局音频处理监控器实例
_audio_processing_monitor = AudioProcessingMonitor()


def get_audio_processing_monitor() -> AudioProcessingMonitor:
    """获取全局音频处理监控器实例。
    
    Returns:
        音频处理监控器实例
    """
    return _audio_processing_monitor


def reset_audio_processing_monitor() -> None:
    """重置全局音频处理监控器。"""
    global _audio_processing_monitor
    _audio_processing_monitor.reset()