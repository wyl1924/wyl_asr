#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热词管理器测试模块

测试热词管理器的各项功能，包括：
1. 热词的添加、删除、更新
2. 热词分类管理
3. 热词格式转换
4. 热词导入导出
5. 热词持久化存储
6. 热词统计信息
"""

import unittest
import tempfile
import os
import json
from unittest.mock import patch, MagicMock
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.hotword_manager import HotwordManager, Hotword, get_hotword_manager, init_hotword_manager


class TestHotword(unittest.TestCase):
    """测试Hotword数据类"""
    
    def test_hotword_creation(self):
        """测试热词对象创建"""
        hotword = Hotword("测试词", 5.0, "测试", "测试描述")
        
        self.assertEqual(hotword.word, "测试词")
        self.assertEqual(hotword.weight, 5.0)
        self.assertEqual(hotword.category, "测试")
        self.assertEqual(hotword.description, "测试描述")
        self.assertIsNotNone(hotword.created_at)
        self.assertIsNotNone(hotword.updated_at)
    
    def test_hotword_to_dict(self):
        """测试热词对象转字典"""
        hotword = Hotword("测试词", 5.0, "测试", "测试描述")
        data = hotword.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data["word"], "测试词")
        self.assertEqual(data["weight"], 5.0)
        self.assertEqual(data["category"], "测试")
        self.assertEqual(data["description"], "测试描述")
    
    def test_hotword_from_dict(self):
        """测试从字典创建热词对象"""
        data = {
            "word": "测试词",
            "weight": 5.0,
            "category": "测试",
            "description": "测试描述",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00"
        }
        
        hotword = Hotword.from_dict(data)
        
        self.assertEqual(hotword.word, "测试词")
        self.assertEqual(hotword.weight, 5.0)
        self.assertEqual(hotword.category, "测试")
        self.assertEqual(hotword.description, "测试描述")


class TestHotwordManager(unittest.TestCase):
    """测试热词管理器"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时文件用于测试
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.manager = HotwordManager(self.temp_file.name)
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时文件
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_manager_initialization(self):
        """测试管理器初始化"""
        self.assertIsInstance(self.manager.hotwords, dict)
        self.assertIsInstance(self.manager.categories, dict)
        self.assertIn("default", self.manager.categories)
        self.assertEqual(self.manager.storage_path, self.temp_file.name)
    
    def test_add_hotword_success(self):
        """测试成功添加热词"""
        result = self.manager.add_hotword("人工智能", 5.0, "技术", "AI相关")
        
        self.assertTrue(result)
        self.assertIn("人工智能", self.manager.hotwords)
        self.assertIn("技术", self.manager.categories)
        self.assertIn("人工智能", self.manager.categories["技术"])
        
        hotword = self.manager.hotwords["人工智能"]
        self.assertEqual(hotword.word, "人工智能")
        self.assertEqual(hotword.weight, 5.0)
        self.assertEqual(hotword.category, "技术")
        self.assertEqual(hotword.description, "AI相关")
    
    def test_add_hotword_invalid_word(self):
        """测试添加无效热词"""
        # 空字符串
        result = self.manager.add_hotword("", 5.0)
        self.assertFalse(result)
        
        # 包含特殊字符
        result = self.manager.add_hotword("测试<>", 5.0)
        self.assertFalse(result)
        
        # 过长的字符串
        long_word = "a" * 100
        result = self.manager.add_hotword(long_word, 5.0)
        self.assertFalse(result)
    
    def test_add_hotword_invalid_weight(self):
        """测试添加无效权重的热词"""
        # 权重过小
        result = self.manager.add_hotword("测试", 0.5)
        self.assertFalse(result)
        
        # 权重过大
        result = self.manager.add_hotword("测试", 15.0)
        self.assertFalse(result)
    
    def test_add_hotword_duplicate(self):
        """测试添加重复热词"""
        # 第一次添加
        result1 = self.manager.add_hotword("测试", 5.0)
        self.assertTrue(result1)
        
        # 第二次添加（不覆盖）
        result2 = self.manager.add_hotword("测试", 6.0, overwrite=False)
        self.assertFalse(result2)
        self.assertEqual(self.manager.hotwords["测试"].weight, 5.0)
        
        # 第三次添加（覆盖）
        result3 = self.manager.add_hotword("测试", 6.0, overwrite=True)
        self.assertTrue(result3)
        self.assertEqual(self.manager.hotwords["测试"].weight, 6.0)
    
    def test_remove_hotword(self):
        """测试删除热词"""
        # 先添加热词
        self.manager.add_hotword("测试", 5.0, "技术")
        self.assertIn("测试", self.manager.hotwords)
        
        # 删除热词
        result = self.manager.remove_hotword("测试")
        self.assertTrue(result)
        self.assertNotIn("测试", self.manager.hotwords)
        self.assertNotIn("测试", self.manager.categories["技术"])
        
        # 删除不存在的热词
        result = self.manager.remove_hotword("不存在")
        self.assertFalse(result)
    
    def test_update_hotword(self):
        """测试更新热词"""
        # 先添加热词
        self.manager.add_hotword("测试", 5.0, "技术", "原描述")
        
        # 更新权重
        result = self.manager.update_hotword("测试", weight=6.0)
        self.assertTrue(result)
        self.assertEqual(self.manager.hotwords["测试"].weight, 6.0)
        
        # 更新分类
        result = self.manager.update_hotword("测试", category="新分类")
        self.assertTrue(result)
        self.assertEqual(self.manager.hotwords["测试"].category, "新分类")
        self.assertIn("测试", self.manager.categories["新分类"])
        self.assertNotIn("测试", self.manager.categories["技术"])
        
        # 更新描述
        result = self.manager.update_hotword("测试", description="新描述")
        self.assertTrue(result)
        self.assertEqual(self.manager.hotwords["测试"].description, "新描述")
        
        # 更新不存在的热词
        result = self.manager.update_hotword("不存在", weight=5.0)
        self.assertFalse(result)
    
    def test_get_hotword(self):
        """测试获取热词"""
        # 添加热词
        self.manager.add_hotword("测试", 5.0, "技术")
        
        # 获取存在的热词
        hotword = self.manager.get_hotword("测试")
        self.assertIsNotNone(hotword)
        self.assertEqual(hotword.word, "测试")
        
        # 获取不存在的热词
        hotword = self.manager.get_hotword("不存在")
        self.assertIsNone(hotword)
    
    def test_list_hotwords(self):
        """测试列出热词"""
        # 添加不同分类的热词
        self.manager.add_hotword("AI", 5.0, "技术")
        self.manager.add_hotword("机器学习", 4.0, "技术")
        self.manager.add_hotword("阿里巴巴", 5.0, "公司")
        
        # 列出所有热词
        all_hotwords = self.manager.list_hotwords()
        self.assertEqual(len(all_hotwords), 3)
        
        # 列出指定分类的热词
        tech_hotwords = self.manager.list_hotwords("技术")
        self.assertEqual(len(tech_hotwords), 2)
        
        company_hotwords = self.manager.list_hotwords("公司")
        self.assertEqual(len(company_hotwords), 1)
        
        # 列出不存在分类的热词
        empty_hotwords = self.manager.list_hotwords("不存在")
        self.assertEqual(len(empty_hotwords), 0)
    
    def test_list_categories(self):
        """测试列出分类"""
        # 初始只有default分类
        categories = self.manager.list_categories()
        self.assertIn("default", categories)
        
        # 添加不同分类的热词
        self.manager.add_hotword("AI", 5.0, "技术")
        self.manager.add_hotword("阿里巴巴", 5.0, "公司")
        
        categories = self.manager.list_categories()
        self.assertIn("技术", categories)
        self.assertIn("公司", categories)
    
    def test_get_hotwords_string_funasr(self):
        """测试获取FunASR格式热词字符串"""
        self.manager.add_hotword("AI", 5.0)
        self.manager.add_hotword("机器学习", 4.0)
        
        hotwords_str = self.manager.get_hotwords_string(format_type="funasr")
        
        # FunASR格式应该是 "词1 权重1 词2 权重2"
        self.assertIn("AI", hotwords_str)
        self.assertIn("5", hotwords_str)
        self.assertIn("机器学习", hotwords_str)
        self.assertIn("4", hotwords_str)
    
    def test_get_hotwords_string_simple(self):
        """测试获取简单格式热词字符串"""
        self.manager.add_hotword("AI", 5.0)
        self.manager.add_hotword("机器学习", 4.0)
        
        hotwords_str = self.manager.get_hotwords_string(format_type="simple")
        
        # 简单格式应该是逗号分隔
        self.assertIn("AI", hotwords_str)
        self.assertIn("机器学习", hotwords_str)
        self.assertIn(",", hotwords_str)
    
    def test_get_hotwords_string_json(self):
        """测试获取JSON格式热词字符串"""
        self.manager.add_hotword("AI", 5.0, "技术")
        
        hotwords_str = self.manager.get_hotwords_string(format_type="json")
        
        # 应该是有效的JSON
        data = json.loads(hotwords_str)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["word"], "AI")
        self.assertEqual(data[0]["weight"], 5.0)
        self.assertEqual(data[0]["category"], "技术")
    
    def test_parse_hotwords_string_funasr(self):
        """测试解析FunASR格式热词字符串"""
        hotwords_str = "AI 5 机器学习 4 深度学习 3"
        
        count = self.manager.parse_hotwords_string(hotwords_str, "导入")
        
        self.assertEqual(count, 3)
        self.assertIn("AI", self.manager.hotwords)
        self.assertIn("机器学习", self.manager.hotwords)
        self.assertIn("深度学习", self.manager.hotwords)
        
        self.assertEqual(self.manager.hotwords["AI"].weight, 5.0)
        self.assertEqual(self.manager.hotwords["机器学习"].weight, 4.0)
        self.assertEqual(self.manager.hotwords["深度学习"].weight, 3.0)
    
    def test_parse_hotwords_string_comma(self):
        """测试解析逗号分隔格式热词字符串"""
        hotwords_str = "AI,机器学习,深度学习"
        
        count = self.manager.parse_hotwords_string(hotwords_str, "导入")
        
        self.assertEqual(count, 3)
        self.assertIn("AI", self.manager.hotwords)
        self.assertIn("机器学习", self.manager.hotwords)
        self.assertIn("深度学习", self.manager.hotwords)
        
        # 默认权重应该是4.0
        self.assertEqual(self.manager.hotwords["AI"].weight, 4.0)
    
    def test_parse_hotwords_string_space(self):
        """测试解析空格分隔格式热词字符串"""
        hotwords_str = "AI 机器学习 深度学习"
        
        count = self.manager.parse_hotwords_string(hotwords_str, "导入")
        
        self.assertEqual(count, 3)
        self.assertIn("AI", self.manager.hotwords)
        self.assertIn("机器学习", self.manager.hotwords)
        self.assertIn("深度学习", self.manager.hotwords)
    
    def test_clear_category(self):
        """测试清空分类"""
        # 添加不同分类的热词
        self.manager.add_hotword("AI", 5.0, "技术")
        self.manager.add_hotword("机器学习", 4.0, "技术")
        self.manager.add_hotword("阿里巴巴", 5.0, "公司")
        
        # 清空技术分类
        count = self.manager.clear_category("技术")
        
        self.assertEqual(count, 2)
        self.assertNotIn("AI", self.manager.hotwords)
        self.assertNotIn("机器学习", self.manager.hotwords)
        self.assertIn("阿里巴巴", self.manager.hotwords)  # 其他分类不受影响
        
        # 清空不存在的分类
        count = self.manager.clear_category("不存在")
        self.assertEqual(count, 0)
    
    def test_clear_all(self):
        """测试清空所有热词"""
        # 添加热词
        self.manager.add_hotword("AI", 5.0, "技术")
        self.manager.add_hotword("阿里巴巴", 5.0, "公司")
        
        count = self.manager.clear_all()
        
        self.assertEqual(count, 2)
        self.assertEqual(len(self.manager.hotwords), 0)
        self.assertEqual(list(self.manager.categories.keys()), ["default"])
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        # 添加不同权重和分类的热词
        self.manager.add_hotword("AI", 5.0, "技术")
        self.manager.add_hotword("机器学习", 5.0, "技术")
        self.manager.add_hotword("深度学习", 4.0, "技术")
        self.manager.add_hotword("阿里巴巴", 5.0, "公司")
        
        stats = self.manager.get_statistics()
        
        self.assertEqual(stats["total_hotwords"], 4)
        self.assertEqual(stats["total_categories"], 3)  # default, 技术, 公司
        self.assertEqual(stats["categories"]["技术"]["count"], 3)
        self.assertEqual(stats["categories"]["公司"]["count"], 1)
        self.assertEqual(stats["weight_distribution"][5], 3)  # 3个权重为5的热词
        self.assertEqual(stats["weight_distribution"][4], 1)  # 1个权重为4的热词
    
    def test_save_and_load_hotwords(self):
        """测试保存和加载热词"""
        # 添加热词
        self.manager.add_hotword("AI", 5.0, "技术", "人工智能")
        self.manager.add_hotword("阿里巴巴", 5.0, "公司", "互联网公司")
        
        # 保存
        result = self.manager.save_hotwords()
        self.assertTrue(result)
        
        # 创建新的管理器实例并加载
        new_manager = HotwordManager(self.temp_file.name)
        
        # 验证加载的数据
        self.assertEqual(len(new_manager.hotwords), 2)
        self.assertIn("AI", new_manager.hotwords)
        self.assertIn("阿里巴巴", new_manager.hotwords)
        
        ai_hotword = new_manager.hotwords["AI"]
        self.assertEqual(ai_hotword.word, "AI")
        self.assertEqual(ai_hotword.weight, 5.0)
        self.assertEqual(ai_hotword.category, "技术")
        self.assertEqual(ai_hotword.description, "人工智能")


class TestHotwordManagerGlobalFunctions(unittest.TestCase):
    """测试热词管理器全局函数"""
    
    def setUp(self):
        """测试前准备"""
        # 重置全局管理器
        import src.modules.hotword_manager as hm
        hm._hotword_manager = None
    
    def test_get_hotword_manager(self):
        """测试获取全局热词管理器"""
        manager1 = get_hotword_manager()
        manager2 = get_hotword_manager()
        
        # 应该返回同一个实例
        self.assertIs(manager1, manager2)
        self.assertIsInstance(manager1, HotwordManager)
    
    def test_init_hotword_manager(self):
        """测试初始化热词管理器"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        temp_file.close()
        
        try:
            manager = init_hotword_manager(temp_file.name)
            
            self.assertIsInstance(manager, HotwordManager)
            self.assertEqual(manager.storage_path, temp_file.name)
            
            # 再次获取应该返回同一个实例
            manager2 = get_hotword_manager()
            self.assertIs(manager, manager2)
            
        finally:
            os.unlink(temp_file.name)
    
    @patch('src.modules.hotword_manager.get_hotword_manager')
    def test_convenience_functions(self, mock_get_manager):
        """测试便捷函数"""
        # 创建模拟管理器
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager
        
        # 导入便捷函数
        from src.modules.hotword_manager import (
            add_hotword, remove_hotword, get_hotwords_string,
            parse_hotwords_string, list_hotwords
        )
        
        # 测试add_hotword
        add_hotword("测试", 5.0, "技术", "描述", True)
        mock_manager.add_hotword.assert_called_once_with("测试", 5.0, "技术", "描述", True)
        
        # 测试remove_hotword
        remove_hotword("测试")
        mock_manager.remove_hotword.assert_called_once_with("测试")
        
        # 测试get_hotwords_string
        get_hotwords_string("技术", "funasr")
        mock_manager.get_hotwords_string.assert_called_once_with("技术", "funasr")
        
        # 测试parse_hotwords_string
        parse_hotwords_string("AI 5", "导入")
        mock_manager.parse_hotwords_string.assert_called_once_with("AI 5", "导入")
        
        # 测试list_hotwords
        list_hotwords("技术")
        mock_manager.list_hotwords.assert_called_once_with("技术")


class TestHotwordManagerIntegration(unittest.TestCase):
    """热词管理器集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.manager = HotwordManager(self.temp_file.name)
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_complete_workflow(self):
        """测试完整的工作流程"""
        # 1. 添加多个分类的热词
        tech_words = [("人工智能", 5.0), ("机器学习", 4.5), ("深度学习", 4.0)]
        company_words = [("阿里巴巴", 5.0), ("达摩院", 4.5)]
        
        for word, weight in tech_words:
            self.assertTrue(self.manager.add_hotword(word, weight, "技术"))
        
        for word, weight in company_words:
            self.assertTrue(self.manager.add_hotword(word, weight, "公司"))
        
        # 2. 验证添加结果
        self.assertEqual(len(self.manager.hotwords), 5)
        self.assertEqual(len(self.manager.list_hotwords("技术")), 3)
        self.assertEqual(len(self.manager.list_hotwords("公司")), 2)
        
        # 3. 测试格式转换
        funasr_str = self.manager.get_hotwords_string("技术", "funasr")
        self.assertIn("人工智能", funasr_str)
        self.assertIn("5", funasr_str)
        
        simple_str = self.manager.get_hotwords_string("公司", "simple")
        self.assertIn("阿里巴巴", simple_str)
        self.assertIn("达摩院", simple_str)
        
        # 4. 测试导入导出
        export_str = self.manager.get_hotwords_string("技术", "funasr")
        
        # 清空技术分类
        self.manager.clear_category("技术")
        self.assertEqual(len(self.manager.list_hotwords("技术")), 0)
        
        # 重新导入
        count = self.manager.parse_hotwords_string(export_str, "技术")
        self.assertEqual(count, 3)
        self.assertEqual(len(self.manager.list_hotwords("技术")), 3)
        
        # 5. 测试持久化
        self.assertTrue(self.manager.save_hotwords())
        
        # 创建新实例并验证加载
        new_manager = HotwordManager(self.temp_file.name)
        self.assertEqual(len(new_manager.hotwords), 5)
        
        # 6. 测试统计信息
        stats = new_manager.get_statistics()
        self.assertEqual(stats["total_hotwords"], 5)
        self.assertIn("技术", stats["categories"])
        self.assertIn("公司", stats["categories"])
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试无效输入
        self.assertFalse(self.manager.add_hotword("", 5.0))  # 空字符串
        self.assertFalse(self.manager.add_hotword("测试", 0.5))  # 无效权重
        self.assertFalse(self.manager.add_hotword("测试<>", 5.0))  # 特殊字符
        
        # 测试操作不存在的热词
        self.assertFalse(self.manager.remove_hotword("不存在"))
        self.assertFalse(self.manager.update_hotword("不存在", weight=5.0))
        self.assertIsNone(self.manager.get_hotword("不存在"))
        
        # 测试空字符串解析
        count = self.manager.parse_hotwords_string("", "测试")
        self.assertEqual(count, 0)
        
        count = self.manager.parse_hotwords_string("   ", "测试")
        self.assertEqual(count, 0)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)