#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPUS-MT 翻译模型下载 & 转换脚本
=================================

用法：
    cd wyl_asr          # 切换到项目根目录（含 models/ 的那一级）
    python scripts/download_opus_mt.py

完成后目录结构：
    models/
    ├── opus-mt-zh-en/        # HuggingFace 原始格式（备用）
    └── opus-mt-zh-en-ct2/    # ctranslate2 量化版（主用，更快）

如果服务器无法访问 HuggingFace，可以：
    1. 在能访问的机器上跑此脚本
    2. 将 models/opus-mt-zh-en-ct2/ 整个目录拷贝到服务器
"""

import os
import sys


def check_deps():
    missing = []
    for pkg in ["transformers", "ctranslate2", "sentencepiece"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"❌ 缺少依赖: {', '.join(missing)}")
        print(f"   请先执行: pip install {' '.join(missing)}")
        sys.exit(1)
    print("✅ 依赖检查通过")


def get_models_dir():
    """返回 models/ 目录（脚本从项目根或 scripts/ 均可运行）。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 如果在 scripts/ 里，向上一级
    if os.path.basename(script_dir) == "scripts":
        root = os.path.dirname(script_dir)
    else:
        root = script_dir
    return os.path.join(root, "models")


def download_hf_model(hf_path: str):
    """从 HuggingFace 下载原始权重到 models/opus-mt-zh-en/。"""
    from transformers import MarianMTModel, MarianTokenizer

    model_name = "Helsinki-NLP/opus-mt-zh-en"
    print(f"\n📥 下载 HuggingFace 模型: {model_name}")
    print(f"   目标路径: {hf_path}")
    print("   （首次下载约 300MB，请耐心等待…）\n")

    tokenizer = MarianTokenizer.from_pretrained(model_name)
    tokenizer.save_pretrained(hf_path)
    print("   ✅ 分词器已保存")

    model = MarianMTModel.from_pretrained(model_name)
    model.save_pretrained(hf_path)
    print("   ✅ 模型权重已保存")


def convert_to_ct2(hf_path: str, ct2_path: str):
    """使用 ctranslate2 将 HF MarianMT 模型转换为 INT8 量化版。"""
    import ctranslate2

    print(f"\n⚙️  转换为 ctranslate2 INT8 量化格式")
    print(f"   输入: {hf_path}")
    print(f"   输出: {ct2_path}")

    # HuggingFace 格式的 MarianMT 需要使用 TransformersConverter
    converter = ctranslate2.converters.TransformersConverter(hf_path)
    converter.convert(ct2_path, quantization="int8", force=True)
    print("   ✅ 转换完成")

    # 把 source.spm 也复制到 ct2 目录，供推理时使用
    import shutil
    src_spm = os.path.join(hf_path, "source.spm")
    dst_spm = os.path.join(ct2_path, "source.spm")
    if os.path.exists(src_spm) and not os.path.exists(dst_spm):
        shutil.copy2(src_spm, dst_spm)
        print("   ✅ source.spm 已复制")



def verify_ct2(ct2_path: str):
    """简单验证：加载模型并翻译一句话。"""
    import ctranslate2
    import sentencepiece as spm

    print("\n🧪 验证翻译效果…")
    sp = spm.SentencePieceProcessor()
    sp.Load(os.path.join(ct2_path, "source.spm"))

    translator = ctranslate2.Translator(ct2_path, inter_threads=1, intra_threads=2)

    test_sentences = ["你好，今天开会的议题是什么？", "请大家认真听讲。"]
    for text in test_sentences:
        tokens = sp.Encode(text, out_type=str)
        results = translator.translate_batch([tokens])
        output = "".join(results[0].hypotheses[0]).replace("▁", " ").strip()
        print(f"   [{text}] → [{output}]")

    print("✅ 验证通过，模型可正常使用！")


def main():
    print("=" * 60)
    print("  OPUS-MT 本地翻译模型下载 & 转换工具")
    print("=" * 60)

    check_deps()

    models_dir = get_models_dir()
    os.makedirs(models_dir, exist_ok=True)

    hf_path  = os.path.join(models_dir, "opus-mt-zh-en")
    ct2_path = os.path.join(models_dir, "opus-mt-zh-en-ct2")

    # Step 1: 下载 HF 格式（如果还没有）
    if os.path.isdir(hf_path) and (
        os.path.exists(os.path.join(hf_path, "pytorch_model.bin")) or
        os.path.exists(os.path.join(hf_path, "model.safetensors"))
    ):
        print(f"\n✅ 已有 HuggingFace 模型，跳过下载: {hf_path}")
    else:
        download_hf_model(hf_path)

    # Step 2: 转换为 ct2（如果还没有）
    if os.path.isdir(ct2_path) and os.path.exists(os.path.join(ct2_path, "model.bin")):
        print(f"\n✅ 已有 ctranslate2 模型，跳过转换: {ct2_path}")
    else:
        convert_to_ct2(hf_path, ct2_path)

    # Step 3: 验证
    verify_ct2(ct2_path)

    print("\n" + "=" * 60)
    print("  🎉 完成！翻译模型已就绪。")
    print(f"     主用路径: {ct2_path}")
    print(f"     备用路径: {hf_path}")
    print("\n  启动服务后翻译功能将自动使用本地模型，无需讯飞 API。")
    print("=" * 60)


if __name__ == "__main__":
    main()
