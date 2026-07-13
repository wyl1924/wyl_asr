#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型下载和整理工具。

自动下载FunASR所需的模型文件，并整理到项目的models目录中。
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List


def get_modelscope_cache_dir() -> str:
    """获取ModelScope缓存目录。"""
    return os.path.expanduser("~/.cache/modelscope/hub/models")


def get_project_models_dir() -> str:
    """获取项目models目录。"""
    project_root = Path(__file__).resolve().parent
    return str(project_root / "models")


def check_model_completeness(model_path: str) -> bool:
    """检查模型文件是否完整。
    
    Args:
        model_path: 模型目录路径
        
    Returns:
        如果模型文件完整返回True，否则返回False
    """
    if not os.path.exists(model_path):
        return False
    
    # 检查配置文件（必须存在）
    config_files = ['config.yaml', 'configuration.json', 'config.json']
    if not any(os.path.exists(os.path.join(model_path, item)) for item in config_files):
        return False
    
    # 检查模型文件（至少存在一种格式）
    model_files = [
        'model.pt',           # PyTorch模型
        'model.onnx',         # 标准ONNX模型
        'model_quant.onnx',   # 量化ONNX模型
        'model.torchscript',  # TorchScript模型
        'model.safetensors',  # safetensors模型
        'pytorch_model.bin',  # HuggingFace模型
        'campplus_cn_common.bin',
        'zh_itn_tagger.fst',
        'zh_itn_verbalizer.fst',
    ]
    
    # 至少要有一个模型文件存在
    for model_file in model_files:
        model_file_path = os.path.join(model_path, model_file)
        if os.path.exists(model_file_path):
            return True
    
    return False


def download_model_with_modelscope(model_name: str) -> bool:
    """使用ModelScope下载模型。
    
    Args:
        model_name: 模型名称，如 'iic/SenseVoiceSmall'
        
    Returns:
        下载成功返回True，否则返回False
    """
    try:
        from modelscope import snapshot_download
        
        print(f"📥 正在下载模型: {model_name}")
        snapshot_download(model_name)
        print(f"✅ 模型下载完成: {model_name}")
        return True
        
    except ImportError:
        print("❌ 未安装modelscope库，请先安装: pip install modelscope")
        return False
    except Exception as e:
        print(f"❌ 下载模型失败 {model_name}: {e}")
        return False


def copy_model_to_project(source_path: str, target_path: str) -> bool:
    """将模型文件复制到项目目录。
    
    Args:
        source_path: 源模型路径
        target_path: 目标模型路径
        
    Returns:
        复制成功返回True，否则返回False
    """
    try:
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        
        # 创建目标目录的父目录
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # 复制整个模型目录
        shutil.copytree(source_path, target_path)
        print(f"📁 模型已复制到: {target_path}")
        return True
        
    except Exception as e:
        print(f"❌ 复制模型失败: {e}")
        return False


def organize_models() -> None:
    """整理所有模型文件。"""
    # 定义需要的模型
    models_config = {
        # ASR模型 - PyTorch版本
        'SenseVoiceSmall': 'iic/SenseVoiceSmall',
        'speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch':
            'iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch',
        
        
        # 标点恢复模型（已废弃：SenseVoice 自带标点输出，无需单独标点模型）
        # 'punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727': 'iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727',
        
        # VAD模型
        'speech_fsmn_vad_zh-cn-16k-common-pytorch': 'iic/speech_fsmn_vad_zh-cn-16k-common-pytorch',
        
        
        # 语言模型和ITN模型 (FunASR官方2pass服务器需要)
        # 'speech_ngram_lm_zh-cn-ai-wesp-fst': 'damo/speech_ngram_lm_zh-cn-ai-wesp-fst',
        'fst_itn_zh': 'thuduj12/fst_itn_zh',
        
        # 说话人识别模型 (CAM++系列)
        'speech_campplus_sv_zh-cn_16k-common': 'iic/speech_campplus_sv_zh-cn_16k-common',
        # 'speech_campplus_sv_zh_en_16k-common_advanced': 'damo/speech_campplus_sv_zh_en_16k-common_advanced',
        # 'speech_campplus_sv_zh-cn_16k-common_damo': 'damo/speech_campplus_sv_zh-cn_16k-common',
        
        # 翻译模型
        # 'nlp_csanmt_translation_zh2en': 'iic/nlp_csanmt_translation_zh2en',
        
        # 文档分段模型
        'nlp_bert_document-segmentation_chinese-base': 'iic/nlp_bert_document-segmentation_chinese-base'
    }
    
    cache_dir = get_modelscope_cache_dir()
    project_models_dir = get_project_models_dir()
    
    print(f"🎯 ModelScope缓存目录: {cache_dir}")
    print(f"🎯 项目模型目录: {project_models_dir}")
    print("="*60)
    
    # 创建项目models目录
    os.makedirs(project_models_dir, exist_ok=True)
    
    for local_name, full_model_name in models_config.items():
        print(f"\n🔍 处理模型: {local_name} ({full_model_name})")
        
        # 检查项目目录中是否已有完整模型
        project_model_path = os.path.join(project_models_dir, local_name)
        if check_model_completeness(project_model_path):
            print(f"✅ 项目中已存在完整模型: {local_name}")
            continue
        
        # 检查缓存目录中是否有完整模型
        if '/' in full_model_name:
            org, model = full_model_name.split('/', 1)
            cache_model_path = os.path.join(cache_dir, org, model)
        else:
            cache_model_path = os.path.join(cache_dir, full_model_name)
        
        if check_model_completeness(cache_model_path):
            print(f"📁 在缓存中找到完整模型: {cache_model_path}")
            # 复制到项目目录
            copy_model_to_project(cache_model_path, project_model_path)
        else:
            print(f"📥 缓存中无完整模型，开始下载: {full_model_name}")
            # 下载模型
            if download_model_with_modelscope(full_model_name):
                # 下载完成后复制到项目目录
                if check_model_completeness(cache_model_path):
                    copy_model_to_project(cache_model_path, project_model_path)
                else:
                    print(f"❌ 下载的模型文件不完整: {full_model_name}")
            else:
                print(f"❌ 模型下载失败: {full_model_name}")
    
    print("\n" + "="*60)
    print("🎉 模型整理完成!")
    
    # 显示最终的模型目录结构
    print(f"\n📂 项目模型目录结构:")
    if os.path.exists(project_models_dir):
        for item in os.listdir(project_models_dir):
            item_path = os.path.join(project_models_dir, item)
            if os.path.isdir(item_path):
                size = sum(os.path.getsize(os.path.join(item_path, f)) 
                          for f in os.listdir(item_path) 
                          if os.path.isfile(os.path.join(item_path, f)))
                size_mb = size / (1024 * 1024)
                print(f"  📁 {item} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    try:
        organize_models()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        sys.exit(1)
