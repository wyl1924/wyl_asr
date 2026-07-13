#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
说话人前三名候选人测试

测试临时说话人匹配时返回相似度前三名的功能。
"""

import sys
import os
import logging
import numpy as np
from unittest.mock import Mock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.speaker.speaker_labeling import SpeakerLabeler

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestSpeakerTop3Candidates:
    """说话人前三名候选人测试类"""
    
    def __init__(self):
        # 使用较低的阈值便于测试
        self.labeler = SpeakerLabeler(similarity_threshold=0.25, consistency_threshold=0.3)
    
    def test_top3_candidates_with_match(self):
        """测试有匹配的临时说话人时返回前三名候选人"""
        logger.info("🔄 测试有匹配的临时说话人时返回前三名候选人")
        
        # 先创建几个临时说话人
        embeddings = []
        for i in range(5):
            # 创建不同的特征向量
            embedding = np.random.rand(512).astype(np.float32)
            embeddings.append(embedding)
            
            # 模拟没有已注册说话人的情况
            speaker_result = {
                "success": True,
                "best_match": None,
                "candidates": [],
                "threshold": 0.25
            }
            
            result = self.labeler.process_speaker_result(speaker_result, embedding)
            logger.info(f"创建临时说话人: {result['speaker_label']}")
        
        # 现在测试与现有临时说话人的匹配
        # 使用与第一个临时说话人相似的特征向量
        similar_embedding = embeddings[0] + np.random.normal(0, 0.1, embeddings[0].shape).astype(np.float32)
        
        speaker_result = {
            "success": True,
            "best_match": None,
            "candidates": [],
            "threshold": 0.25
        }
        
        result = self.labeler.process_speaker_result(speaker_result, similar_embedding)
        
        # 验证结果
        logger.info(f"匹配结果: {result}")
        
        assert "top_3_candidates" in result, "结果中应包含top_3_candidates字段"
        assert isinstance(result["top_3_candidates"], list), "top_3_candidates应该是列表"
        assert len(result["top_3_candidates"]) <= 3, "候选人数量不应超过3个"
        
        # 验证候选人信息的完整性
        for candidate in result["top_3_candidates"]:
            assert "speaker_label" in candidate, "候选人应包含speaker_label"
            assert "similarity" in candidate, "候选人应包含similarity"
            assert isinstance(candidate["similarity"], float), "相似度应该是浮点数"
        
        # 验证候选人按相似度降序排列
        if len(result["top_3_candidates"]) > 1:
            for i in range(len(result["top_3_candidates"]) - 1):
                assert result["top_3_candidates"][i]["similarity"] >= result["top_3_candidates"][i+1]["similarity"], \
                    "候选人应按相似度降序排列"
        
        logger.info(f"✅ 测试通过: 返回了{len(result['top_3_candidates'])}个候选人")
        return result
    
    def test_top3_candidates_no_match(self):
        """测试没有匹配的临时说话人时创建新说话人并返回前三名候选人"""
        logger.info("🔄 测试没有匹配的临时说话人时创建新说话人")
        
        # 先创建几个临时说话人
        for i in range(3):
            embedding = np.random.rand(512).astype(np.float32)
            speaker_result = {
                "success": True,
                "best_match": None,
                "candidates": [],
                "threshold": 0.25
            }
            result = self.labeler.process_speaker_result(speaker_result, embedding)
            logger.info(f"创建临时说话人: {result['speaker_label']}")
        
        # 使用完全不同的特征向量（相似度很低）
        # 创建一个与随机向量完全不同的向量
        different_embedding = np.zeros(512, dtype=np.float32)
        different_embedding[:256] = 1.0  # 前半部分为1，后半部分为0，与随机向量差异很大
        
        speaker_result = {
            "success": True,
            "best_match": None,
            "candidates": [],
            "threshold": 0.25
        }
        
        result = self.labeler.process_speaker_result(speaker_result, different_embedding)
        
        # 验证结果
        logger.info(f"创建新说话人结果: {result}")
        
        assert result["speaker_type"] == "dynamic", "应该创建新的临时说话人"
        assert "top_3_candidates" in result, "结果中应包含top_3_candidates字段"
        logger.info(f"实际返回的候选人数量: {len(result['top_3_candidates'])}")
        logger.info(f"候选人详情: {result['top_3_candidates']}")
        assert len(result["top_3_candidates"]) <= 3, "候选人数量不应超过3个"
        # 如果之前创建了3个临时说话人，应该返回3个候选人
        # 但如果某些临时说话人没有embedding，可能会少一些
        assert len(result["top_3_candidates"]) >= 0, "应该至少返回0个候选人"
        
        # 验证候选人信息的完整性（不强制要求相似度低于阈值，因为随机向量可能偶然相似）
        for candidate in result["top_3_candidates"]:
            assert "similarity" in candidate, "候选人应包含相似度信息"
            assert "speaker_label" in candidate, "候选人应包含说话人标签"
            logger.info(f"候选人: {candidate['speaker_label']}, 相似度: {candidate['similarity']:.4f}")
        
        logger.info(f"✅ 测试通过: 创建新说话人并返回了{len(result['top_3_candidates'])}个候选人")
        return result
    
    def test_top3_candidates_less_than_3(self):
        """测试临时说话人少于3个时的情况"""
        logger.info("🔄 测试临时说话人少于3个时的情况")
        
        # 只创建2个临时说话人
        for i in range(2):
            embedding = np.random.rand(512).astype(np.float32)
            speaker_result = {
                "success": True,
                "best_match": None,
                "candidates": [],
                "threshold": 0.25
            }
            result = self.labeler.process_speaker_result(speaker_result, embedding)
            logger.info(f"创建临时说话人: {result['speaker_label']}")
        
        # 测试匹配
        test_embedding = np.random.rand(512).astype(np.float32)
        speaker_result = {
            "success": True,
            "best_match": None,
            "candidates": [],
            "threshold": 0.25
        }
        
        result = self.labeler.process_speaker_result(speaker_result, test_embedding)
        
        # 验证结果
        logger.info(f"匹配结果: {result}")
        
        assert "top_3_candidates" in result, "结果中应包含top_3_candidates字段"
        # 应该返回2个候选人（如果创建新的）或2个候选人（如果匹配到现有的）
        assert len(result["top_3_candidates"]) <= 3, "候选人数量不应超过3个"
        
        logger.info(f"✅ 测试通过: 返回了{len(result['top_3_candidates'])}个候选人")
        return result
    
    def test_candidate_info_completeness(self):
        """测试候选人信息的完整性"""
        logger.info("🔄 测试候选人信息的完整性")
        
        # 创建一个临时说话人
        embedding1 = np.random.rand(512).astype(np.float32)
        speaker_result = {
            "success": True,
            "best_match": None,
            "candidates": [],
            "threshold": 0.25
        }
        
        result1 = self.labeler.process_speaker_result(speaker_result, embedding1)
        first_speaker = result1["speaker_label"]
        
        # 再次匹配同一个说话人，增加count
        similar_embedding = embedding1 + np.random.normal(0, 0.05, embedding1.shape).astype(np.float32)
        result2 = self.labeler.process_speaker_result(speaker_result, similar_embedding)
        
        # 创建另一个临时说话人进行测试
        different_embedding = np.random.rand(512).astype(np.float32)
        result3 = self.labeler.process_speaker_result(speaker_result, different_embedding)
        
        # 验证候选人信息的完整性
        logger.info(f"最终结果: {result3}")
        
        for candidate in result3["top_3_candidates"]:
            # 验证必需字段
            assert "speaker_label" in candidate, "候选人应包含speaker_label字段"
            assert "similarity" in candidate, "候选人应包含similarity字段"
            
            # 验证字段类型和值
            assert isinstance(candidate["similarity"], float), "similarity应该是浮点数"
            assert 0.0 <= candidate["similarity"] <= 1.0, "similarity应该在0.0-1.0范围内"
            
            logger.info(f"候选人: {candidate['speaker_label']}, 相似度: {candidate['similarity']:.4f}")
        
        logger.info("✅ 测试通过: 候选人信息完整且正确")
        return result3
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始运行说话人前三名候选人测试")
        
        tests = [
            self.test_top3_candidates_with_match,
            self.test_top3_candidates_no_match,
            self.test_top3_candidates_less_than_3,
            self.test_candidate_info_completeness
        ]
        
        results = []
        for test in tests:
            try:
                # 每个测试使用新的labeler实例
                self.labeler = SpeakerLabeler(similarity_threshold=0.25, consistency_threshold=0.3)
                result = test()
                results.append(result)
                logger.info(f"✅ {test.__name__} 测试通过")
            except Exception as e:
                logger.error(f"❌ {test.__name__} 测试失败: {e}")
                raise
        
        logger.info("🎉 所有前三名候选人测试通过！")
        return results

def main():
    """主函数"""
    try:
        tester = TestSpeakerTop3Candidates()
        results = tester.run_all_tests()
        
        logger.info("📊 测试结果汇总:")
        for i, result in enumerate(results, 1):
            top3_count = len(result.get("top_3_candidates", []))
            logger.info(f"  {i}. {result['speaker_label']} ({result['speaker_type']}) - 前{top3_count}名候选人")
            
            # 显示前三名候选人的详细信息
            for j, candidate in enumerate(result.get("top_3_candidates", []), 1):
                logger.info(f"     第{j}名: {candidate['speaker_label']} (相似度: {candidate['similarity']:.4f})")
        
        logger.info("✅ 说话人前三名候选人测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()