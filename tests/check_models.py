#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型完整性检查工具。

用于验证项目中所有模型文件的完整性和大小，确保模型文件正确下载和配置。
"""

import os
import sys
from pathlib import Path

# 添加utils模块到路径
sys.path.append(str(Path(__file__).parent / 'utils'))

from organize_models import get_project_models_dir, check_model_completeness


def get_file_size_mb(file_path: str) -> float:
    """获取文件大小（MB）。
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件大小（MB）
    """
    if os.path.exists(file_path):
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    return 0.0


def check_all_models() -> None:
    """检查所有模型的完整性。"""
    models_dir = get_project_models_dir()
    
    if not os.path.exists(models_dir):
        print(f"❌ 模型目录不存在: {models_dir}")
        return
    
    print("🔍 检查模型完整性:")
    print("=" * 50)
    
    model_dirs = [d for d in os.listdir(models_dir) 
                  if os.path.isdir(os.path.join(models_dir, d))]
    
    complete_models = 0
    total_models = len(model_dirs)
    
    for model_name in sorted(model_dirs):
        model_path = os.path.join(models_dir, model_name)
        is_complete = check_model_completeness(model_path)
        
        status = "✅ 完整" if is_complete else "❌ 不完整"
        print(f"{model_name}: {status}")
        
        if is_complete:
            complete_models += 1
    
    print("\n📊 模型统计:")
    print("=" * 50)
    print(f"完整模型: {complete_models}/{total_models}")
    
    if complete_models == total_models:
        print("🎉 所有模型都完整！")
    else:
        print(f"⚠️  有 {total_models - complete_models} 个模型不完整")
    
    # 显示模型文件大小
    print("\n📁 模型文件大小:")
    print("=" * 50)
    
    for model_name in sorted(model_dirs):
        model_path = os.path.join(models_dir, model_name)
        if check_model_completeness(model_path):
            model_file = os.path.join(model_path, "model.pt")
            size_mb = get_file_size_mb(model_file)
            print(f"{model_name}: {size_mb:.1f} MB")


if __name__ == "__main__":
    check_all_models()