#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""说话人管理模块。

提供说话人注册、识别、管理等功能。
"""

# 标准库导入
import os
import json
import pickle
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union, Tuple

# 第三方库导入
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN

# 本地模块导入
from ..speaker.speaker_verification import extract_embedding, init_speaker_verification
from ..core.server_state import ServerState
from config.config import DATA_DIR

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# 异常定义
# ============================================================================

class SpeakerManagerError(Exception):
    """说话人管理相关异常。"""
    pass


# ============================================================================
# 全局状态管理
# ============================================================================

# 全局说话人管理状态
_manager_state = {
    'db_path': None,                    # 数据库文件路径
    'embeddings_path': None,            # 特征向量文件路径
    'similarity_threshold': None,       # 相似度阈值
    'args': None,                      # 命令行参数
    'speaker_db': {},                  # 说话人信息数据库
    'speaker_embeddings': {},          # 说话人特征向量
    'initialized': False               # 初始化状态
}


# ============================================================================
# 公共接口函数
# ============================================================================

def init_speaker_manager(args: Optional[object] = None):
    """初始化说话人管理器
    
    Args:
        args: 命令行参数对象 (可选)
    """
    global _manager_state
    
    if _manager_state['initialized']:
        return
    
    # 获取args参数
    if args is None:
        try:
            from ..core.server_state import server_state
            args = getattr(server_state, 'args', None)
        except:
            args = None
    
    # 设置路径和参数
    speaker_dir = getattr(args, 'speaker_db_path', None) or os.path.join(DATA_DIR, "speaker")
    _manager_state.update({
        'db_path': os.path.join(speaker_dir, "speaker_database.json"),
        'embeddings_path': os.path.join(speaker_dir, "speaker_embeddings.pkl"),
        'similarity_threshold': getattr(args, 'speaker_threshold', 0.8),
        'args': args
    })
    
    # 初始化说话人验证模块
    init_speaker_verification(args)
    
    # 加载现有数据
    _load_database()
    _load_embeddings()
    
    _manager_state['initialized'] = True
    
    logger.info(f"说话人管理器初始化完成")
    logger.info(f"数据库路径: {_manager_state['db_path']}")
    logger.info(f"特征向量路径: {_manager_state['embeddings_path']}")
    logger.info(f"相似度阈值: {_manager_state['similarity_threshold']}")
    logger.info(f"已注册说话人数量: {len(_manager_state['speaker_db'])}")


def register_speaker(speaker_name: str,
                    audio_input: Union[str, bytes],
                    description: str = "",
                    overwrite: bool = False) -> Dict:
    """
    注册新说话人
    
    Args:
        speaker_name: 说话人姓名
        audio_input: 音频文件路径或音频数据
        description: 说话人描述
        overwrite: 是否覆盖已存在的说话人
        
    Returns:
        注册结果字典
    """
    global _manager_state
    
    if not _manager_state['initialized']:
        init_speaker_manager()
    
    try:
        logger.info(f"注册说话人: {speaker_name}")
        
        # 检查是否已存在
        if speaker_name in _manager_state['speaker_db'] and not overwrite:
            return {
                "success": False,
                "message": f"说话人 {speaker_name} 已存在，使用 overwrite=True 覆盖",
                "speaker_name": speaker_name
            }
        
        # 检查说话人验证模型是否加载，如果未加载则尝试初始化
        try:
            from ..speaker.speaker_verification import get_model_info
            model_info = get_model_info()
            if not model_info.get('model_loaded', False):
                logger.info("说话人验证模型未加载，尝试初始化...")
                from ..speaker.speaker_verification import init_speaker_verification
                init_speaker_verification(_manager_state.get('args'))
                
                # 再次检查模型是否加载成功
                model_info = get_model_info()
                if not model_info.get('model_loaded', False):
                    logger.warning("说话人验证模型加载失败，但允许继续注册（仅保存音频数据）")
                    # 不返回错误，允许继续注册但不提取特征
                else:
                    logger.info("说话人验证模型初始化成功")
        except Exception as e:
            logger.warning(f"初始化说话人验证模型失败: {str(e)}，但允许继续注册")
            # 不返回错误，允许继续注册
        
        # 提取特征向量
        try:
            embedding = extract_embedding(audio_input)
            logger.info(f"成功提取特征向量，维度: {embedding.shape}")
        except Exception as e:
            logger.error(f"特征提取失败: {str(e)}")
            return {
                "success": False,
                "message": f"特征提取失败: {str(e)}",
                "speaker_name": speaker_name
            }
        
        # 检查是否与现有说话人过于相似
        if not overwrite:
            similar_speakers = _find_similar_speakers_internal(embedding)
            if similar_speakers:
                most_similar = similar_speakers[0]
                if most_similar["similarity"] > _manager_state['similarity_threshold']:
                    return {
                        "success": False,
                        "message": f"与已注册说话人 {most_similar['speaker_name']} 过于相似 (相似度: {most_similar['similarity']:.4f})",
                        "similar_speaker": most_similar,
                        "speaker_name": speaker_name
                    }
        
        # 生成唯一ID
        speaker_id = f"speaker_{len(_manager_state['speaker_db']):04d}"
        
        # 保存说话人信息
        speaker_info = {
            "speaker_id": speaker_id,
            "speaker_name": speaker_name,
            "description": description,
            "registration_time": datetime.now().isoformat(),
            "audio_samples": 1,
            "last_updated": datetime.now().isoformat()
        }
        
        # 更新数据库
        _manager_state['speaker_db'][speaker_name] = speaker_info
        _manager_state['speaker_embeddings'][speaker_name] = embedding
        
        # 保存到文件
        _save_database()
        _save_embeddings()
        
        logger.info(f"说话人 {speaker_name} 注册成功")
        return {
            "success": True,
            "message": f"说话人 {speaker_name} 注册成功",
            "speaker_info": speaker_info,
            "embedding_shape": embedding.shape
        }
        
    except Exception as e:
        logger.error(f"注册说话人失败: {str(e)}")
        return {
            "success": False,
            "message": f"注册失败: {str(e)}",
            "speaker_name": speaker_name
        }


def identify_speaker(audio_input: Union[str, bytes],
                    top_k: int = 3) -> Dict:
    """
    识别说话人
    
    Args:
        audio_input: 音频文件路径或音频数据
        top_k: 返回前k个最相似的结果
        
    Returns:
        识别结果字典
    """
    global _manager_state
    
    if not _manager_state['initialized']:
        init_speaker_manager()
    
    try:
        logger.info("开始说话人识别...")
        
        if not _manager_state['speaker_embeddings']:
            return {
                "success": False,
                "message": "没有已注册的说话人",
                "candidates": []
            }
        
        # 提取特征向量
        query_embedding = extract_embedding(audio_input)
        
        # 查找相似说话人
        similar_speakers = _find_similar_speakers_internal(query_embedding, top_k)
        
        # 判断最佳匹配
        best_match = None
        if similar_speakers and similar_speakers[0]["similarity"] >= _manager_state['similarity_threshold']:
            best_match = similar_speakers[0]
        
        result = {
            "success": True,
            "best_match": best_match,
            "candidates": similar_speakers,
            "threshold": _manager_state['similarity_threshold'],
            "query_embedding_shape": query_embedding.shape
        }
        
        if best_match:
            logger.info(f"识别成功: {best_match['speaker_name']} (相似度: {best_match['similarity']:.4f})")
        else:
            logger.info("未找到匹配的说话人")
        
        return result
        
    except Exception as e:
        logger.error(f"说话人识别失败: {str(e)}")
        return {
            "success": False,
            "message": f"识别失败: {str(e)}",
            "candidates": []
        }


def update_speaker(speaker_name: str,
                  audio_input: Union[str, bytes] = None,
                  description: str = None) -> Dict:
    """更新说话人信息
    
    Args:
        speaker_name: 说话人名称
        audio_input: 新的音频数据 (可选)
        description: 新的描述 (可选)
        
    Returns:
        Dict: 更新结果
    """
    global _manager_state
    
    if not _manager_state['initialized']:
        init_speaker_manager()
    
    try:
        if speaker_name not in _manager_state['speaker_db']:
            return {
                "success": False,
                "message": f"说话人 {speaker_name} 不存在",
                "speaker_name": speaker_name
            }
        
        # 更新描述
        if description is not None:
            _manager_state['speaker_db'][speaker_name]["description"] = description
        
        # 更新音频样本
        if audio_input is not None:
            new_embedding = extract_embedding(audio_input)
            _manager_state['speaker_embeddings'][speaker_name] = new_embedding
            _manager_state['speaker_db'][speaker_name]["audio_samples"] += 1
        
        # 更新时间戳
        _manager_state['speaker_db'][speaker_name]["last_updated"] = datetime.now().isoformat()
        
        # 保存更改
        _save_database()
        if audio_input is not None:
            _save_embeddings()
        
        logger.info(f"说话人 {speaker_name} 信息已更新")
        return {
            "success": True,
            "message": f"说话人 {speaker_name} 更新成功",
            "speaker_info": _manager_state['speaker_db'][speaker_name]
        }
        
    except Exception as e:
        logger.error(f"更新说话人失败: {str(e)}")
        return {
            "success": False,
            "message": f"更新失败: {str(e)}",
            "speaker_name": speaker_name
        }


def delete_speaker(speaker_name: str) -> Dict:
    """删除说话人
    
    Args:
        speaker_name: 说话人名称
        
    Returns:
        Dict: 删除结果
    """
    global _manager_state
    
    if not _manager_state['initialized']:
        init_speaker_manager()
    
    try:
        if speaker_name not in _manager_state['speaker_db']:
            return {
                "success": False,
                "message": f"说话人 {speaker_name} 不存在",
                "speaker_name": speaker_name
            }
        
        # 删除记录
        del _manager_state['speaker_db'][speaker_name]
        if speaker_name in _manager_state['speaker_embeddings']:
            del _manager_state['speaker_embeddings'][speaker_name]
        
        # 保存更改
        _save_database()
        _save_embeddings()
        
        logger.info(f"说话人 {speaker_name} 已删除")
        return {
            "success": True,
            "message": f"说话人 {speaker_name} 删除成功",
            "speaker_name": speaker_name
        }
        
    except Exception as e:
        logger.error(f"删除说话人失败: {str(e)}")
        return {
            "success": False,
            "message": f"删除失败: {str(e)}",
            "speaker_name": speaker_name
        }


def list_speakers() -> List[Dict]:
    """列出所有说话人
    
    Returns:
        List[Dict]: 说话人信息列表
    """
    global _manager_state
    
    if not _manager_state['initialized']:
        init_speaker_manager()
    
    return list(_manager_state['speaker_db'].values())


def get_speaker_info(speaker_name: str) -> Optional[Dict]:
    """获取说话人信息
    
    Args:
        speaker_name: 说话人名称
        
    Returns:
        Optional[Dict]: 说话人信息，不存在则返回None
    """
    global _manager_state
    
    if not _manager_state['initialized']:
        init_speaker_manager()
    
    return _manager_state['speaker_db'].get(speaker_name)


def get_statistics() -> Dict:
    """获取统计信息
    
    Returns:
        Dict: 统计信息
    """
    global _manager_state
    
    if not _manager_state['initialized']:
        init_speaker_manager()
    
    return {
        "total_speakers": len(_manager_state['speaker_db']),
        "total_embeddings": len(_manager_state['speaker_embeddings']),
        "similarity_threshold": _manager_state['similarity_threshold'],
        "database_path": _manager_state['db_path'],
        "embeddings_path": _manager_state['embeddings_path']
    }


# ============================================================================
# 便利函数 (向后兼容)
# ============================================================================

def get_speaker_manager(args: Optional[object] = None, **kwargs):
    """获取说话人管理器状态 (向后兼容)
    
    Args:
        args: 命令行参数对象 (可选)
        **kwargs: 其他参数
        
    Returns:
        dict: 管理器状态信息
    """
    global _manager_state
    
    if not _manager_state['initialized']:
        init_speaker_manager(args)
    
    return {
        'initialized': _manager_state['initialized'],
        'total_speakers': len(_manager_state['speaker_db']),
        'similarity_threshold': _manager_state['similarity_threshold']
    }


# ============================================================================
# 私有辅助函数
# ============================================================================

def _load_database():
    """加载说话人数据库"""
    global _manager_state
    
    try:
        if os.path.exists(_manager_state['db_path']):
            with open(_manager_state['db_path'], 'r', encoding='utf-8') as f:
                _manager_state['speaker_db'] = json.load(f)
            logger.info(f"已加载说话人数据库: {len(_manager_state['speaker_db'])} 个说话人")
        else:
            _manager_state['speaker_db'] = {}
            logger.info("说话人数据库文件不存在，创建新数据库")
    except Exception as e:
        logger.error(f"加载说话人数据库失败: {str(e)}")
        _manager_state['speaker_db'] = {}


def _load_embeddings():
    """加载说话人特征向量"""
    global _manager_state
    
    try:
        if os.path.exists(_manager_state['embeddings_path']):
            with open(_manager_state['embeddings_path'], 'rb') as f:
                _manager_state['speaker_embeddings'] = pickle.load(f)
            logger.info(f"已加载说话人特征向量: {len(_manager_state['speaker_embeddings'])} 个")
        else:
            _manager_state['speaker_embeddings'] = {}
            logger.info("特征向量文件不存在，创建新文件")
    except Exception as e:
        logger.error(f"加载特征向量失败: {str(e)}")
        _manager_state['speaker_embeddings'] = {}


def _save_database():
    """保存说话人数据库"""
    global _manager_state
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(_manager_state['db_path']), exist_ok=True)
        
        with open(_manager_state['db_path'], 'w', encoding='utf-8') as f:
            json.dump(_manager_state['speaker_db'], f, ensure_ascii=False, indent=2)
        logger.info("说话人数据库已保存")
    except Exception as e:
        logger.error(f"保存说话人数据库失败: {str(e)}")
        raise SpeakerManagerError(f"保存数据库失败: {str(e)}")


def _save_embeddings():
    """保存特征向量"""
    global _manager_state
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(_manager_state['embeddings_path']), exist_ok=True)
        
        with open(_manager_state['embeddings_path'], 'wb') as f:
            pickle.dump(_manager_state['speaker_embeddings'], f)
        logger.info("特征向量已保存")
    except Exception as e:
        logger.error(f"保存特征向量失败: {str(e)}")
        raise SpeakerManagerError(f"保存特征向量失败: {str(e)}")



def _find_similar_speakers_internal(query_embedding: np.ndarray,
                                  top_k: int = None) -> List[Dict]:
    """内部方法：查找相似说话人
    
    Args:
        query_embedding: 查询的特征向量
        top_k: 返回前k个最相似的结果，None表示返回所有
        
    Returns:
        按相似度降序排列的说话人列表
    """
    global _manager_state
    
    similarities = []
    
    # 计算与所有已注册说话人的相似度
    for speaker_name, embedding in _manager_state['speaker_embeddings'].items():
        similarity = cosine_similarity(
            query_embedding.reshape(1, -1),
            embedding.reshape(1, -1)
        )[0][0]
        
        similarities.append({
            "speaker_name": speaker_name,
            "similarity": float(similarity),
            "speaker_info": _manager_state['speaker_db'].get(speaker_name, {})
        })
    
    # 按相似度降序排序
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    
    # 限制返回数量
    if top_k:
        similarities = similarities[:top_k]
    
    return similarities

