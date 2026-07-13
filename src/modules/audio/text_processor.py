#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本处理器模块

该模块提供了语音识别结果的文本后处理功能，包括：
- 标点符号清理
- 热词增强处理
- 富文本后处理集成

Author: Assistant
Date: 2024
"""

import re
import logging
from typing import Dict, List, Optional, Union, Any

try:
    from funasr.utils.postprocess_utils import rich_transcription_postprocess
except ImportError:
    logging.warning("FunASR not installed. Please install it: pip install funasr")
    rich_transcription_postprocess = None


class TextProcessor:
    """
    文本处理器类
    
    负责对语音识别结果进行各种文本后处理操作，包括标点符号清理、
    热词增强等功能。
    """
    
    def __init__(self, hotword_map: Optional[Dict[str, int]] = None):
        """
        初始化文本处理器
        
        Args:
            hotword_map: 热词映射字典，格式为 {热词: 权重}
        """
        self.hotword_map = hotword_map or {}
        
    def process_text(
        self, 
        text: str, 
        enable_rich_postprocess: bool = True,
        enable_punctuation_cleaning: bool = True,
        enable_hotword_boost: bool = True
    ) -> str:
        """
        对文本进行完整的后处理
        
        Args:
            text: 原始文本
            enable_rich_postprocess: 是否启用富文本后处理
            enable_punctuation_cleaning: 是否启用标点符号清理
            enable_hotword_boost: 是否启用热词增强
            
        Returns:
            处理后的文本
        """
        if not text:
            return text
            
        processed_text = text
        
        # 1. 富文本后处理（标点符号恢复等）
        if enable_rich_postprocess and rich_transcription_postprocess:
            processed_text = rich_transcription_postprocess(processed_text)
            
        # 2. 清理重复标点符号
        if enable_punctuation_cleaning:
            processed_text = self.clean_punctuation(processed_text)
            
        # 3. 应用热词增强
        if enable_hotword_boost and self.hotword_map:
            processed_text = self.apply_hotword_boost(processed_text)
            
        return processed_text
    
    def clean_punctuation(self, text: str) -> str:
        """
        清理文本中的重复标点符号
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return text
        
        # 简化的标点符号清理：遇到连续的标点符号，只保留第一个
        # 1. 处理相同标点符号的重复
        punctuation_pattern = r'([。，、？！；：,.?!;:])\1+'
        cleaned_text = re.sub(punctuation_pattern, r'\1', text)
        
        # 2. 特殊处理：逗号后跟句号的情况，保留句号（必须在混合标点处理之前）
        comma_period_pattern = r'，([。.])'
        cleaned_text = re.sub(comma_period_pattern, r'\1', cleaned_text)
        
        # 3. 处理不同标点符号的混合组合，保留第一个
        mixed_punctuation_pattern = r'([。，、？！；：,.?!;:])([。，、？！；：,.?!;:]+)'
        cleaned_text = re.sub(mixed_punctuation_pattern, r'\1', cleaned_text)
        
        # 4. 处理标点符号间的空格
        space_punctuation_pattern = r'([。，、？！；：,.?!;:])\s+([。，、？！；：,.?!;:])'
        cleaned_text = re.sub(space_punctuation_pattern, r'\1', cleaned_text)
        
        # 移除文本开头和结尾的多余空格
        cleaned_text = cleaned_text.strip()
        
        # 记录清理操作（仅在有变化时）
        if cleaned_text != text:
            logging.debug(f"标点符号清理: '{text}' -> '{cleaned_text}'")
        
        return cleaned_text
    
    def apply_hotword_boost(self, text: str) -> str:
        """
        应用热词增强处理
        
        Args:
            text: 原始识别文本
            
        Returns:
            增强后的文本
        """
        if not text or not self.hotword_map:
            return text
        
        enhanced_text = text
        detected_hotwords = []
        
        # 检测热词并应用增强
        for hotword, weight in self.hotword_map.items():
            if hotword in text:
                detected_hotwords.append((hotword, weight))
                logging.debug(f"检测到热词: {hotword} (权重: {weight})")
                
                # 实际的热词增强逻辑
                # 方案1: 在热词前后添加特殊标记（用于调试和验证）
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    enhanced_text = enhanced_text.replace(hotword, f"[{hotword}]")
                
                # 方案2: 可以在这里实现其他增强逻辑，如：
                # - 调整识别置信度
                # - 记录热词统计信息
                # - 触发特定的后处理流程
        
        # 记录检测到的热词信息
        if detected_hotwords:
            logging.info(f"🔥 检测到 {len(detected_hotwords)} 个热词: {[hw[0] for hw in detected_hotwords]}")
        
        return enhanced_text
    
    def process_results(
        self, 
        results: List[Dict], 
        output_timestamp: bool = True,
        enable_rich_postprocess: bool = True,
        enable_punctuation_cleaning: bool = True,
        enable_hotword_boost: bool = True
    ) -> List[Dict[str, Any]]:
        """
        批量处理识别结果
        
        Args:
            results: 原始识别结果列表
            output_timestamp: 是否包含时间戳
            enable_rich_postprocess: 是否启用富文本后处理
            enable_punctuation_cleaning: 是否启用标点符号清理
            enable_hotword_boost: 是否启用热词增强
        
        Returns:
            处理后的结果列表
        """
        processed = []
        
        for result in results:
            if "text" in result:
                # 处理文本
                processed_text = self.process_text(
                    result["text"],
                    enable_rich_postprocess=enable_rich_postprocess,
                    enable_punctuation_cleaning=enable_punctuation_cleaning,
                    enable_hotword_boost=enable_hotword_boost
                )
                
                processed_result = {
                    "text": processed_text,
                    "raw_text": result["text"],
                }
                
                # 添加时间戳信息
                if output_timestamp and "timestamp" in result:
                    processed_result["timestamp"] = result["timestamp"]
                
                # 添加其他元数据
                for key in ["key", "language", "emotion", "event"]:
                    if key in result:
                        processed_result[key] = result[key]
                
                processed.append(processed_result)
        
        return processed
    
    def update_hotword_map(self, hotword_map: Dict[str, int]):
        """
        更新热词映射
        
        Args:
            hotword_map: 新的热词映射字典
        """
        self.hotword_map = hotword_map or {}
        logging.info(f"热词映射已更新，包含 {len(self.hotword_map)} 个热词")
    
    def add_hotword(self, hotword: str, weight: int = 1):
        """
        添加单个热词
        
        Args:
            hotword: 热词
            weight: 权重
        """
        self.hotword_map[hotword] = weight
        logging.info(f"添加热词: {hotword} (权重: {weight})")
    
    def remove_hotword(self, hotword: str):
        """
        移除热词
        
        Args:
            hotword: 要移除的热词
        """
        if hotword in self.hotword_map:
            del self.hotword_map[hotword]
            logging.info(f"移除热词: {hotword}")
    
    def get_hotword_stats(self) -> Dict[str, Any]:
        """
        获取热词统计信息
        
        Returns:
            热词统计信息
        """
        return {
            "total_hotwords": len(self.hotword_map),
            "hotwords": list(self.hotword_map.keys()),
            "weights": list(self.hotword_map.values()),
            "avg_weight": sum(self.hotword_map.values()) / len(self.hotword_map) if self.hotword_map else 0
        }