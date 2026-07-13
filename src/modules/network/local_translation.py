#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一翻译入口（本地 OPUS-MT）
==========================

启动时检测一次本地模型，之后固定使用该后端：
  - 本地模型存在  → Helsinki-NLP/opus-mt-zh-en（ctranslate2 量化版优先）
  - 本地模型不存在 → 翻译功能不可用，返回 None

调用方只需调用 translate(text)，无需关心使用的是哪个后端。

模型存放路径（与项目其他模型一致，位于 models/ 目录下）：
  <project_root>/models/opus-mt-zh-en-ct2/   ← ctranslate2 量化版（推荐）
  <project_root>/models/opus-mt-zh-en/        ← HuggingFace 原始格式（备用）

首次使用前需手动准备模型（任选其一）：

  方式 A：ctranslate2 量化版（推荐，CPU 单句约 50~150ms）
  ---------------------------------------------------------
  pip install ctranslate2 sentencepiece transformers
  ct2-opus-mt-convert \\
      --model Helsinki-NLP/opus-mt-zh-en \\
      --output_dir ./models/opus-mt-zh-en-ct2 \\
      --quantization int8

  方式 B：直接下载 HuggingFace 格式
  ------------------------------------
  pip install transformers sentencepiece
  python -c "
  from transformers import MarianMTModel, MarianTokenizer
  m = 'Helsinki-NLP/opus-mt-zh-en'
  MarianTokenizer.from_pretrained(m).save_pretrained('./models/opus-mt-zh-en')
  MarianMTModel.from_pretrained(m).save_pretrained('./models/opus-mt-zh-en')
  "
"""

import os
import logging
import asyncio
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# 内部状态（模块级单例）
# --------------------------------------------------------------------------
_engine: Optional[str] = None      # "ct2" | "hf" | None（未初始化或不可用）
_tokenizer = None
_model = None
_executor: Optional[ThreadPoolExecutor] = None
_initialized = False


# --------------------------------------------------------------------------
# 路径工具
# --------------------------------------------------------------------------
def _models_root() -> str:
    """返回项目 models/ 根目录（与其他 ASR 模型保持一致）。"""
    # 此文件位于 src/modules/network/local_translation.py
    # 向上三级到达项目根目录
    this_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(this_dir, '..', '..', '..'))
    return os.path.join(project_root, 'models')


def _find_local_model() -> tuple:
    """
    扫描 models/ 目录，查找可用的 OPUS-MT 模型。
    优先顺序：ctranslate2 量化版（更快）→ HuggingFace 原始格式（备用）
    Returns: (path, engine_type)  engine_type = "hf" | "ct2" | None
    """
    candidates = _find_local_models()
    return candidates[0] if candidates else (None, None)


def _find_local_models() -> list:
    """按优先级返回可用的 OPUS-MT 本地模型候选。"""
    root = _models_root()
    candidates = []

    # 优先：ctranslate2 量化版，上传长音频逐段翻译时明显更稳。
    ct2 = os.path.join(root, 'opus-mt-zh-en-ct2')
    if os.path.isdir(ct2) and os.path.exists(os.path.join(ct2, 'model.bin')):
        candidates.append((ct2, "ct2"))

    # 备用：HuggingFace 格式。
    hf = os.path.join(root, 'opus-mt-zh-en')
    if os.path.isdir(hf) and (
        os.path.exists(os.path.join(hf, 'pytorch_model.bin')) or
        os.path.exists(os.path.join(hf, 'model.safetensors'))
    ):
        candidates.append((hf, "hf"))

    return candidates


# --------------------------------------------------------------------------
# 引擎加载
# --------------------------------------------------------------------------
def _load_ct2(model_path: str) -> bool:
    try:
        import ctranslate2
        import sentencepiece as spm

        # source.spm 可能在 ct2 目录本身，也可能在同级 hf 目录
        sp_path = os.path.join(model_path, 'source.spm')
        if not os.path.exists(sp_path):
            hf_sibling = os.path.join(os.path.dirname(model_path), 'opus-mt-zh-en')
            sp_path = os.path.join(hf_sibling, 'source.spm')

        if not os.path.exists(sp_path):
            logger.error(f"[翻译] 找不到 source.spm，请确认分词器文件存在于: {sp_path}")
            return False

        global _tokenizer, _model
        sp = spm.SentencePieceProcessor()
        sp.Load(sp_path)
        _tokenizer = sp
        _model = ctranslate2.Translator(model_path, inter_threads=2, intra_threads=2)
        logger.info(f"[翻译] 已加载本地 ctranslate2 模型: {model_path}")
        return True
    except ImportError as e:
        logger.warning(f"[翻译] ctranslate2/sentencepiece 未安装: {e}")
        return False
    except Exception as e:
        logger.error(f"[翻译] ctranslate2 加载失败: {e}")
        return False


def _load_hf(model_path: str) -> bool:
    try:
        from transformers import MarianMTModel, MarianTokenizer

        global _tokenizer, _model
        _tokenizer = MarianTokenizer.from_pretrained(model_path)
        _model = MarianMTModel.from_pretrained(model_path)
        logger.info(f"[翻译] 已加载本地 HuggingFace 模型: {model_path}")
        return True
    except ImportError as e:
        logger.warning(f"[翻译] transformers 未安装: {e}")
        return False
    except Exception as e:
        logger.error(f"[翻译] HuggingFace 模型加载失败: {e}")
        return False


# --------------------------------------------------------------------------
# 初始化（启动时调用一次）
# --------------------------------------------------------------------------
def initialize() -> None:
    """
    检测本地模型，决定使用的翻译后端。
    - 找到本地模型 → 加载 OPUS-MT
    - 未找到       → 翻译不可用

    此函数只需调用一次，后续 translate() 自动路由到对应后端。
    """
    global _engine, _executor, _initialized

    if _initialized:
        return

    _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="opus_mt")

    _engine = None
    for path, engine_type in _find_local_models():
        if engine_type == "ct2" and _load_ct2(path):
            _engine = "ct2"
            break
        if engine_type == "hf" and _load_hf(path):
            _engine = "hf"
            break

    if not _engine:
        _engine = None
        logger.info(
            f"[翻译] 未在 {_models_root()} 找到本地 OPUS-MT 模型，"
            "翻译功能不可用。请参考 local_translation.py 顶部说明准备本地模型。"
        )

    _initialized = True
    logger.info(f"[翻译] 后端已确定: {_engine}")


def get_engine() -> Optional[str]:
    """返回当前使用的翻译后端名称。"""
    return _engine


# --------------------------------------------------------------------------
# 同步推理
# --------------------------------------------------------------------------
def _run_ct2(text: str) -> Optional[str]:
    try:
        tokens = _tokenizer.Encode(text.strip(), out_type=str)
        # 动态限制输出长度，防止长句无限循环
        max_len = max(60, len(tokens) * 2)
        results = _model.translate_batch(
            [tokens],
            beam_size=2,
            max_decoding_length=max_len,
            repetition_penalty=1.5,
            no_repeat_ngram_size=4,
        )
        output = results[0].hypotheses[0]
        return "".join(output).replace("\u2581", " ").strip()
    except Exception as e:
        logger.error(f"[翻译-ct2] 推理失败: {e}")
        return None


def _run_hf(text: str) -> Optional[str]:
    try:
        import torch
        inputs = _tokenizer(
            text.strip(),
            return_tensors="pt",
            padding=True,
            max_length=512,
            truncation=True,
        )
        with torch.no_grad():
            out = _model.generate(
                **inputs,
                num_beams=4,
                max_length=256,
                no_repeat_ngram_size=4,
                repetition_penalty=1.3,
                early_stopping=True,
            )
        return _tokenizer.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        logger.error(f"[翻译-hf] 推理失败: {e}")
        return None


# --------------------------------------------------------------------------
# 统一异步入口（调用方只用这个）
# --------------------------------------------------------------------------
async def translate(text: str) -> Optional[str]:
    """
    翻译中文文本为英文。

    自动路由到已选定的本地后端，调用方无需判断。

    Args:
        text: 待翻译的中文文本

    Returns:
        翻译结果，失败返回 None
    """
    if not text or not text.strip():
        return ""

    if not _initialized:
        initialize()

    if _engine in ("ct2", "hf"):
        # 本地推理：在线程池中运行，避免阻塞 asyncio 循环
        loop = asyncio.get_event_loop()
        fn = _run_ct2 if _engine == "ct2" else _run_hf
        try:
            return await loop.run_in_executor(_executor, fn, text)
        except Exception as e:
            logger.error(f"[翻译] 本地推理异步错误: {e}")
            return None

    else:
        logger.warning("[翻译] 本地翻译后端未初始化或不可用")
        return None


def get_status() -> dict:
    """健康检查用，返回当前后端状态。"""
    return {
        "engine": _engine,
        "initialized": _initialized,
        "models_root": _models_root(),
    }
