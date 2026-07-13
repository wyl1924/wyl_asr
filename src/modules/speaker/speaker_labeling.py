#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""说话人标记模块。

实现动态说话人标记功能：
- 如果识别成功但没有匹配的已注册说话人，自动分配说话人1、说话人2等标签
- 如果有匹配的已注册说话人，使用最高相似度的那个
- 支持说话人一致性检查和标签管理
"""

import logging
from typing import Dict, List, Optional, Union, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)


class SpeakerLabelingError(Exception):
    """说话人标记相关异常。"""
    pass


class SpeakerLabeler:
    """说话人标记器类"""
    
    def __init__(self, similarity_threshold: float = 0.7, consistency_threshold: float = 0.5):
        """
        初始化说话人标记器
        
        Args:
            similarity_threshold: 已注册说话人匹配的相似度阈值
            consistency_threshold: 动态标签一致性检查的相似度阈值（也用于动态标签模式匹配）
        """
        self.similarity_threshold = similarity_threshold
        self.consistency_threshold = consistency_threshold
        
        # 动态说话人标签管理
        self.dynamic_speakers = {}  # {label: {"embedding": np.array, "count": int, "last_seen": str}}
        self.next_speaker_id = 1
        
        logger.info(f"说话人标记器初始化完成，相似度阈值: {similarity_threshold}, 一致性阈值: {consistency_threshold}（用于模式匹配）")
    
    def process_speaker_result(self, speaker_result: Dict, audio_embedding: Optional[np.ndarray] = None) -> Dict:
        """
        处理说话人识别结果并分配标签
        
        处理逻辑：
        1. 先与已注册说话人比较，有符合相似度阈值的就返回最高相似度的
        2. 没有符合的再与临时分配的说话人比较
        3. 没有符合的就创建新的临时说话人保存供下次比较
        4. 有符合的取最高相似度的
        
        Args:
            speaker_result: identify_speaker函数的返回结果
            audio_embedding: 音频特征向量（必需，用于与临时说话人比较）
            
        Returns:
            处理后的说话人信息字典
        """
        try:
            # 检查识别结果是否有效
            if not speaker_result:
                # 完全没有识别结果，需要音频特征向量来分配动态标签
                if audio_embedding is None:
                    return {
                        "speaker_label": "未知说话人",
                        "speaker_type": "unknown",
                        "confidence": 0.0,
                        "message": "无识别结果且无音频特征向量"
                    }
                # 直接与临时说话人比较
                return self._process_with_dynamic_speakers(audio_embedding)
            
            # 检查是否识别成功
            if not speaker_result.get("success"):
                # 识别失败，需要音频特征向量来分配动态标签
                if audio_embedding is None:
                    message = speaker_result.get("message", "")
                    return {
                        "speaker_label": "未知说话人",
                        "speaker_type": "unknown",
                        "confidence": 0.0,
                        "message": f"说话人识别失败且无音频特征向量: {message}"
                    }
                # 直接与临时说话人比较
                return self._process_with_dynamic_speakers(audio_embedding)
            
            candidates = speaker_result.get("candidates", [])
            
            # 步骤1: 检查已注册说话人中是否有符合相似度阈值的
            qualified_registered = []
            for candidate in candidates:
                if candidate.get("similarity", 0) >= self.similarity_threshold:
                    qualified_registered.append(candidate)
            
            # 如果有符合条件的已注册说话人，返回相似度最高的
            if qualified_registered:
                best_registered = max(qualified_registered, key=lambda x: x.get("similarity", 0))
                logger.debug(f"匹配到已注册说话人: {best_registered['speaker_name']} (相似度: {best_registered['similarity']:.3f})")
                return {
                    "speaker_label": best_registered["speaker_name"],
                    "speaker_type": "registered",
                    "confidence": best_registered["similarity"],
                    "speaker_info": best_registered.get("speaker_info", {}),
                    "message": f"识别为已注册说话人: {best_registered['speaker_name']}"
                }
            
            # 步骤2: 没有符合条件的已注册说话人，与临时说话人比较
            if audio_embedding is None:
                # 没有音频特征向量，无法与临时说话人比较
                return {
                    "speaker_label": "未知说话人",
                    "speaker_type": "unknown",
                    "confidence": 0.0,
                    "message": "无符合条件的已注册说话人且无音频特征向量"
                }
            
            return self._process_with_dynamic_speakers(audio_embedding)
            
        except Exception as e:
            logger.error(f"处理说话人结果失败: {e}")
            return {
                "speaker_label": "错误",
                "speaker_type": "error",
                "confidence": 0.0,
                "message": f"处理失败: {str(e)}"
            }
    
    def _process_with_dynamic_speakers(self, audio_embedding: np.ndarray) -> Dict:
        """
        与临时分配的说话人进行比较处理
        
        Args:
            audio_embedding: 音频特征向量
            
        Returns:
            处理后的说话人信息字典
        """
        try:
            # 与现有的临时说话人比较
            similarity_results = []
            
            for label, speaker_data in self.dynamic_speakers.items():
                if "embedding" in speaker_data:
                    # 计算与现有临时说话人的相似度
                    similarity = cosine_similarity(
                        audio_embedding.reshape(1, -1),
                        speaker_data["embedding"].reshape(1, -1)
                    )[0][0]
                    
                    similarity_results.append({
                        "speaker_label": label,
                        "similarity": float(similarity)
                    })
            
            # 按相似度降序排序，取前3名
            similarity_results.sort(key=lambda x: x["similarity"], reverse=True)
            top_3_candidates = similarity_results[:3]
            
            # 检查是否有符合阈值的临时说话人
            best_match = None
            for candidate in similarity_results:
                if candidate["similarity"] >= self.consistency_threshold:
                    best_match = candidate
                    break
            
            # 如果找到符合条件的临时说话人
            if best_match:
                best_match_label = best_match["speaker_label"]
                best_similarity = best_match["similarity"]
                
                # 更新该说话人的信息
                self.dynamic_speakers[best_match_label]["count"] += 1
                self.dynamic_speakers[best_match_label]["last_seen"] = datetime.now().isoformat()
                
                # 使用加权平均更新特征向量
                old_embedding = self.dynamic_speakers[best_match_label]["embedding"]
                count = self.dynamic_speakers[best_match_label]["count"]
                weight = min(0.3, 1.0 / count)  # 新样本权重，随着样本增多而减小
                self.dynamic_speakers[best_match_label]["embedding"] = (
                    (1 - weight) * old_embedding + weight * audio_embedding
                )
                
                logger.debug(f"匹配到现有临时说话人: {best_match_label} (相似度: {best_similarity:.3f})")
                return {
                    "speaker_label": best_match_label,
                    "speaker_type": "dynamic",
                    "confidence": best_similarity,
                    "speaker_info": {
                        "speaker_id": best_match_label,
                        "speaker_name": best_match_label,
                        "speaker_type": "dynamic",
                        "count": self.dynamic_speakers[best_match_label]["count"],
                        "last_seen": self.dynamic_speakers[best_match_label]["last_seen"]
                    },
                    "top_3_candidates": top_3_candidates,
                    "message": f"匹配到临时说话人: {best_match_label}"
                }
            
            # 没有找到符合条件的临时说话人，创建新的
            new_label = f"说话人{self.next_speaker_id}"
            self.dynamic_speakers[new_label] = {
                "embedding": audio_embedding.copy(),
                "count": 1,
                "last_seen": datetime.now().isoformat()
            }
            self.next_speaker_id += 1
            
            logger.debug(f"创建新临时说话人: {new_label}")
            return {
                "speaker_label": new_label,
                "speaker_type": "dynamic",
                "confidence": 0.0,
                "speaker_info": {
                    "speaker_id": new_label,
                    "speaker_name": new_label,
                    "speaker_type": "dynamic",
                    "count": 1,
                    "last_seen": self.dynamic_speakers[new_label]["last_seen"]
                },
                "top_3_candidates": top_3_candidates,
                "message": f"创建新临时说话人: {new_label}"
            }
            
        except Exception as e:
            logger.error(f"临时说话人处理失败: {e}")
            # 回退到简单创建
            fallback_label = f"说话人{self.next_speaker_id}"
            self.dynamic_speakers[fallback_label] = {
                "embedding": audio_embedding.copy(),
                "count": 1,
                "last_seen": datetime.now().isoformat()
            }
            self.next_speaker_id += 1
            return {
                "speaker_label": fallback_label,
                "speaker_type": "dynamic",
                "confidence": 0.0,
                "speaker_info": {
                    "speaker_id": fallback_label,
                    "speaker_name": fallback_label,
                    "speaker_type": "dynamic",
                    "count": 1,
                    "last_seen": self.dynamic_speakers[fallback_label]["last_seen"]
                },
                "top_3_candidates": [],  # 回退情况下没有候选人信息
                "message": f"回退创建临时说话人: {fallback_label}"
            }
    
    def _assign_dynamic_label(self, audio_embedding: np.ndarray) -> str:
        """
        基于音频特征向量分配动态标签
        按照用户要求：说话人1、说话人2、说话人3...的顺序分配
        
        Args:
            audio_embedding: 音频特征向量
            
        Returns:
            分配的动态标签
        """
        try:
            # 按说话人编号顺序检查现有动态说话人
            for i in range(1, self.next_speaker_id):
                label = f"说话人{i}"
                if label in self.dynamic_speakers:
                    speaker_data = self.dynamic_speakers[label]
                    similarity = cosine_similarity(
                        audio_embedding.reshape(1, -1),
                        speaker_data["embedding"].reshape(1, -1)
                    )[0][0]
                    
                    # 如果与现有说话人相似度足够高，使用该标签
                    if similarity >= self.consistency_threshold:
                        # 更新该说话人的信息
                        self.dynamic_speakers[label]["count"] += 1
                        self.dynamic_speakers[label]["last_seen"] = datetime.now().isoformat()
                        
                        # 使用加权平均更新特征向量
                        old_embedding = self.dynamic_speakers[label]["embedding"]
                        count = self.dynamic_speakers[label]["count"]
                        weight = min(0.3, 1.0 / count)  # 新样本权重，随着样本增多而减小
                        self.dynamic_speakers[label]["embedding"] = (
                            (1 - weight) * old_embedding + weight * audio_embedding
                        )
                        
                        logger.debug(f"匹配到现有动态说话人: {label} (相似度: {similarity:.3f})")
                        return label
            
            # 如果没有匹配的现有说话人，创建新的动态说话人
            new_label = f"说话人{self.next_speaker_id}"
            self.dynamic_speakers[new_label] = {
                "embedding": audio_embedding.copy(),
                "count": 1,
                "last_seen": datetime.now().isoformat()
            }
            self.next_speaker_id += 1
            
            logger.debug(f"创建新动态说话人: {new_label}")
            return new_label
            
        except Exception as e:
            logger.error(f"分配动态标签失败: {e}")
            # 回退到简单标签
            fallback_label = f"说话人{self.next_speaker_id}"
            self.next_speaker_id += 1
            return fallback_label
    
    def _assign_dynamic_label_from_candidates(self, candidates: List[Dict]) -> str:
        """
        基于候选人信息分配动态标签（当没有音频特征向量时）
        使用候选人相似度模式进行智能分配和一致性检查
        
        Args:
            candidates: 候选说话人列表
            
        Returns:
            分配的动态标签
        """
        try:
            if not candidates:
                # 没有候选人，直接创建新标签
                new_label = f"说话人{self.next_speaker_id}"
                self.next_speaker_id += 1
                logger.debug(f"无候选人，创建新动态说话人: {new_label}")
                return new_label
            
            # 获取候选人的相似度向量作为"指纹"
            current_pattern = [c.get("similarity", 0) for c in candidates[:3]]  # 取前3个作为模式
            
            # 检查是否与现有动态说话人的模式匹配
            best_match_label = None
            best_pattern_similarity = 0.0
            
            for i in range(1, self.next_speaker_id):
                label = f"说话人{i}"
                if label in self.dynamic_speakers:
                    speaker_data = self.dynamic_speakers[label]
                    
                    # 如果之前存储了相似度模式，进行比较
                    if "similarity_pattern" in speaker_data:
                        stored_pattern = speaker_data["similarity_pattern"]
                        
                        # 计算模式相似度（使用余弦相似度或简单的差值比较）
                        pattern_similarity = self._calculate_pattern_similarity(current_pattern, stored_pattern)
                        
                        if pattern_similarity > best_pattern_similarity:
                            best_pattern_similarity = pattern_similarity
                            best_match_label = label
            
            # 如果找到足够相似的模式，使用现有标签
            if best_match_label and best_pattern_similarity >= self.consistency_threshold:
                # 更新该说话人的信息
                self.dynamic_speakers[best_match_label]["count"] += 1
                self.dynamic_speakers[best_match_label]["last_seen"] = datetime.now().isoformat()
                
                # 更新相似度模式（加权平均）
                old_pattern = self.dynamic_speakers[best_match_label]["similarity_pattern"]
                count = self.dynamic_speakers[best_match_label]["count"]
                weight = min(0.3, 1.0 / count)
                
                # 计算新的加权平均模式
                new_pattern = []
                for i in range(min(len(current_pattern), len(old_pattern))):
                    new_val = (1 - weight) * old_pattern[i] + weight * current_pattern[i]
                    new_pattern.append(new_val)
                
                self.dynamic_speakers[best_match_label]["similarity_pattern"] = new_pattern
                
                logger.debug(f"匹配到现有动态说话人: {best_match_label} (模式相似度: {best_pattern_similarity:.3f})")
                return best_match_label
            
            # 创建新的动态说话人
            new_label = f"说话人{self.next_speaker_id}"
            self.dynamic_speakers[new_label] = {
                "similarity_pattern": current_pattern,
                "count": 1,
                "last_seen": datetime.now().isoformat()
            }
            self.next_speaker_id += 1
            
            logger.debug(f"创建新动态说话人: {new_label} (模式: {current_pattern})")
            return new_label
            
        except Exception as e:
            logger.error(f"基于候选人分配标签失败: {e}")
            # 回退处理
            fallback_label = f"说话人{self.next_speaker_id}"
            self.next_speaker_id += 1
            return fallback_label
    
    def _calculate_pattern_similarity(self, pattern1: List[float], pattern2: List[float]) -> float:
        """
        计算两个相似度模式的相似度
        
        Args:
            pattern1: 第一个相似度模式
            pattern2: 第二个相似度模式
            
        Returns:
            模式相似度 (0.0-1.0)
        """
        try:
            if not pattern1 or not pattern2:
                return 0.0
            
            # 确保两个模式长度相同
            min_len = min(len(pattern1), len(pattern2))
            p1 = pattern1[:min_len]
            p2 = pattern2[:min_len]
            
            # 使用余弦相似度计算
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            
            if np.sum(p1) == 0 or np.sum(p2) == 0:
                return 0.0
            
            similarity = cosine_similarity([p1], [p2])[0][0]
            return max(0.0, similarity)  # 确保非负
            
        except Exception as e:
            logger.error(f"计算模式相似度失败: {e}")
            # 回退到简单的差值比较
            try:
                if len(pattern1) != len(pattern2):
                    return 0.0
                
                total_diff = sum(abs(a - b) for a, b in zip(pattern1, pattern2))
                max_diff = len(pattern1) * 1.0  # 最大可能差值
                similarity = 1.0 - (total_diff / max_diff)
                return max(0.0, similarity)
            except:
                return 0.0
    
    def get_dynamic_speakers_info(self) -> Dict:
        """
        获取所有动态说话人信息
        
        Returns:
            动态说话人信息字典
        """
        info = {}
        for label, data in self.dynamic_speakers.items():
            info[label] = {
                "count": data["count"],
                "last_seen": data["last_seen"],
                "similarity_pattern": data.get("similarity_pattern", []),
                "embedding_shape": data["embedding"].shape if "embedding" in data else "N/A"
            }
        return info
    
    def reset_dynamic_speakers(self):
        """
        重置所有动态说话人标签
        """
        self.dynamic_speakers.clear()
        self.next_speaker_id = 1
        logger.info("动态说话人标签已重置")
    
    def set_thresholds(self, similarity_threshold: float = None, consistency_threshold: float = None):
        """
        设置阈值参数
        
        Args:
            similarity_threshold: 已注册说话人匹配的相似度阈值
            consistency_threshold: 动态标签一致性检查的相似度阈值（也用于模式匹配）
        """
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
            logger.info(f"相似度阈值更新为: {similarity_threshold}")
        
        if consistency_threshold is not None:
            self.consistency_threshold = consistency_threshold
            logger.info(f"一致性阈值更新为: {consistency_threshold}（用于模式匹配）")


# 全局说话人标记器实例
_global_speaker_labeler = None


def get_speaker_labeler() -> SpeakerLabeler:
    """
    获取全局说话人标记器实例
    
    Returns:
        SpeakerLabeler实例
    """
    global _global_speaker_labeler
    if _global_speaker_labeler is None:
        _global_speaker_labeler = SpeakerLabeler()
    return _global_speaker_labeler


def init_speaker_labeler(similarity_threshold: float = 0.7, consistency_threshold: float = 0.5):
    """
    初始化全局说话人标记器
    
    Args:
        similarity_threshold: 已注册说话人匹配的相似度阈值
        consistency_threshold: 动态标签一致性检查的相似度阈值（也用于模式匹配）
    """
    global _global_speaker_labeler
    _global_speaker_labeler = SpeakerLabeler(similarity_threshold, consistency_threshold)
    logger.info("全局说话人标记器初始化完成")


def process_speaker_identification(speaker_result: Dict, audio_embedding: Optional[np.ndarray] = None) -> Dict:
    """
    处理说话人识别结果的便利函数
    
    Args:
        speaker_result: identify_speaker函数的返回结果
        audio_embedding: 音频特征向量（可选）
        
    Returns:
        处理后的说话人信息字典
    """
    labeler = get_speaker_labeler()
    return labeler.process_speaker_result(speaker_result, audio_embedding)


def reset_speaker_labels():
    """
    重置所有动态说话人标签的便利函数
    """
    labeler = get_speaker_labeler()
    labeler.reset_dynamic_speakers()


def get_speaker_labels_info() -> Dict:
    """
    获取说话人标签信息的便利函数
    
    Returns:
        说话人标签信息字典
    """
    labeler = get_speaker_labeler()
    return labeler.get_dynamic_speakers_info()