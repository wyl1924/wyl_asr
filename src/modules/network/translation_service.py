#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翻译服务模块
============

基于ModelScope的中英翻译功能，支持中文到英文的实时翻译。
使用CSANMT连续语义增强机器翻译模型。
"""

import logging
from typing import Optional, List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    from modelscope.pipelines import pipeline
    from modelscope.utils.constant import Tasks
    MODELSCOPE_AVAILABLE = True
except ImportError:
    MODELSCOPE_AVAILABLE = False
    logging.warning("ModelScope not available. Translation features will be disabled.")


class TranslationService:
    """
    翻译服务类
    
    提供基于ModelScope的中英翻译功能，支持：
    - 中文到英文翻译
    - 批量翻译
    - 异步翻译处理
    
    Attributes:
        model_id (str): ModelScope模型ID
        pipeline_ins: ModelScope翻译管道实例
        executor: 线程池执行器
        logger: 日志记录器
        is_initialized (bool): 初始化状态
    """
    
    def __init__(self, model_id: str = "iic/nlp_csanmt_translation_zh2en", max_workers: int = 2):
        """
        初始化翻译服务
        
        Args:
            model_id: ModelScope模型ID
            max_workers: 线程池最大工作线程数
        """
        self.model_id = model_id
        self.pipeline_ins = None
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger(__name__)
        self.is_initialized = False
        
    def initialize(self) -> bool:
        """
        初始化翻译模型
        
        Returns:
            bool: 初始化是否成功
        """
        if not MODELSCOPE_AVAILABLE:
            self.logger.error("ModelScope not available. Cannot initialize translation service.")
            return False
            
        try:
            self.logger.info(f"Initializing translation model: {self.model_id}")
            self.pipeline_ins = pipeline(
                task=Tasks.translation, 
                model=self.model_id
            )
            self.is_initialized = True
            self.logger.info("Translation service initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize translation service: {e}")
            return False
    
    def _translate_sync(self, text: str) -> Optional[str]:
        """
        同步翻译单个文本
        
        Args:
            text: 待翻译的中文文本
            
        Returns:
            Optional[str]: 翻译结果，失败时返回None
        """
        if not self.is_initialized or not self.pipeline_ins:
            self.logger.error("Translation service not initialized")
            return None
            
        if not text or not text.strip():
            return ""
            
        try:
            # 清理输入文本
            cleaned_text = text.strip()
            
            # 执行翻译
            result = self.pipeline_ins(input=cleaned_text)
            translation = result.get('translation', '')
            
            self.logger.debug(f"Translation: '{cleaned_text}' -> '{translation}'")
            return translation
            
        except Exception as e:
            self.logger.error(f"Translation failed for text '{text}': {e}")
            return None
    
    def _translate_batch_sync(self, texts: List[str]) -> List[Optional[str]]:
        """
        同步批量翻译
        
        Args:
            texts: 待翻译的中文文本列表
            
        Returns:
            List[Optional[str]]: 翻译结果列表
        """
        if not self.is_initialized or not self.pipeline_ins:
            self.logger.error("Translation service not initialized")
            return [None] * len(texts)
            
        if not texts:
            return []
            
        try:
            # 过滤空文本
            valid_texts = [text.strip() for text in texts if text and text.strip()]
            if not valid_texts:
                return [""] * len(texts)
            
            # 使用特定连接符进行批量翻译
            batch_input = '<SENT_SPLIT>'.join(valid_texts)
            result = self.pipeline_ins(input=batch_input)
            
            # 解析批量翻译结果
            translations = result.get('translation', '').split('<SENT_SPLIT>')
            
            # 确保返回结果数量与输入一致
            if len(translations) != len(valid_texts):
                self.logger.warning(f"Translation count mismatch: input={len(valid_texts)}, output={len(translations)}")
                # 如果数量不匹配，逐个翻译
                return [self._translate_sync(text) for text in texts]
            
            # 映射回原始文本位置
            results = []
            valid_idx = 0
            for text in texts:
                if text and text.strip():
                    results.append(translations[valid_idx] if valid_idx < len(translations) else None)
                    valid_idx += 1
                else:
                    results.append("")
            
            self.logger.debug(f"Batch translation completed: {len(texts)} texts")
            return results
            
        except Exception as e:
            self.logger.error(f"Batch translation failed: {e}")
            # 降级到逐个翻译
            return [self._translate_sync(text) for text in texts]
    
    async def translate(self, text: str) -> Optional[str]:
        """
        异步翻译单个文本
        
        Args:
            text: 待翻译的中文文本
            
        Returns:
            Optional[str]: 翻译结果，失败时返回None
        """
        if not text or not text.strip():
            return ""
            
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self.executor, 
                self._translate_sync, 
                text
            )
            return result
        except Exception as e:
            self.logger.error(f"Async translation failed: {e}")
            return None
    
    async def translate_batch(self, texts: List[str]) -> List[Optional[str]]:
        """
        异步批量翻译
        
        Args:
            texts: 待翻译的中文文本列表
            
        Returns:
            List[Optional[str]]: 翻译结果列表
        """
        if not texts:
            return []
            
        loop = asyncio.get_event_loop()
        try:
            results = await loop.run_in_executor(
                self.executor, 
                self._translate_batch_sync, 
                texts
            )
            return results
        except Exception as e:
            self.logger.error(f"Async batch translation failed: {e}")
            return [None] * len(texts)
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取翻译服务状态
        
        Returns:
            Dict[str, Any]: 服务状态信息
        """
        return {
            "initialized": self.is_initialized,
            "model_id": self.model_id,
            "modelscope_available": MODELSCOPE_AVAILABLE,
            "executor_active": not self.executor._shutdown if self.executor else False
        }
    
    def shutdown(self):
        """
        关闭翻译服务
        """
        if self.executor:
            self.executor.shutdown(wait=True)
            self.logger.info("Translation service shutdown completed")


# 全局翻译服务实例
_translation_service = None


def get_translation_service() -> TranslationService:
    """
    获取全局翻译服务实例
    
    Returns:
        TranslationService: 翻译服务实例
    """
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service


def initialize_translation_service() -> bool:
    """
    初始化全局翻译服务
    
    Returns:
        bool: 初始化是否成功
    """
    service = get_translation_service()
    return service.initialize()


def shutdown_translation_service():
    """
    关闭全局翻译服务
    """
    global _translation_service
    if _translation_service:
        _translation_service.shutdown()
        _translation_service = None