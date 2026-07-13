#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块级混淆脚本
对关键模块进行单独混淆
"""

import os
import subprocess
import shutil
from pathlib import Path

def obfuscate_critical_modules():
    """混淆关键模块"""
    project_root = Path(__file__).parent.parent
    
    # 需要重点保护的模块
    critical_modules = [
        "src/modules/core/",
        "src/modules/audio/",
        "src/modules/speaker/",
        "src/modules/database/",
        "src/modules/network/"
    ]
    
    base_output_dir = project_root / "dist" / "modules"
    base_output_dir.mkdir(parents=True, exist_ok=True)
    
    print("开始混淆关键模块...")
    
    for module_path in critical_modules:
        module_dir = project_root / module_path
        if not module_dir.exists():
            print(f"跳过不存在的模块: {module_path}")
            continue
            
        output_dir = base_output_dir / module_dir.name
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"混淆模块: {module_path}")
        
        try:
            # 检查PyArmor是否安装
            try:
                subprocess.run(["pyarmor", "--version"], check=True, capture_output=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("错误: PyArmor未安装，请运行: pip install pyarmor")
                return False
            
            # 使用PyArmor gen命令混淆模块
            cmd = [
                "pyarmor", "gen",
                "--output", str(output_dir),
                "--recursive",
                "--exclude", "__pycache__",
                "--exclude", "*.pyc",
                "--exclude", "tests",
                str(module_dir)
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"模块 {module_dir.name} 混淆完成")
            
            # 显示混淆结果
            if result.stdout:
                print(f"输出: {result.stdout.strip()}")
            
        except subprocess.CalledProcessError as e:
            print(f"模块 {module_dir.name} 混淆失败: {e}")
            if e.stderr:
                print(f"错误信息: {e.stderr}")
            continue
        except Exception as e:
            print(f"处理模块 {module_dir.name} 时发生错误: {e}")
            continue
    
    print("\n关键模块混淆完成！")
    return True

def obfuscate_single_files():
    """混淆单个重要文件"""
    project_root = Path(__file__).parent.parent
    
    # 需要单独混淆的重要文件
    important_files = [
        "main.py",
        "ui_server.py",
        "organize_models.py"
    ]
    
    output_dir = project_root / "dist" / "single_files"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n开始混淆重要单文件...")
    
    for file_path in important_files:
        file_full_path = project_root / file_path
        if not file_full_path.exists():
            print(f"跳过不存在的文件: {file_path}")
            continue
        
        file_output_dir = output_dir / file_full_path.stem
        if file_output_dir.exists():
            shutil.rmtree(file_output_dir)
        file_output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"混淆文件: {file_path}")
        
        try:
            cmd = [
                "pyarmor", "gen",
                "--output", str(file_output_dir),
                str(file_full_path)
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"文件 {file_path} 混淆完成")
            
        except subprocess.CalledProcessError as e:
            print(f"文件 {file_path} 混淆失败: {e}")
            if e.stderr:
                print(f"错误信息: {e.stderr}")
            continue
        except Exception as e:
            print(f"处理文件 {file_path} 时发生错误: {e}")
            continue
    
    print("重要单文件混淆完成！")

def create_module_info():
    """创建模块信息文件"""
    project_root = Path(__file__).parent.parent
    info_file = project_root / "dist" / "modules" / "module_info.txt"
    
    with open(info_file, 'w', encoding='utf-8') as f:
        f.write("WYL ASR 模块混淆信息\n")
        f.write("=" * 50 + "\n")
        f.write(f"混淆时间: {__import__('datetime').datetime.now()}\n")
        f.write("\n混淆的模块:\n")
        
        modules_dir = project_root / "dist" / "modules"
        if modules_dir.exists():
            for item in modules_dir.iterdir():
                if item.is_dir() and item.name != "__pycache__":
                    f.write(f"- {item.name}/\n")
        
        f.write("\n使用说明:\n")
        f.write("1. 这些是经过PyArmor混淆的Python模块\n")
        f.write("2. 混淆后的代码具有反调试和反逆向功能\n")
        f.write("3. 请勿尝试反编译或修改混淆后的代码\n")
        f.write("4. 如需技术支持，请联系开发团队\n")
    
    print(f"创建模块信息文件: {info_file}")

if __name__ == "__main__":
    success = obfuscate_critical_modules()
    if success:
        obfuscate_single_files()
        create_module_info()
        print("\n所有模块混淆任务完成！")
    else:
        print("\n模块混淆任务失败！")