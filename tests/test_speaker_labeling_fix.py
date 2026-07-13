#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
说话人标记修复测试

测试修复后的说话人标记逻辑，特别是当没有已注册说话人时的处理。
"""

import sys
import os
import logging
import asyncio
from unittest.mock import Mock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.speaker.speaker_labeling import SpeakerLabeler, process_speaker_identification

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestSpeakerLabelingFix:
    """说话人标记修复测试类"""
    
    def __init__(self):
        self.labeler = SpeakerLabeler(similarity_threshold=0.7, consistency_threshold=0.5)
    
    def test_no_registered_speakers(self):
        """测试没有已注册说话人的情况"""
        logger.info("🔄 测试没有已注册说话人的情况")
        
        # 模拟identify_speaker返回的结果（没有已注册说话人）
        speaker_result = {
            "success": False,
            "message": "没有已注册的说话人",
            "candidates": []
        }
        
        # 创建模拟的音频特征向量
        import numpy as np
        audio_embedding = np.random.rand(512).astype(np.float32)  # 模拟512维特征向量
        
        # 处理结果
        result = self.labeler.process_speaker_result(speaker_result, audio_embedding)
        
        # 验证结果
        assert result["speaker_type"] == "dynamic", f"期望speaker_type为dynamic，实际为{result['speaker_type']}"
        assert result["speaker_label"].startswith("说话人"), f"期望speaker_label以'说话人'开头，实际为{result['speaker_label']}"
        assert "临时说话人" in result["message"], f"期望message包含'临时说话人'，实际为{result['message']}"
        
        logger.info(f"✅ 测试通过: {result}")
        return result
    
    def test_identification_failure(self):
        """测试识别失败的情况"""
        logger.info("🔄 测试识别失败的情况")
        
        # 模拟identify_speaker返回的结果（特征提取失败）
        speaker_result = {
            "success": False,
            "message": "特征提取失败: 音频文件损坏",
            "candidates": []
        }
        
        # 处理结果
        result = self.labeler.process_speaker_result(speaker_result)
        
        # 验证结果
        assert result["speaker_type"] == "unknown", f"期望speaker_type为unknown，实际为{result['speaker_type']}"
        assert result["speaker_label"] == "未知说话人", f"期望speaker_label为'未知说话人'，实际为{result['speaker_label']}"
        assert "说话人识别失败" in result["message"], f"期望message包含'说话人识别失败'，实际为{result['message']}"
        
        logger.info(f"✅ 测试通过: {result}")
        return result
    
    def test_no_result(self):
        """测试完全没有识别结果的情况"""
        logger.info("🔄 测试完全没有识别结果的情况")
        
        # 创建模拟的音频特征向量
        import numpy as np
        audio_embedding = np.random.rand(512).astype(np.float32)
        
        # 处理空结果
        result = self.labeler.process_speaker_result(None, audio_embedding)
        
        # 验证结果
        assert result["speaker_type"] == "dynamic", f"期望speaker_type为dynamic，实际为{result['speaker_type']}"
        assert result["speaker_label"].startswith("说话人"), f"期望speaker_label以'说话人'开头，实际为{result['speaker_label']}"
        assert "临时说话人" in result["message"], f"期望message包含'临时说话人'，实际为{result['message']}"
        
        logger.info(f"✅ 测试通过: {result}")
        return result
    
    def test_successful_identification(self):
        """测试成功识别已注册说话人的情况"""
        logger.info("🔄 测试成功识别已注册说话人的情况")
        
        # 模拟identify_speaker返回的结果（成功识别）
        speaker_result = {
            "success": True,
            "best_match": {
                "speaker_name": "张三",
                "similarity": 0.85,
                "speaker_info": {"id": "001"}
            },
            "candidates": [
                {
                    "speaker_name": "张三",
                    "similarity": 0.85,
                    "speaker_info": {"id": "001"}
                }
            ],
            "threshold": 0.7
        }
        
        # 处理结果
        result = self.labeler.process_speaker_result(speaker_result)
        
        # 验证结果
        assert result["speaker_type"] == "registered", f"期望speaker_type为registered，实际为{result['speaker_type']}"
        assert result["speaker_label"] == "张三", f"期望speaker_label为'张三'，实际为{result['speaker_label']}"
        assert result["confidence"] == 0.85, f"期望confidence为0.85，实际为{result['confidence']}"
        
        logger.info(f"✅ 测试通过: {result}")
        return result
    
    def test_low_similarity_candidates(self):
        """测试候选人相似度都低于阈值的情况"""
        logger.info("🔄 测试候选人相似度都低于阈值的情况")
        
        # 模拟identify_speaker返回的结果（有候选人但相似度都很低）
        speaker_result = {
            "success": True,
            "best_match": None,
            "candidates": [
                {
                    "speaker_name": "张三",
                    "similarity": 0.5,  # 低于阈值0.7
                    "speaker_info": {"id": "001"}
                },
                {
                    "speaker_name": "李四",
                    "similarity": 0.4,  # 低于阈值0.7
                    "speaker_info": {"id": "002"}
                }
            ],
            "threshold": 0.7
        }
        
        # 创建模拟的音频特征向量
        import numpy as np
        audio_embedding = np.random.rand(512).astype(np.float32)
        
        # 处理结果
        result = self.labeler.process_speaker_result(speaker_result, audio_embedding)
        
        # 验证结果
        assert result["speaker_type"] == "dynamic", f"期望speaker_type为dynamic，实际为{result['speaker_type']}"
        assert result["speaker_label"].startswith("说话人"), f"期望speaker_label以'说话人'开头，实际为{result['speaker_label']}"
        assert "临时说话人" in result["message"], f"期望message包含'临时说话人'，实际为{result['message']}"
        
        logger.info(f"✅ 测试通过: {result}")
        return result
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始运行说话人标记修复测试")
        
        tests = [
            self.test_no_registered_speakers,
            self.test_identification_failure,
            self.test_no_result,
            self.test_successful_identification,
            self.test_low_similarity_candidates
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
        
        logger.info("🎉 所有测试通过！")
        return results

def main():
    """主函数"""
    try:
        tester = TestSpeakerLabelingFix()
        results = tester.run_all_tests()
        
        logger.info("📊 测试结果汇总:")
        for i, result in enumerate(results, 1):
            logger.info(f"  {i}. {result['speaker_label']} ({result['speaker_type']}) - {result['message']}")
        
        logger.info("✅ 说话人标记修复测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()