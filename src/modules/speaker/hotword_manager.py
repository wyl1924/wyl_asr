#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热词管理模块

提供热词的管理功能，包括：
1. 热词的添加、删除、更新
2. 热词权重管理
3. 热词格式验证和转换
4. 热词持久化存储
5. 热词分类管理
"""

import json
import os
import re
import logging
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class Hotword:
    """热词数据类"""
    word: str
    weight: float = 4.0
    category: str = "default"
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Hotword':
        """从字典创建热词对象"""
        return cls(**data)


class HotwordManager:
    """热词管理器"""
    
    def __init__(self, storage_path: str = "data/hotwords.json"):
        """
        初始化热词管理器
        
        Args:
            storage_path: 热词存储文件路径
        """
        self.storage_path = storage_path
        self.hotwords: Dict[str, Hotword] = {}
        self.categories: Dict[str, List[str]] = {"default": []}
        
        # 确保存储目录存在
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        
        # 加载已有热词
        self.load_hotwords()
        
        logger.info(f"热词管理器初始化完成，存储路径: {storage_path}")
    
    def add_hotword(self, word: str, weight: float = 4.0, category: str = "default", 
                   description: str = "", overwrite: bool = False) -> bool:
        """
        添加热词
        
        Args:
            word: 热词文本
            weight: 热词权重 (1-10)
            category: 热词分类
            description: 热词描述
            overwrite: 是否覆盖已存在的热词
            
        Returns:
            bool: 添加是否成功
        """
        # 验证输入
        if not self._validate_word(word):
            logger.error(f"无效的热词: {word}")
            return False
        
        if not self._validate_weight(weight):
            logger.error(f"无效的权重: {weight}")
            return False
        
        # 检查是否已存在
        if word in self.hotwords and not overwrite:
            logger.warning(f"热词已存在: {word}")
            return False
        
        # 创建热词对象
        hotword = Hotword(
            word=word,
            weight=weight,
            category=category,
            description=description
        )
        
        # 添加到管理器
        self.hotwords[word] = hotword
        
        # 更新分类
        if category not in self.categories:
            self.categories[category] = []
        if word not in self.categories[category]:
            self.categories[category].append(word)
        
        # 保存到文件
        self.save_hotwords()
        
        logger.info(f"热词添加成功: {word} (权重: {weight}, 分类: {category})")
        return True
    
    def remove_hotword(self, word: str) -> bool:
        """
        删除热词
        
        Args:
            word: 要删除的热词
            
        Returns:
            bool: 删除是否成功
        """
        if word not in self.hotwords:
            logger.warning(f"热词不存在: {word}")
            return False
        
        # 获取分类信息
        category = self.hotwords[word].category
        
        # 从热词字典中删除
        del self.hotwords[word]
        
        # 从分类中删除
        if category in self.categories and word in self.categories[category]:
            self.categories[category].remove(word)
            
            # 如果分类为空且不是默认分类，删除分类
            if not self.categories[category] and category != "default":
                del self.categories[category]
        
        # 保存到文件
        self.save_hotwords()
        
        logger.info(f"热词删除成功: {word}")
        return True
    
    def update_hotword(self, word: str, weight: Optional[float] = None, 
                      category: Optional[str] = None, description: Optional[str] = None) -> bool:
        """
        更新热词信息
        
        Args:
            word: 热词文本
            weight: 新的权重
            category: 新的分类
            description: 新的描述
            
        Returns:
            bool: 更新是否成功
        """
        if word not in self.hotwords:
            logger.warning(f"热词不存在: {word}")
            return False
        
        hotword = self.hotwords[word]
        old_category = hotword.category
        
        # 更新属性
        if weight is not None:
            if not self._validate_weight(weight):
                logger.error(f"无效的权重: {weight}")
                return False
            hotword.weight = weight
        
        if category is not None:
            hotword.category = category
            
            # 更新分类
            if old_category != category:
                # 从旧分类中删除
                if old_category in self.categories and word in self.categories[old_category]:
                    self.categories[old_category].remove(word)
                    if not self.categories[old_category] and old_category != "default":
                        del self.categories[old_category]
                
                # 添加到新分类
                if category not in self.categories:
                    self.categories[category] = []
                if word not in self.categories[category]:
                    self.categories[category].append(word)
        
        if description is not None:
            hotword.description = description
        
        # 更新时间戳
        hotword.updated_at = datetime.now().isoformat()
        
        # 保存到文件
        self.save_hotwords()
        
        logger.info(f"热词更新成功: {word}")
        return True
    
    def get_hotword(self, word: str) -> Optional[Hotword]:
        """
        获取热词信息
        
        Args:
            word: 热词文本
            
        Returns:
            Optional[Hotword]: 热词对象，如果不存在返回None
        """
        return self.hotwords.get(word)
    
    def list_hotwords(self, category: Optional[str] = None) -> List[Hotword]:
        """
        列出热词
        
        Args:
            category: 指定分类，如果为None则返回所有热词
            
        Returns:
            List[Hotword]: 热词列表
        """
        if category is None:
            return list(self.hotwords.values())
        
        if category not in self.categories:
            return []
        
        return [self.hotwords[word] for word in self.categories[category] if word in self.hotwords]
    
    def list_categories(self) -> List[str]:
        """
        列出所有分类
        
        Returns:
            List[str]: 分类列表
        """
        return list(self.categories.keys())
    
    def get_hotwords_string(self, category: Optional[str] = None, format_type: str = "funasr") -> str:
        """
        获取热词字符串，用于ASR模型
        
        Args:
            category: 指定分类，如果为None则返回所有热词
            format_type: 格式类型 ("funasr", "simple", "json")
            
        Returns:
            str: 格式化的热词字符串
        """
        hotwords = self.list_hotwords(category)
        
        if not hotwords:
            return ""
        
        if format_type == "funasr":
            # FunASR格式: "词1 权重1 词2 权重2"
            parts = []
            for hotword in hotwords:
                parts.extend([hotword.word, str(int(hotword.weight))])
            return " ".join(parts)
        
        elif format_type == "simple":
            # 简单格式: "词1,词2,词3"
            return ",".join([hotword.word for hotword in hotwords])
        
        elif format_type == "json":
            # JSON格式
            return json.dumps([hotword.to_dict() for hotword in hotwords], ensure_ascii=False)
        
        else:
            logger.error(f"不支持的格式类型: {format_type}")
            return ""
    
    def parse_hotwords_string(self, hotwords_str: str, category: str = "imported") -> int:
        """
        解析热词字符串并添加到管理器
        
        支持多种格式：
        - "词1 权重1 词2 权重2" (FunASR格式)
        - "词1,词2,词3" (逗号分隔)
        - "词1 词2 词3" (空格分隔)
        
        Args:
            hotwords_str: 热词字符串
            category: 导入的热词分类
            
        Returns:
            int: 成功导入的热词数量
        """
        if not hotwords_str.strip():
            return 0
        
        imported_count = 0
        
        # 尝试解析FunASR格式 (词 权重 词 权重)
        parts = hotwords_str.strip().split()
        if len(parts) % 2 == 0:
            # 检查是否为权重格式
            is_weight_format = True
            for i in range(1, len(parts), 2):
                try:
                    float(parts[i])
                except ValueError:
                    is_weight_format = False
                    break
            
            if is_weight_format:
                for i in range(0, len(parts), 2):
                    word = parts[i]
                    weight = float(parts[i + 1])
                    if self.add_hotword(word, weight, category, overwrite=True):
                        imported_count += 1
                return imported_count
        
        # 尝试逗号分隔格式
        if "," in hotwords_str:
            words = [word.strip() for word in hotwords_str.split(",") if word.strip()]
            for word in words:
                if self.add_hotword(word, 4.0, category, overwrite=True):
                    imported_count += 1
            return imported_count
        
        # 空格分隔格式
        words = [word.strip() for word in hotwords_str.split() if word.strip()]
        for word in words:
            if self.add_hotword(word, 4.0, category, overwrite=True):
                imported_count += 1
        
        return imported_count
    
    def clear_category(self, category: str) -> int:
        """
        清空指定分类的所有热词
        
        Args:
            category: 分类名称
            
        Returns:
            int: 删除的热词数量
        """
        if category not in self.categories:
            return 0
        
        words_to_remove = self.categories[category].copy()
        removed_count = 0
        
        for word in words_to_remove:
            if self.remove_hotword(word):
                removed_count += 1
        
        logger.info(f"分类 '{category}' 清空完成，删除了 {removed_count} 个热词")
        return removed_count
    
    def clear_all(self) -> int:
        """
        清空所有热词
        
        Returns:
            int: 删除的热词数量
        """
        count = len(self.hotwords)
        self.hotwords.clear()
        self.categories = {"default": []}
        self.save_hotwords()
        
        logger.info(f"所有热词已清空，共删除 {count} 个热词")
        return count
    
    def get_statistics(self) -> Dict:
        """
        获取热词统计信息
        
        Returns:
            Dict: 统计信息
        """
        stats = {
            "total_hotwords": len(self.hotwords),
            "total_categories": len(self.categories),
            "categories": {}
        }
        
        for category, words in self.categories.items():
            stats["categories"][category] = {
                "count": len(words),
                "words": words
            }
        
        # 权重分布
        weight_distribution = {}
        for hotword in self.hotwords.values():
            weight = int(hotword.weight)
            weight_distribution[weight] = weight_distribution.get(weight, 0) + 1
        
        stats["weight_distribution"] = weight_distribution
        
        return stats
    
    def save_hotwords(self) -> bool:
        """
        保存热词到文件
        
        Returns:
            bool: 保存是否成功
        """
        try:
            data = {
                "hotwords": {word: hotword.to_dict() for word, hotword in self.hotwords.items()},
                "categories": self.categories,
                "metadata": {
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                    "total_count": len(self.hotwords)
                }
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"热词保存成功: {self.storage_path}")
            return True
            
        except Exception as e:
            logger.error(f"热词保存失败: {e}")
            return False
    
    def load_hotwords(self) -> bool:
        """
        从文件加载热词
        
        Returns:
            bool: 加载是否成功
        """
        if not os.path.exists(self.storage_path):
            logger.info("热词文件不存在，使用空的热词库")
            return True
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 加载热词
            if "hotwords" in data:
                for word, hotword_data in data["hotwords"].items():
                    self.hotwords[word] = Hotword.from_dict(hotword_data)
            
            # 加载分类
            if "categories" in data:
                self.categories = data["categories"]
            
            logger.info(f"热词加载成功: {len(self.hotwords)} 个热词，{len(self.categories)} 个分类")
            return True
            
        except Exception as e:
            logger.error(f"热词加载失败: {e}")
            return False
    
    def _validate_word(self, word: str) -> bool:
        """
        验证热词是否有效
        
        Args:
            word: 热词文本
            
        Returns:
            bool: 是否有效
        """
        if not word or not word.strip():
            return False
        
        # 检查长度
        if len(word.strip()) > 50:
            return False
        
        # 检查是否包含特殊字符
        if re.search(r'[<>|\[\]{}]', word):
            return False
        
        return True
    
    def _validate_weight(self, weight: float) -> bool:
        """
        验证权重是否有效
        
        Args:
            weight: 权重值
            
        Returns:
            bool: 是否有效
        """
        return 1.0 <= weight <= 10.0


# 全局热词管理器实例
_hotword_manager = None


def get_hotword_manager() -> HotwordManager:
    """
    获取全局热词管理器实例
    
    Returns:
        HotwordManager: 热词管理器实例
    """
    global _hotword_manager
    if _hotword_manager is None:
        _hotword_manager = HotwordManager()
    return _hotword_manager


def init_hotword_manager(storage_path: str = "data/hotwords.json", args: Optional[object] = None) -> HotwordManager:
    """
    初始化热词管理器
    
    Args:
        storage_path: 存储路径
        args: 命令行参数对象 (可选)
        
    Returns:
        HotwordManager: 热词管理器实例
    """
    global _hotword_manager
    
    # 如果提供了args参数，尝试从中获取热词存储路径
    if args is None:
        try:
            from ..core.server_state import server_state
            args = getattr(server_state, 'args', None)
        except:
            args = None
    
    # 从args获取热词存储路径
    if args and hasattr(args, 'hotword_storage_path'):
        storage_path = args.hotword_storage_path
        logger.info(f"使用命令行指定的热词存储路径: {storage_path}")
    
    _hotword_manager = HotwordManager(storage_path)
    logger.info(f"热词管理器初始化完成，存储路径: {storage_path}")
    return _hotword_manager


def get_model_info() -> Dict:
    """获取热词管理器信息"""
    manager = get_hotword_manager()
    stats = manager.get_statistics()
    return {
        "storage_path": manager.storage_path,
        "total_hotwords": stats.get("total_hotwords", 0),
        "total_categories": stats.get("total_categories", 0),
        "categories": list(stats.get("categories", {}).keys())
    }


def shutdown():
    """
    关闭热词管理器
    
    保存当前状态并清理资源
    """
    global _hotword_manager
    if _hotword_manager:
        _hotword_manager.save_hotwords()
        logger.info("热词管理器已关闭")
        _hotword_manager = None


# 便捷函数
def add_hotword(word: str, weight: float = 4.0, category: str = "default", 
               description: str = "", overwrite: bool = False) -> bool:
    """添加热词的便捷函数"""
    return get_hotword_manager().add_hotword(word, weight, category, description, overwrite)


def remove_hotword(word: str) -> bool:
    """删除热词的便捷函数"""
    return get_hotword_manager().remove_hotword(word)


def get_hotwords_string(category: Optional[str] = None, format_type: str = "funasr") -> str:
    """获取热词字符串的便捷函数"""
    return get_hotword_manager().get_hotwords_string(category, format_type)


def parse_hotwords_string(hotwords_str: str, category: str = "imported") -> int:
    """解析热词字符串的便捷函数"""
    return get_hotword_manager().parse_hotwords_string(hotwords_str, category)


def list_hotwords(category: Optional[str] = None) -> List[Hotword]:
    """列出热词的便捷函数"""
    return get_hotword_manager().list_hotwords(category)


if __name__ == "__main__":
    # 测试代码
    manager = HotwordManager("test_hotwords.json")
    
    # 添加测试热词
    manager.add_hotword("人工智能", 5.0, "技术", "AI相关词汇")
    manager.add_hotword("机器学习", 4.5, "技术", "ML相关词汇")
    manager.add_hotword("深度学习", 4.0, "技术", "DL相关词汇")
    manager.add_hotword("阿里巴巴", 5.0, "公司", "公司名称")
    manager.add_hotword("达摩院", 4.5, "公司", "研究机构")
    
    # 测试功能
    print("热词列表:")
    for hotword in manager.list_hotwords():
        print(f"  {hotword.word} (权重: {hotword.weight}, 分类: {hotword.category})")
    
    print("\nFunASR格式热词字符串:")
    print(manager.get_hotwords_string(format_type="funasr"))
    
    print("\n统计信息:")
    stats = manager.get_statistics()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    
    # 清理测试文件
    os.remove("test_hotwords.json")