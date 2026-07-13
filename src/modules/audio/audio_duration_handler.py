#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音频时长处理模块。

解决说话人识别和分离的音频时长限制问题，提供音频分段、合并和优化处理功能。
"""

import numpy as np
import logging
from typing import List, Tuple, Dict, Optional, Union
import time


class AudioDurationError(Exception):
    """音频时长处理相关异常。"""
    pass


class AudioDurationHandler:
    """音频时长处理器。
    
    解决FunASR说话人识别和分离模型的时长限制问题：
    1. 说话人识别：建议音频时长 1-30秒，最佳 3-10秒
    2. 说话人分离：建议音频时长 5-300秒，最佳 10-60秒
    3. VAD处理：单段最大 60秒
    
    处理策略：
    - 短音频：填充或合并到最小时长
    - 长音频：智能分段处理
    - 重叠处理：确保说话人连续性
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
        # 时长限制配置（毫秒）
        self.speaker_id_min_duration = 1000    # 说话人识别最小时长：1秒
        self.speaker_id_max_duration = 30000   # 说话人识别最大时长：30秒
        self.speaker_id_optimal_duration = 5000 # 说话人识别最佳时长：5秒
        
        self.speaker_dia_min_duration = 5000   # 说话人分离最小时长：5秒
        self.speaker_dia_max_duration = 300000 # 说话人分离最大时长：300秒
        self.speaker_dia_optimal_duration = 30000 # 说话人分离最佳时长：30秒
        
        self.vad_max_segment_duration = 60000  # VAD最大段时长：60秒
        
        # 音频参数
        self.sample_rate = 16000  # 16kHz
        self.bytes_per_sample = 2  # 16-bit
        self.bytes_per_second = self.sample_rate * self.bytes_per_sample
        
        # 分段重叠配置
        self.overlap_duration = 2000  # 重叠时长：2秒
        self.overlap_bytes = self.overlap_duration * self.bytes_per_second // 1000
    
    def get_audio_duration_ms(self, audio_data: bytes) -> int:
        """获取音频时长（毫秒）。
        
        Args:
            audio_data: 音频数据（16kHz, 16-bit PCM）
            
        Returns:
            音频时长（毫秒）
        """
        if not audio_data:
            return 0
        
        duration_ms = len(audio_data) * 1000 // self.bytes_per_second
        return duration_ms
    
    def validate_audio_for_speaker_identification(self, audio_data: bytes) -> Dict[str, any]:
        """验证音频是否适合说话人识别。
        
        Args:
            audio_data: 音频数据
            
        Returns:
            验证结果字典
        """
        duration_ms = self.get_audio_duration_ms(audio_data)
        
        result = {
            "valid": False,
            "duration_ms": duration_ms,
            "reason": "",
            "suggestion": "",
            "processed_audio": None
        }
        
        if duration_ms < self.speaker_id_min_duration:
            result["reason"] = f"音频过短（{duration_ms}ms < {self.speaker_id_min_duration}ms）"
            result["suggestion"] = "建议使用更长的音频或进行音频填充"
            # 尝试填充音频
            processed_audio = self._pad_audio_for_speaker_id(audio_data)
            if processed_audio:
                result["processed_audio"] = processed_audio
                result["valid"] = True
                result["reason"] = "音频已填充到最小时长"
        elif duration_ms > self.speaker_id_max_duration:
            result["reason"] = f"音频过长（{duration_ms}ms > {self.speaker_id_max_duration}ms）"
            result["suggestion"] = "建议截取音频中间部分或进行分段处理"
            # 截取最佳时长的音频
            processed_audio = self._trim_audio_for_speaker_id(audio_data)
            result["processed_audio"] = processed_audio
            result["valid"] = True
            result["reason"] = "音频已截取到最佳时长"
        else:
            result["valid"] = True
            result["reason"] = "音频时长适合说话人识别"
            result["processed_audio"] = audio_data
        
        return result
    
    def validate_audio_for_speaker_diarization(self, audio_data: bytes) -> Dict[str, any]:
        """验证音频是否适合说话人分离。
        
        Args:
            audio_data: 音频数据
            
        Returns:
            验证结果字典
        """
        duration_ms = self.get_audio_duration_ms(audio_data)
        
        result = {
            "valid": False,
            "duration_ms": duration_ms,
            "reason": "",
            "suggestion": "",
            "processed_audio": None,
            "segments": None
        }
        
        if duration_ms < self.speaker_dia_min_duration:
            result["reason"] = f"音频过短（{duration_ms}ms < {self.speaker_dia_min_duration}ms）"
            result["suggestion"] = "说话人分离需要更长的音频，建议至少5秒"
            result["valid"] = False
        elif duration_ms > self.speaker_dia_max_duration:
            result["reason"] = f"音频过长（{duration_ms}ms > {self.speaker_dia_max_duration}ms）"
            result["suggestion"] = "音频将被分段处理"
            # 分段处理
            segments = self._segment_audio_for_diarization(audio_data)
            result["segments"] = segments
            result["valid"] = True
            result["reason"] = f"音频已分为{len(segments)}段进行处理"
        else:
            result["valid"] = True
            result["reason"] = "音频时长适合说话人分离"
            result["processed_audio"] = audio_data
        
        return result
    
    def _pad_audio_for_speaker_id(self, audio_data: bytes) -> Optional[bytes]:
        """为说话人识别填充音频到最小时长。
        
        Args:
            audio_data: 原始音频数据
            
        Returns:
            填充后的音频数据
        """
        try:
            current_duration = self.get_audio_duration_ms(audio_data)
            if current_duration >= self.speaker_id_min_duration:
                return audio_data
            
            # 计算需要填充的时长
            target_duration = self.speaker_id_min_duration
            padding_duration = target_duration - current_duration
            padding_bytes = padding_duration * self.bytes_per_second // 1000
            
            # 使用静音填充
            padding = b'\x00' * padding_bytes
            
            # 在音频前后各填充一半
            half_padding = len(padding) // 2
            padded_audio = padding[:half_padding] + audio_data + padding[half_padding:]
            
            self.logger.debug(f"音频填充：{current_duration}ms -> {self.get_audio_duration_ms(padded_audio)}ms")
            return padded_audio
            
        except Exception as e:
            self.logger.warning(f"音频填充失败: {e}")
            return None
    
    def _trim_audio_for_speaker_id(self, audio_data: bytes) -> bytes:
        """为说话人识别截取音频到最佳时长。
        
        Args:
            audio_data: 原始音频数据
            
        Returns:
            截取后的音频数据
        """
        try:
            current_duration = self.get_audio_duration_ms(audio_data)
            if current_duration <= self.speaker_id_max_duration:
                return audio_data
            
            # 截取中间部分，保留最佳时长
            target_bytes = self.speaker_id_optimal_duration * self.bytes_per_second // 1000
            
            # 从中间开始截取
            start_offset = (len(audio_data) - target_bytes) // 2
            end_offset = start_offset + target_bytes
            
            trimmed_audio = audio_data[start_offset:end_offset]
            
            self.logger.debug(f"音频截取：{current_duration}ms -> {self.get_audio_duration_ms(trimmed_audio)}ms")
            return trimmed_audio
            
        except Exception as e:
            self.logger.warning(f"音频截取失败: {e}")
            return audio_data
    
    def _segment_audio_for_diarization(self, audio_data: bytes) -> List[Dict[str, any]]:
        """为说话人分离分段音频。
        
        Args:
            audio_data: 原始音频数据
            
        Returns:
            音频段列表
        """
        segments = []
        
        try:
            total_duration = self.get_audio_duration_ms(audio_data)
            segment_duration_bytes = self.speaker_dia_optimal_duration * self.bytes_per_second // 1000
            
            current_offset = 0
            segment_index = 0
            
            while current_offset < len(audio_data):
                # 计算当前段的结束位置
                end_offset = min(current_offset + segment_duration_bytes, len(audio_data))
                
                # 提取音频段
                segment_audio = audio_data[current_offset:end_offset]
                segment_duration = self.get_audio_duration_ms(segment_audio)
                
                # 只有足够长的段才进行处理
                if segment_duration >= self.speaker_dia_min_duration:
                    segments.append({
                        "index": segment_index,
                        "audio_data": segment_audio,
                        "start_offset": current_offset,
                        "end_offset": end_offset,
                        "duration_ms": segment_duration,
                        "start_time_ms": current_offset * 1000 // self.bytes_per_second,
                        "end_time_ms": end_offset * 1000 // self.bytes_per_second
                    })
                    segment_index += 1
                
                # 移动到下一段，考虑重叠
                if end_offset >= len(audio_data):
                    break
                
                current_offset = end_offset - self.overlap_bytes
                if current_offset < 0:
                    current_offset = end_offset
            
            self.logger.debug(f"音频分段：{total_duration}ms -> {len(segments)}段")
            return segments
            
        except Exception as e:
            self.logger.error(f"音频分段失败: {e}")
            return []
    
    def merge_diarization_results(self, segment_results: List[Dict]) -> Dict:
        """合并分段说话人分离结果。
        
        Args:
            segment_results: 各段的分离结果列表
            
        Returns:
            合并后的分离结果
        """
        try:
            if not segment_results:
                return None
            
            # 如果只有一段，直接返回
            if len(segment_results) == 1:
                return segment_results[0]
            
            # 合并多段结果
            merged_speakers = {}
            merged_segments = []
            total_speakers = set()
            
            for segment_idx, result in enumerate(segment_results):
                if not result or result.get("type") != "diarization":
                    continue
                
                # 获取段的时间偏移
                segment_info = result.get("segment_info", {})
                time_offset = segment_info.get("start_time_ms", 0)
                
                # 处理说话人段落
                for speaker_segment in result.get("speaker_segments", []):
                    speaker_id = speaker_segment["speaker_id"]
                    
                    # 调整时间戳
                    adjusted_segment = speaker_segment.copy()
                    adjusted_segment["start_time"] += time_offset
                    adjusted_segment["end_time"] += time_offset
                    adjusted_segment["segment_index"] = segment_idx
                    
                    merged_segments.append(adjusted_segment)
                    total_speakers.add(speaker_id)
                
                # 合并说话人统计
                for speaker in result.get("speakers", []):
                    speaker_id = speaker["speaker_id"]
                    if speaker_id not in merged_speakers:
                        merged_speakers[speaker_id] = {
                            "speaker_id": speaker_id,
                            "total_duration": 0,
                            "segment_count": 0,
                            "text_segments": []
                        }
                    
                    merged_speakers[speaker_id]["total_duration"] += speaker["total_duration"]
                    merged_speakers[speaker_id]["segment_count"] += speaker["segment_count"]
                    merged_speakers[speaker_id]["text_segments"].extend(speaker["text_segments"])
            
            # 按发言时长排序
            sorted_speakers = sorted(
                merged_speakers.values(),
                key=lambda x: x["total_duration"],
                reverse=True
            )
            
            merged_result = {
                "type": "diarization",
                "speakers": sorted_speakers,
                "primary_speaker": sorted_speakers[0] if sorted_speakers else None,
                "speaker_segments": merged_segments,
                "total_speakers": len(total_speakers),
                "processing_info": {
                    "total_segments": len(segment_results),
                    "merged_segments": len(merged_segments),
                    "processing_method": "segmented_merge"
                }
            }
            
            self.logger.debug(f"合并分离结果：{len(segment_results)}段 -> {len(total_speakers)}个说话人")
            return merged_result
            
        except Exception as e:
            self.logger.error(f"合并分离结果失败: {e}")
            return None
    
    def optimize_audio_for_processing(self, audio_data: bytes, task_type: str) -> Dict[str, any]:
        """为特定任务优化音频。
        
        Args:
            audio_data: 原始音频数据
            task_type: 任务类型（'identification' 或 'diarization'）
            
        Returns:
            优化结果字典
        """
        if task_type == "identification":
            return self.validate_audio_for_speaker_identification(audio_data)
        elif task_type == "diarization":
            return self.validate_audio_for_speaker_diarization(audio_data)
        else:
            raise AudioDurationError(f"不支持的任务类型: {task_type}")
    
    def get_processing_recommendations(self, audio_data: bytes) -> Dict[str, str]:
        """获取音频处理建议。
        
        Args:
            audio_data: 音频数据
            
        Returns:
            处理建议字典
        """
        duration_ms = self.get_audio_duration_ms(audio_data)
        recommendations = {}
        
        # 说话人识别建议
        if duration_ms < self.speaker_id_min_duration:
            recommendations["speaker_identification"] = "音频过短，建议录制更长音频或使用音频填充"
        elif duration_ms > self.speaker_id_max_duration:
            recommendations["speaker_identification"] = "音频过长，建议截取中间部分或分段处理"
        else:
            recommendations["speaker_identification"] = "音频时长适合说话人识别"
        
        # 说话人分离建议
        if duration_ms < self.speaker_dia_min_duration:
            recommendations["speaker_diarization"] = "音频过短，说话人分离需要至少5秒音频"
        elif duration_ms > self.speaker_dia_max_duration:
            recommendations["speaker_diarization"] = "音频过长，将进行分段处理"
        else:
            recommendations["speaker_diarization"] = "音频时长适合说话人分离"
        
        # 通用建议
        if self.speaker_id_min_duration <= duration_ms <= self.speaker_id_optimal_duration:
            recommendations["general"] = "音频时长理想，适合所有说话人处理任务"
        elif duration_ms < 1000:
            recommendations["general"] = "音频过短，可能影响处理质量"
        elif duration_ms > 600000:  # 10分钟
            recommendations["general"] = "音频很长，建议分段处理以提高效率"
        else:
            recommendations["general"] = "音频时长可接受"
        
        return recommendations


# 全局实例
_duration_handler = None


def get_audio_duration_handler() -> AudioDurationHandler:
    """获取音频时长处理器实例。
    
    Returns:
        AudioDurationHandler实例
    """
    global _duration_handler
    if _duration_handler is None:
        _duration_handler = AudioDurationHandler()
    return _duration_handler


def validate_speaker_audio(audio_data: bytes, task_type: str) -> Dict[str, any]:
    """验证说话人处理音频的便捷函数。
    
    Args:
        audio_data: 音频数据
        task_type: 任务类型（'identification' 或 'diarization'）
        
    Returns:
        验证结果字典
    """
    handler = get_audio_duration_handler()
    return handler.optimize_audio_for_processing(audio_data, task_type)


def get_audio_recommendations(audio_data: bytes) -> Dict[str, str]:
    """获取音频处理建议的便捷函数。
    
    Args:
        audio_data: 音频数据
        
    Returns:
        处理建议字典
    """
    handler = get_audio_duration_handler()
    return handler.get_processing_recommendations(audio_data)