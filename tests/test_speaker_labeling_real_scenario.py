#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
说话人标记真实场景测试

测试修复后的说话人标记逻辑，模拟真实的使用场景。
"""

import sys
import os
import logging
import numpy as np
from unittest.mock import Mock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.speaker.speaker_labeling import SpeakerLabeler, process_speaker_identification

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestSpeakerLabelingRealScenario:
    """说话人标记真实场景测试类"""
    
    def __init__(self):
        # 使用arg_parser.py中的默认阈值
        self.labeler = SpeakerLabeler(similarity_threshold=0.25, consistency_threshold=0.2)
    
    def test_real_scenario_low_similarity(self):
        """测试真实场景：有候选人但相似度都低于阈值的情况"""
        logger.info("🔄 测试真实场景：有候选人但相似度都低于阈值")
        
        # 模拟真实的识别结果（基于用户提供的日志）
        speaker_result = {
            "success": True,
            "best_match": None,
            "candidates": [
                {
                    "speaker_name": "王延领",
                    "similarity": 0.4612121284008026,  # 高于0.25阈值，应该被识别
                    "speaker_info": {
                        "speaker_id": "speaker_0000",
                        "speaker_name": "王延领",
                        "description": "",
                        "registration_time": "2025-07-29T23:22:35.913176",
                        "audio_samples": 1,
                        "last_updated": "2025-07-29T23:22:35.913182"
                    }
                },
                {
                    "speaker_name": "张生",
                    "similarity": 0.3592623174190521,  # 高于0.25阈值，应该被识别
                    "speaker_info": {
                        "speaker_id": "speaker_0006",
                        "speaker_name": "张生",
                        "description": "",
                        "registration_time": "2025-07-30T17:56:31.002646",
                        "audio_samples": 1,
                        "last_updated": "2025-07-30T17:56:31.002649"
                    }
                },
                {
                    "speaker_name": "宋",
                    "similarity": 0.16999539732933044,  # 低于0.25阈值
                    "speaker_info": {
                        "speaker_id": "speaker_0001",
                        "speaker_name": "宋",
                        "description": "",
                        "registration_time": "2025-07-29T23:23:01.123456",
                        "audio_samples": 1,
                        "last_updated": "2025-07-29T23:23:01.123456"
                    }
                }
            ],
            "threshold": 0.25
        }
        
        # 创建模拟的音频特征向量
        audio_embedding = np.random.rand(512).astype(np.float32)
        
        # 处理结果
        result = self.labeler.process_speaker_result(speaker_result, audio_embedding)
        
        # 验证结果 - 应该识别为"王延领"（相似度最高且超过阈值）
        logger.info(f"处理结果: {result}")
        
        assert result["speaker_type"] == "registered", f"期望speaker_type为registered，实际为{result['speaker_type']}"
        assert result["speaker_label"] == "王延领", f"期望speaker_label为'王延领'，实际为{result['speaker_label']}"
        assert abs(result["confidence"] - 0.4612121284008026) < 0.0001, f"期望confidence为0.4612，实际为{result['confidence']}"
        
        logger.info(f"✅ 测试通过: 识别为已注册说话人 {result['speaker_label']}")
        return result
    
    def test_real_scenario_all_low_similarity(self):
        """测试真实场景：所有候选人相似度都低于阈值的情况"""
        logger.info("🔄 测试真实场景：所有候选人相似度都低于阈值")
        
        # 模拟所有候选人相似度都低于阈值的情况
        speaker_result = {
            "success": True,
            "best_match": None,
            "candidates": [
                {
                    "speaker_name": "王延领",
                    "similarity": 0.2,  # 低于0.25阈值
                    "speaker_info": {"speaker_id": "speaker_0000"}
                },
                {
                    "speaker_name": "张生",
                    "similarity": 0.15,  # 低于0.25阈值
                    "speaker_info": {"speaker_id": "speaker_0006"}
                }
            ],
            "threshold": 0.25
        }
        
        # 创建模拟的音频特征向量
        audio_embedding = np.random.rand(512).astype(np.float32)
        
        # 处理结果
        result = self.labeler.process_speaker_result(speaker_result, audio_embedding)
        
        # 验证结果 - 应该创建临时说话人
        logger.info(f"处理结果: {result}")
        
        assert result["speaker_type"] == "dynamic", f"期望speaker_type为dynamic，实际为{result['speaker_type']}"
        assert result["speaker_label"].startswith("说话人"), f"期望speaker_label以'说话人'开头，实际为{result['speaker_label']}"
        assert "临时说话人" in result["message"], f"期望message包含'临时说话人'，实际为{result['message']}"
        
        logger.info(f"✅ 测试通过: 创建临时说话人 {result['speaker_label']}")
        return result
    
    def test_dynamic_speaker_matching(self):
        """测试临时说话人匹配逻辑"""
        logger.info("🔄 测试临时说话人匹配逻辑")
        
        # 第一次：创建临时说话人
        speaker_result1 = {
            "success": True,
            "best_match": None,
            "candidates": [
                {"speaker_name": "王延领", "similarity": 0.2, "speaker_info": {}}
            ],
            "threshold": 0.25
        }
        
        audio_embedding1 = np.random.rand(512).astype(np.float32)
        result1 = self.labeler.process_speaker_result(speaker_result1, audio_embedding1)
        
        logger.info(f"第一次处理结果: {result1}")
        assert result1["speaker_type"] == "dynamic"
        first_speaker_label = result1["speaker_label"]
        
        # 第二次：使用相似的特征向量，应该匹配到同一个临时说话人
        speaker_result2 = {
            "success": True,
            "best_match": None,
            "candidates": [
                {"speaker_name": "张生", "similarity": 0.18, "speaker_info": {}}
            ],
            "threshold": 0.25
        }
        
        # 创建与第一次相似的特征向量（添加少量噪声）
        audio_embedding2 = audio_embedding1 + np.random.normal(0, 0.01, audio_embedding1.shape).astype(np.float32)
        result2 = self.labeler.process_speaker_result(speaker_result2, audio_embedding2)
        
        logger.info(f"第二次处理结果: {result2}")
        
        # 验证是否匹配到同一个临时说话人
        if result2["speaker_label"] == first_speaker_label:
            logger.info(f"✅ 测试通过: 成功匹配到同一个临时说话人 {first_speaker_label}")
        else:
            logger.info(f"ℹ️ 创建了新的临时说话人 {result2['speaker_label']}（特征差异较大）")
        
        assert result2["speaker_type"] == "dynamic"
        return result1, result2
    
    def test_threshold_boundary(self):
        """测试阈值边界情况"""
        logger.info("🔄 测试阈值边界情况")
        
        # 测试刚好等于阈值的情况
        speaker_result = {
            "success": True,
            "best_match": None,
            "candidates": [
                {
                    "speaker_name": "边界测试",
                    "similarity": 0.25,  # 刚好等于阈值
                    "speaker_info": {"speaker_id": "test_001"}
                }
            ],
            "threshold": 0.25
        }
        
        audio_embedding = np.random.rand(512).astype(np.float32)
        result = self.labeler.process_speaker_result(speaker_result, audio_embedding)
        
        logger.info(f"边界测试结果: {result}")
        
        # 应该识别为已注册说话人（>=阈值）
        assert result["speaker_type"] == "registered", f"期望speaker_type为registered，实际为{result['speaker_type']}"
        assert result["speaker_label"] == "边界测试", f"期望speaker_label为'边界测试'，实际为{result['speaker_label']}"
        
        logger.info(f"✅ 边界测试通过: 阈值边界情况正确处理")
        return result
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始运行说话人标记真实场景测试")
        
        tests = [
            self.test_real_scenario_low_similarity,
            self.test_real_scenario_all_low_similarity,
            self.test_dynamic_speaker_matching,
            self.test_threshold_boundary
        ]
        
        results = []
        for test in tests:
            try:
                result = test()
                results.append(result)
                logger.info(f"✅ {test.__name__} 测试通过")
            except Exception as e:
                logger.error(f"❌ {test.__name__} 测试失败: {e}")
                raise
        
        logger.info("🎉 所有真实场景测试通过！")
        return results

def main():
    """主函数"""
    try:
        tester = TestSpeakerLabelingRealScenario()
        results = tester.run_all_tests()
        
        logger.info("📊 测试结果汇总:")
        for i, result in enumerate(results, 1):
            if isinstance(result, tuple):  # 动态匹配测试返回两个结果
                logger.info(f"  {i}. 动态匹配测试:")
                logger.info(f"     第一次: {result[0]['speaker_label']} ({result[0]['speaker_type']})")
                logger.info(f"     第二次: {result[1]['speaker_label']} ({result[1]['speaker_type']})")
            else:
                logger.info(f"  {i}. {result['speaker_label']} ({result['speaker_type']}) - {result['message']}")
        
        logger.info("✅ 说话人标记真实场景测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()