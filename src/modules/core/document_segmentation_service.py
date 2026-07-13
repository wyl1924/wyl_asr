#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档分段服务模块
================

基于ModelScope的BERT文档分割功能，支持中文长文本的段落分割。
使用BERT文本分割-中文-通用领域模型。
"""

import os
import logging
from typing import Optional, List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    from modelscope.pipelines import pipeline
    from modelscope.utils.constant import Tasks
    from modelscope.outputs import OutputKeys
    MODELSCOPE_AVAILABLE = True
except ImportError:
    MODELSCOPE_AVAILABLE = False
    logging.warning("ModelScope not available. Document segmentation features will be disabled.")


class DocumentSegmentationError(Exception):
    """文档分段相关异常。"""
    pass


# 设置日志
logger = logging.getLogger(__name__)


# 全局模型状态
_model_state = {
    'model': None,
    'pipeline_ins': None,
    'model_name': None,
    'device': None,
    'cache_dir': None,
    'args': None,
    'executor': None,
    'is_initialized': False
}


def _check_model_exists(model_name: str, cache_dir: str = None) -> bool:
    """检查模型是否存在于本地"""
    try:
        # 检查缓存目录中是否存在模型
        if cache_dir and os.path.exists(cache_dir):
            # 检查缓存目录下是否有对应的模型文件夹
            model_cache_path = os.path.join(cache_dir, model_name.replace('/', '--'))
            if os.path.exists(model_cache_path):
                logger.info(f"在缓存目录中找到模型: {model_cache_path}")
                return True
        
        # 检查默认的 huggingface 缓存目录
        try:
            import transformers
            default_cache_dir = transformers.utils.hub.default_cache_path
            if default_cache_dir and os.path.exists(default_cache_dir):
                # 在默认缓存中查找模型
                model_cache_path = os.path.join(default_cache_dir, f"models--{model_name.replace('/', '--')}")
                if os.path.exists(model_cache_path):
                    logger.info(f"在默认缓存目录中找到模型: {model_cache_path}")
                    return True
        except ImportError:
            pass
        
        # 如果都没找到，返回 False
        logger.debug(f"模型 {model_name} 在本地未找到")
        return False
        
    except Exception as e:
        logger.debug(f"检查模型存在性时出错: {str(e)}")
        # 如果检查过程出错，假设模型不存在
        return False


def _load_model(args: Optional[object] = None):
    """加载文档分段模型"""
    global _model_state
    
    # 获取args参数
    if args is None:
        try:
            from ..core.server_state import server_state
            args = getattr(server_state, 'args', None)
        except:
            args = None
    
    # 设置模型参数
    model_name = getattr(args, 'segmentation_model', 'iic/nlp_bert_document-segmentation_chinese-base')
    device = getattr(args, 'device', None)
    cache_dir = getattr(args, 'cache_dir', None)
    max_workers = getattr(args, 'segmentation_workers', 2)
    
    _model_state.update({
        'model_name': model_name,
        'device': device,
        'cache_dir': cache_dir,
        'args': args
    })
    
    if not model_name:
        logger.warning("未指定文档分段模型")
        return
    
    if not MODELSCOPE_AVAILABLE:
        logger.error("ModelScope not available. Cannot initialize document segmentation service.")
        return
    
    # 检查模型是否存在（本地检查）
    if not _check_model_exists(model_name, cache_dir):
        logger.warning(f"模型 {model_name} 不存在，跳过加载")
        return
        
    try:
        logger.info(f"正在尝试加载文档分段模型: {model_name}")
        logger.info(f"设备: {device}")

        # 初始化线程池
        _model_state['executor'] = ThreadPoolExecutor(max_workers=max_workers)
        
        # 加载模型管道
        logger.info("开始加载文档分段管道...")
        _model_state['pipeline_ins'] = pipeline(
            task=Tasks.document_segmentation,
            model=model_name
        )
        _model_state['is_initialized'] = True
        logger.info(f"文档分段模型加载成功: {model_name}")

        # 测试模型是否可用
        logger.info("测试模型可用性...")
        model_info = get_model_info()
        logger.info(f"模型信息: {model_info}")

    except Exception as e:
        logger.warning(f"模型 {model_name} 加载失败: {str(e)}")
        logger.warning(f"文档分段功能将不可用")
        logger.info("💡 如需使用文档分段功能，请先下载相应模型")
        _model_state['pipeline_ins'] = None
        _model_state['is_initialized'] = False


def _segment_sync(text: str) -> Optional[str]:
    """
    同步分段单个文本
    
    Args:
        text: 待分段的中文文本
        
    Returns:
        Optional[str]: 分段结果，失败时返回None
    """
    if not _model_state['is_initialized'] or not _model_state['pipeline_ins']:
        raise DocumentSegmentationError("文档分段模型未加载，请确保模型文件存在或先下载模型")
        
    if not text or not text.strip():
        return ""
        
    try:
        # 清理输入文本
        cleaned_text = text.strip()
        
        # 执行文档分段
        result = _model_state['pipeline_ins'](documents=cleaned_text)
        
        # 提取分段结果
        if result and OutputKeys.TEXT in result:
            segmented_text = result[OutputKeys.TEXT]
            logger.debug(f"Document segmentation successful: {len(cleaned_text)} -> {len(segmented_text)} chars")
            return segmented_text
        else:
            logger.warning("Document segmentation returned empty result")
            return cleaned_text  # 返回原文本作为备选
            
    except Exception as e:
        logger.error(f"Document segmentation failed: {e}")
        return None


def _segment_batch_sync(texts: List[str]) -> List[Optional[str]]:
    """
    同步批量分段文本
    
    Args:
        texts: 待分段的文本列表
        
    Returns:
        List[Optional[str]]: 分段结果列表
    """
    if not _model_state['is_initialized'] or not _model_state['pipeline_ins']:
        raise DocumentSegmentationError("文档分段模型未加载，请确保模型文件存在或先下载模型")
        
    results = []
    for text in texts:
        try:
            if not text or not text.strip():
                results.append("")
                continue
                
            # 执行文档分段
            result = _model_state['pipeline_ins'](documents=text.strip())
            
            # 提取分段结果
            if result and OutputKeys.TEXT in result:
                segmented_text = result[OutputKeys.TEXT]
                results.append(segmented_text)
            else:
                results.append(text)  # 返回原文本作为备选
                
        except Exception as e:
            logger.error(f"Batch document segmentation failed for text: {e}")
            results.append(None)
            
    return results


async def segment(text: str) -> Optional[str]:
    """
    异步分段单个文本
    
    Args:
        text: 待分段的中文文本
        
    Returns:
        Optional[str]: 分段结果，失败时返回None
    """
    if not _model_state['is_initialized']:
        raise DocumentSegmentationError("文档分段模型未加载，请确保模型文件存在或先下载模型")
        
    try:
        # 在线程池中执行同步分段
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _model_state['executor'], 
            _segment_sync, 
            text
        )
        return result
    except Exception as e:
        logger.error(f"Async document segmentation failed: {e}")
        return None


async def segment_batch(texts: List[str]) -> List[Optional[str]]:
    """
    异步批量分段文本
    
    Args:
        texts: 待分段的文本列表
        
    Returns:
        List[Optional[str]]: 分段结果列表
    """
    if not _model_state['is_initialized']:
        raise DocumentSegmentationError("文档分段模型未加载，请确保模型文件存在或先下载模型")
        
    try:
        # 在线程池中执行同步批量分段
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            _model_state['executor'], 
            _segment_batch_sync, 
            texts
        )
        return results
    except Exception as e:
        logger.error(f"Async batch document segmentation failed: {e}")
        return [None] * len(texts)


def get_status() -> Dict[str, Any]:
    """
    获取服务状态信息
    
    Returns:
        Dict[str, Any]: 状态信息字典
    """
    return {
        "model_name": _model_state['model_name'],
        "is_initialized": _model_state['is_initialized'],
        "modelscope_available": MODELSCOPE_AVAILABLE,
        "executor_workers": _model_state['executor']._max_workers if _model_state['executor'] else 0
    }


def get_model_info() -> Dict:
    """获取模型信息"""
    return {
        "model_name": _model_state['model_name'],
        "device": _model_state['device'],
        "cache_dir": _model_state['cache_dir'],
        "model_loaded": _model_state['is_initialized']
    }


def shutdown():
    """
    关闭文档分段服务
    
    清理资源并关闭线程池
    """
    try:
        if _model_state['executor']:
            _model_state['executor'].shutdown(wait=True)
            logger.info("Document segmentation service executor shutdown")
    except Exception as e:
        logger.error(f"Error shutting down document segmentation service: {e}")


def init_document_segmentation(args: Optional[object] = None):
    """初始化文档分段模块
    
    Args:
        args: 命令行参数对象 (可选)
    """
    _load_model(args)


class DocumentSegmentationService:
    """
    文档分段服务类（兼容性保留）
    
    提供基于ModelScope的中文文档分段功能，支持：
    - 长文本段落分割
    - 批量文档分段
    - 异步分段处理
    
    Attributes:
        model_id (str): ModelScope模型ID
        pipeline_ins: ModelScope文档分段管道实例
        executor: 线程池执行器
        logger: 日志记录器
        is_initialized (bool): 初始化状态
    """
    
    def __init__(self, model_id: str = "iic/nlp_bert_document-segmentation_chinese-base", max_workers: int = 2):
        """
        初始化文档分段服务
        
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
        初始化文档分段模型
        
        Returns:
            bool: 初始化是否成功
        """
        if not MODELSCOPE_AVAILABLE:
            self.logger.error("ModelScope not available. Cannot initialize document segmentation service.")
            return False
            
        try:
            self.logger.info(f"Initializing document segmentation model: {self.model_id}")
            self.pipeline_ins = pipeline(
                task=Tasks.document_segmentation,
                model=self.model_id
            )
            self.is_initialized = True
            self.logger.info("Document segmentation service initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize document segmentation service: {e}")
            return False
    
    def _segment_sync(self, text: str) -> Optional[str]:
        """
        同步分段单个文本
        
        Args:
            text: 待分段的中文文本
            
        Returns:
            Optional[str]: 分段结果，失败时返回None
        """
        if not self.is_initialized or not self.pipeline_ins:
            self.logger.error("Document segmentation service not initialized")
            return None
            
        if not text or not text.strip():
            return ""
            
        try:
            # 清理输入文本
            cleaned_text = text.strip()
            
            # 执行文档分段
            result = self.pipeline_ins(documents=cleaned_text)
            
            # 提取分段结果
            if result and OutputKeys.TEXT in result:
                segmented_text = result[OutputKeys.TEXT]
                self.logger.debug(f"Document segmentation successful: {len(cleaned_text)} -> {len(segmented_text)} chars")
                return segmented_text
            else:
                self.logger.warning("Document segmentation returned empty result")
                return cleaned_text  # 返回原文本作为备选
                
        except Exception as e:
            self.logger.error(f"Document segmentation failed: {e}")
            return None
    
    def _segment_batch_sync(self, texts: List[str]) -> List[Optional[str]]:
        """
        同步批量分段文本
        
        Args:
            texts: 待分段的文本列表
            
        Returns:
            List[Optional[str]]: 分段结果列表
        """
        if not self.is_initialized or not self.pipeline_ins:
            self.logger.error("Document segmentation service not initialized")
            return [None] * len(texts)
            
        results = []
        for text in texts:
            try:
                if not text or not text.strip():
                    results.append("")
                    continue
                    
                # 执行文档分段
                result = self.pipeline_ins(documents=text.strip())
                
                # 提取分段结果
                if result and OutputKeys.TEXT in result:
                    segmented_text = result[OutputKeys.TEXT]
                    results.append(segmented_text)
                else:
                    results.append(text)  # 返回原文本作为备选
                    
            except Exception as e:
                self.logger.error(f"Batch document segmentation failed for text: {e}")
                results.append(None)
                
        return results
    
    async def segment(self, text: str) -> Optional[str]:
        """
        异步分段单个文本
        
        Args:
            text: 待分段的中文文本
            
        Returns:
            Optional[str]: 分段结果，失败时返回None
        """
        if not self.is_initialized:
            self.logger.error("Document segmentation service not initialized")
            return None
            
        try:
            # 在线程池中执行同步分段
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                self._segment_sync, 
                text
            )
            return result
        except Exception as e:
            self.logger.error(f"Async document segmentation failed: {e}")
            return None
    
    async def segment_batch(self, texts: List[str]) -> List[Optional[str]]:
        """
        异步批量分段文本
        
        Args:
            texts: 待分段的文本列表
            
        Returns:
            List[Optional[str]]: 分段结果列表
        """
        if not self.is_initialized:
            self.logger.error("Document segmentation service not initialized")
            return [None] * len(texts)
            
        try:
            # 在线程池中执行同步批量分段
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                self.executor, 
                self._segment_batch_sync, 
                texts
            )
            return results
        except Exception as e:
            self.logger.error(f"Async batch document segmentation failed: {e}")
            return [None] * len(texts)
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取服务状态信息
        
        Returns:
            Dict[str, Any]: 状态信息字典
        """
        return {
            "model_id": self.model_id,
            "is_initialized": self.is_initialized,
            "modelscope_available": MODELSCOPE_AVAILABLE,
            "executor_workers": self.executor._max_workers if self.executor else 0
        }

    def shutdown(self):
        """
        关闭文档分段服务
        
        清理资源并关闭线程池
        """
        try:
            if self.executor:
                self.executor.shutdown(wait=True)
                self.logger.info("Document segmentation service executor shutdown")
        except Exception as e:
            self.logger.error(f"Error shutting down document segmentation service: {e}")


# 兼容性函数，使用新的全局模型状态
def get_segmentation_service():
    """
    获取文档分段服务状态（兼容性保留）
    
    Returns:
        dict: 文档分段服务状态信息
    """
    return get_status()


def initialize_segmentation_service() -> bool:
    """
    初始化全局文档分段服务（兼容性保留）
    
    Returns:
        bool: 初始化是否成功
    """
    try:
        init_document_segmentation()
        return _model_state['is_initialized']
    except Exception as e:
        logger.error(f"初始化文档分段服务失败: {e}")
        return False


def shutdown_segmentation_service():
    """
    关闭全局文档分段服务（兼容性保留）
    """
    shutdown()


# 便捷函数
def segment_text(text: str) -> Optional[str]:
    """分段文本的便捷函数"""
    return _segment_sync(text)


def segment_text_batch(texts: List[str]) -> List[Optional[str]]:
    """批量分段文本的便捷函数"""
    return _segment_batch_sync(texts)


async def segment_text_async(text: str) -> Optional[str]:
    """异步分段文本的便捷函数"""
    return await segment(text)


async def segment_text_batch_async(texts: List[str]) -> List[Optional[str]]:
    """异步批量分段文本的便捷函数"""
    return await segment_batch(texts)