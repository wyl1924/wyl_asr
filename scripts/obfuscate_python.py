#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python代码混淆脚本
使用简单混淆方法对Python源码进行保护
"""

import os
import sys
import shutil
from pathlib import Path

# 导入简单混淆模块
sys.path.append(str(Path(__file__).parent))
from simple_obfuscate import obfuscate_directory, copy_non_python_files

def obfuscate_python_code():
    """混淆Python代码"""
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"
    main_file = project_root / "main.py"
    output_dir = project_root / "dist" / "obfuscated"
    
    # 清理输出目录
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("开始混淆Python代码...")
    
    try:
        # 使用简单混淆方法
        exclude_patterns = ['tests', 'docs', '__pycache__', '.git', '.pytest_cache']
        
        # 混淆主文件
        if main_file.exists():
            from simple_obfuscate import obfuscate_file
            obfuscate_file(str(main_file), str(output_dir / "main.py"))
            print(f"混淆主文件: {main_file}")
        
        # 混淆源码目录
        if src_dir.exists():
            obfuscate_directory(str(src_dir), str(output_dir / "src"), exclude_patterns)
            print(f"混淆源码目录: {src_dir}")
        
        # 复制其他必要文件
        copy_files = [
            "requirements.txt",
            "requirements-dev.txt",
            "config/",
            "utils/",
            "README.md",
            "LICENSE"
        ]
        
        for file_path in copy_files:
            src_path = project_root / file_path
            if src_path.exists():
                dest_path = output_dir / file_path
                if src_path.is_file():
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dest_path)
                    print(f"复制文件: {file_path}")
                else:
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                    print(f"复制目录: {file_path}")
        
        # 复制前端构建产物（如果存在）
        ui_dist = project_root / "ui" / "dist"
        if ui_dist.exists():
            shutil.copytree(ui_dist, output_dir / "ui" / "dist", dirs_exist_ok=True)
            print("复制前端构建产物: ui/dist/")
        
        # 创建启动脚本
        create_startup_script(output_dir)
        
        print("Python代码混淆完成！")
        
        print(f"\n混淆完成！输出目录: {output_dir}")
        print("\n使用方法:")
        print(f"cd {output_dir}")
        print("python main.py")
        
    except Exception as e:
        print(f"混淆过程中发生错误: {e}")
        sys.exit(1)

def create_startup_script(output_dir):
    """创建启动脚本"""
    # Linux/macOS启动脚本
    startup_sh = output_dir / "start.sh"
    with open(startup_sh, 'w', encoding='utf-8') as f:
        f.write("""#!/bin/bash
# WYL ASR 混淆版本启动脚本

set -e

echo "启动 WYL ASR 服务器..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查依赖
if [ -f "requirements.txt" ]; then
    echo "检查依赖..."
    python3 -m pip install -r requirements.txt
fi

# 启动服务器
echo "启动服务器..."
python3 main.py "$@"
""")
    
    # 设置执行权限
    startup_sh.chmod(0o755)
    
    # Windows启动脚本
    startup_bat = output_dir / "start.bat"
    with open(startup_bat, 'w', encoding='utf-8') as f:
        f.write("""@echo off
REM WYL ASR 混淆版本启动脚本

echo 启动 WYL ASR 服务器...

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python
    pause
    exit /b 1
)

REM 检查依赖
if exist requirements.txt (
    echo 检查依赖...
    python -m pip install -r requirements.txt
)

REM 启动服务器
echo 启动服务器...
python main.py %*

if errorlevel 1 (
    echo 服务器启动失败
    pause
)
""")
    
    print("创建启动脚本: start.sh, start.bat")

if __name__ == "__main__":
    obfuscate_python_code()