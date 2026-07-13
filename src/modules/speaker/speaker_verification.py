#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""说话人验证模块。

提供说话人身份验证和特征提取功能，支持音频文件和字节流输入。
"""

import os
import logging
import numpy as np
from typing import Dict, List, Optional, Union, Tuple
import torch
import torch.nn.functional as F
from funasr import AutoModel
from sklearn.metrics.pairwise import cosine_similarity
from ..core.server_state import get_local_model_path

class SpeakerVerificationError(Exception):
    """说话人验证相关异常。"""
    pass


def check_audio_file(audio_path: str) -> Dict:
    """检查音频文件的基本信息"""
    try:
        if not os.path.exists(audio_path):
            return {"valid": False, "error": f"文件不存在: {audio_path}"}

        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            return {"valid": False, "error": "文件大小为0"}

        # 检查文件扩展名
        ext = os.path.splitext(audio_path)[1].lower()
        supported_formats = ['.wav', '.mp3', '.flac', '.m4a', '.aac']
        if ext not in supported_formats:
            return {"valid": False, "error": f"不支持的音频格式: {ext}"}

        return {
            "valid": True,
            "size": file_size,
            "format": ext,
            "path": audio_path
        }
    except Exception as e:
        return {"valid": False, "error": f"检查文件时出错: {str(e)}"}


# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 全局模型状态
_model_state = {
    'model': None,
    'model_name': None,
    'device': None,
    'threshold': None,
    'cache_dir': None,
    'args': None
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
    """加载说话人验证模型"""
    global _model_state
    
    # 获取args参数
    if args is None:
        try:
            from ..core.server_state import server_state
            args = getattr(server_state, 'args', None)
        except:
            args = None
    
    # 设置模型参数
    model_name = getattr(args, 'speaker_model', None)
    device = getattr(args, 'device', None)
    threshold = getattr(args, 'speaker_threshold', 0.8)
    cache_dir = getattr(args, 'cache_dir', None)
    
    # 如果未指定模型名称，使用默认模型
    if not model_name:
        model_name = "iic/speech_campplus_sv_zh-cn_16k-common"
        logger.info(f"使用默认说话人验证模型: {model_name}")

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    local_model_path = get_local_model_path(model_name, root_dir)
    model_ref = local_model_path or model_name
    
    _model_state.update({
        'model_name': model_ref,
        'device': device,
        'threshold': threshold,
        'cache_dir': cache_dir,
        'args': args
    })
    
    logger.info(f"说话人验证模型配置: {model_ref}")
    logger.info(f"设备: {device}, 阀值: {threshold}")
    
    # 预检查本地缓存，不存在时提前记录警告（ModelScope 仍会自动下载，不影响主流程）
    if not local_model_path:
        logger.error(
            f"本地未找到说话人验证模型 {model_name}，已跳过加载。"
            "请先运行 `.venv/bin/python organize_models.py` 将模型下载/整理到项目 models 目录"
        )
        _model_state['model'] = None
        return
    
    logger.info(f"准备加载说话人验证模型: {model_ref}")
        
    try:
        logger.info(f"正在尝试加载说话人验证模型: {model_ref}")
        logger.info(f"设备: {device}")

        # 配置模型参数
        model_kwargs = {
            "model": model_ref,
        }
        if device:
            model_kwargs["device"] = device

        # 加载模型
        logger.info("开始加载 AutoModel...")
        _model_state['model'] = AutoModel(**model_kwargs)
        logger.info(f"说话人验证模型加载成功: {model_ref}")

        # 测试模型是否可用
        logger.info("测试模型可用性...")
        model_info = get_model_info()
        logger.info(f"模型信息: {model_info}")

    except Exception as e:
        logger.warning(f"模型 {model_ref} 加载失败: {str(e)}")
        logger.warning(f"说话人验证功能将不可用")
        logger.info("💡 如需使用说话人验证功能，请先下载相应模型")
        _model_state['model'] = None


def extract_embedding(audio_input: Union[str, bytes]) -> np.ndarray:
    """
    提取说话人特征向量

    Args:
        audio_input: 音频文件路径或音频数据

    Returns:
        说话人特征向量
    """
    if _model_state['model'] is None:
        logger.info("🔊 说话人验证模型未在内存中，执行按需延迟加载...")
        _load_model(_model_state.get('args'))
        if _model_state['model'] is None:
            raise SpeakerVerificationError("说话人验证模型未加载，请确保模型文件存在或先下载模型")

    try:
        logger.info(f"开始提取说话人特征: {type(audio_input)}")

        # 处理字节数据（来自前端的Base64解码）
        if isinstance(audio_input, bytes):
            logger.info(f"处理字节数据，长度: {len(audio_input)}")
            # 将字节数据保存为临时文件
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_input)
                temp_file_path = temp_file.name
            
            try:
                # 使用临时文件路径进行特征提取
                logger.info(f"使用临时文件进行特征提取: {temp_file_path}")
                audio_input = temp_file_path
            except Exception as e:
                # 清理临时文件
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                raise e

        # 检查音频文件
        if isinstance(audio_input, str):
            audio_check = check_audio_file(audio_input)
            if not audio_check["valid"]:
                raise SpeakerVerificationError(f"音频文件检查失败: {audio_check['error']}")
            logger.info(f"音频文件检查通过: {audio_check}")

        # 提取特征
        logger.info("调用模型进行特征提取...")
        result = _model_state['model'].generate(input=audio_input)
        
        # 如果使用了临时文件，清理它
        if isinstance(audio_input, str) and '/tmp' in audio_input:
            try:
                os.unlink(audio_input)
                logger.info("临时文件已清理")
            except:
                pass

        logger.info(f"模型返回结果类型: {type(result)}")
        logger.info(f"模型返回结果长度: {len(result) if result else 0}")

        if result and len(result) > 0:
            logger.info(f"结果第一项内容: {result[0]}")
            logger.info(f"结果第一项键: {list(result[0].keys()) if isinstance(result[0], dict) else 'Not a dict'}")

            # 尝试多种可能的键名
            embedding = None
            possible_keys = ["embedding", "embeddings", "feature", "features", "vector", "output"]

            for key in possible_keys:
                if isinstance(result[0], dict) and key in result[0]:
                    embedding = result[0][key]
                    logger.info(f"找到特征向量，键名: {key}")
                    break

            # 如果没找到，尝试直接使用结果
            if embedding is None:
                if isinstance(result[0], (np.ndarray, torch.Tensor)):
                    embedding = result[0]
                    logger.info("直接使用结果作为特征向量")
                elif isinstance(result[0], dict):
                    # 尝试获取第一个数组类型的值
                    for key, value in result[0].items():
                        if isinstance(value, (np.ndarray, torch.Tensor)):
                            embedding = value
                            logger.info(f"使用键 {key} 的值作为特征向量")
                            break

            if embedding is not None:
                logger.info(f"原始特征向量类型: {type(embedding)}")
                logger.info(f"原始特征向量形状: {embedding.shape if hasattr(embedding, 'shape') else 'No shape'}")

                # 确保是 numpy 数组
                if isinstance(embedding, torch.Tensor):
                    embedding = embedding.cpu().numpy()
                    logger.info("转换 Tensor 为 numpy 数组")

                # 确保是一维数组
                if len(embedding.shape) > 1:
                    embedding = embedding.flatten()
                    logger.info(f"展平为一维数组，新形状: {embedding.shape}")

                # 检查向量是否有效
                if embedding.size == 0:
                    raise SpeakerVerificationError("特征向量为空")

                # 标准化特征向量
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                    logger.info("特征向量标准化完成")
                else:
                    raise SpeakerVerificationError("特征向量的范数为0，无法标准化")

                logger.info(f"最终特征向量维度: {embedding.shape}")
                return embedding
            else:
                raise SpeakerVerificationError("在模型输出中未找到特征向量")
        else:
            raise SpeakerVerificationError("模型返回结果为空")

    except Exception as e:
        logger.error(f"特征提取失败: {str(e)}")
        logger.error(f"错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        raise


def verify_speakers(audio1: Union[str, bytes], 
                   audio2: Union[str, bytes]) -> Dict:
    """
    验证两个音频是否为同一说话人
    
    Args:
        audio1: 第一个音频
        audio2: 第二个音频
        
    Returns:
        验证结果字典
    """
    try:
        logger.info("开始说话人验证...")
        
        # 提取特征向量
        embedding1 = extract_embedding(audio1)
        embedding2 = extract_embedding(audio2)
        
        # 计算余弦相似度
        similarity = cosine_similarity(
            embedding1.reshape(1, -1), 
            embedding2.reshape(1, -1)
        )[0][0]
        
        # 判断是否为同一说话人
        threshold = _model_state['threshold'] or 0.8
        is_same_speaker = similarity >= threshold
        
        result = {
            "similarity": float(similarity),
            "threshold": threshold,
            "is_same_speaker": is_same_speaker,
            "confidence": float(abs(similarity - threshold)),
            "embedding1_shape": embedding1.shape,
            "embedding2_shape": embedding2.shape
        }
        
        logger.info(f"验证完成，相似度: {similarity:.4f}, 同一说话人: {is_same_speaker}")
        return result
        
    except Exception as e:
        logger.error(f"说话人验证失败: {str(e)}")
        raise


def compute_similarity_matrix(audio_files: List[str]) -> np.ndarray:
    """
    计算多个音频文件的相似度矩阵
    
    Args:
        audio_files: 音频文件路径列表
        
    Returns:
        相似度矩阵
    """
    try:
        logger.info(f"计算 {len(audio_files)} 个音频的相似度矩阵")
        
        # 提取所有特征向量
        embeddings = []
        for audio_file in audio_files:
            embedding = extract_embedding(audio_file)
            embeddings.append(embedding)
        
        # 转换为矩阵
        embeddings_matrix = np.vstack(embeddings)
        
        # 计算相似度矩阵
        similarity_matrix = cosine_similarity(embeddings_matrix)
        
        logger.info("相似度矩阵计算完成")
        return similarity_matrix
        
    except Exception as e:
        logger.error(f"相似度矩阵计算失败: {str(e)}")
        raise


def find_similar_speakers(target_audio: Union[str, bytes],
                         reference_audios: List[str],
                         top_k: int = 5) -> List[Dict]:
    """
    在参考音频中找到最相似的说话人
    
    Args:
        target_audio: 目标音频
        reference_audios: 参考音频列表
        top_k: 返回前k个最相似的结果
        
    Returns:
        相似度排序结果列表
    """
    try:
        logger.info(f"在 {len(reference_audios)} 个参考音频中查找相似说话人")
        
        # 提取目标音频特征
        target_embedding = extract_embedding(target_audio)
        
        # 计算与所有参考音频的相似度
        similarities = []
        threshold = _model_state['threshold'] or 0.8
        
        for i, ref_audio in enumerate(reference_audios):
            try:
                ref_embedding = extract_embedding(ref_audio)
                similarity = cosine_similarity(
                    target_embedding.reshape(1, -1),
                    ref_embedding.reshape(1, -1)
                )[0][0]
                
                similarities.append({
                    "index": i,
                    "audio_path": ref_audio,
                    "similarity": float(similarity),
                    "is_match": similarity >= threshold
                })
                
            except Exception as e:
                logger.warning(f"处理参考音频 {ref_audio} 失败: {str(e)}")
                similarities.append({
                    "index": i,
                    "audio_path": ref_audio,
                    "similarity": 0.0,
                    "is_match": False,
                    "error": str(e)
                })
        
        # 按相似度排序
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        # 返回前k个结果
        top_results = similarities[:top_k]
        
        logger.info(f"找到 {len(top_results)} 个相似结果")
        return top_results
        
    except Exception as e:
        logger.error(f"相似说话人查找失败: {str(e)}")
        raise


def set_threshold(threshold: float):
    """设置相似度阈值"""
    _model_state['threshold'] = threshold
    logger.info(f"相似度阈值已设置为: {threshold}")


def get_model_info() -> Dict:
    """获取模型信息"""
    return {
        "model_name": _model_state['model_name'],
        "device": _model_state['device'],
        "threshold": _model_state['threshold'],
        "model_loaded": _model_state['model'] is not None
    }


def init_speaker_verification(args: Optional[object] = None):
    """初始化说话人验证模块，仅保存配置参数，真正提取特征时才按需加载模型以释放显存
    
    Args:
        args: 命令行参数对象 (可选)
    """
    global _model_state
    _model_state['args'] = args
    logger.info("📝 说话人验证模块已登记配置，开启延迟按需加载机制")


def extract_speaker_embedding(audio_input: Union[str, bytes]) -> np.ndarray:
    """便捷的特征提取函数"""
    return extract_embedding(audio_input)
