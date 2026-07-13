#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的Python代码混淆脚本
使用基本的混淆技术对Python源码进行保护
"""

import os
import sys
import shutil
import base64
import zlib
from pathlib import Path

def obfuscate_file(file_path, output_path):
    """混淆单个Python文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 压缩并编码
    compressed = zlib.compress(content.encode('utf-8'))
    encoded = base64.b64encode(compressed).decode('ascii')
    
    # 生成混淆后的代码
    obfuscated_code = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Obfuscated by simple_obfuscate.py

import base64
import zlib

# Obfuscated code
_code = "{encoded}"

# Execute
exec(zlib.decompress(base64.b64decode(_code)).decode('utf-8'))
'''
    
    # 写入混淆后的文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(obfuscated_code)

def obfuscate_directory(src_dir, output_dir, exclude_patterns=None):
    """混淆整个目录"""
    if exclude_patterns is None:
        exclude_patterns = ['__pycache__', '.git', '.pytest_cache', 'tests']
    
    src_path = Path(src_dir)
    output_path = Path(output_dir)
    
    for file_path in src_path.rglob('*.py'):
        # 检查是否需要排除
        skip = False
        for pattern in exclude_patterns:
            if pattern in str(file_path):
                skip = True
                break
        
        if skip:
            continue
        
        # 计算相对路径
        rel_path = file_path.relative_to(src_path)
        output_file = output_path / rel_path
        
        print(f"混淆文件: {file_path} -> {output_file}")
        obfuscate_file(file_path, output_file)

def copy_non_python_files(src_dir, output_dir, exclude_patterns=None):
    """复制非Python文件"""
    if exclude_patterns is None:
        exclude_patterns = ['__pycache__', '.git', '.pytest_cache', 'tests', '*.pyc']
    
    src_path = Path(src_dir)
    output_path = Path(output_dir)
    
    for file_path in src_path.rglob('*'):
        if file_path.is_file() and not file_path.suffix == '.py':
            # 检查是否需要排除
            skip = False
            for pattern in exclude_patterns:
                if pattern in str(file_path) or file_path.name.endswith('.pyc'):
                    skip = True
                    break
            
            if skip:
                continue
            
            # 计算相对路径
            rel_path = file_path.relative_to(src_path)
            output_file = output_path / rel_path
            
            # 创建目录并复制文件
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            shutil.copy2(file_path, output_file)
            print(f"复制文件: {file_path} -> {output_file}")

def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"
    main_file = project_root / "main.py"
    output_dir = project_root / "dist" / "obfuscated"
    
    print("=== 简单Python代码混淆工具 ===")
    print(f"项目根目录: {project_root}")
    print(f"源码目录: {src_dir}")
    print(f"输出目录: {output_dir}")
    
    # 清理输出目录
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 混淆主文件
        if main_file.exists():
            print(f"\n混淆主文件: {main_file}")
            obfuscate_file(main_file, output_dir / "main.py")
        
        # 混淆src目录
        if src_dir.exists():
            print(f"\n混淆源码目录: {src_dir}")
            obfuscate_directory(src_dir, output_dir / "src")
        
        # 复制其他必要文件
        print("\n复制配置和数据文件...")
        for item in ['requirements.txt', 'config', 'data', 'models']:
            src_item = project_root / item
            if src_item.exists():
                if src_item.is_file():
                    shutil.copy2(src_item, output_dir / item)
                    print(f"复制文件: {src_item}")
                else:
                    copy_non_python_files(src_item, output_dir / item)
        
        # 创建启动脚本
        startup_script = output_dir / "start.sh"
        with open(startup_script, 'w') as f:
            f.write('''#!/bin/bash
# 混淆版本启动脚本
echo "启动混淆版本的WYL ASR服务器..."
python3 main.py "$@"
''')
        os.chmod(startup_script, 0o755)
        
        print(f"\n✅ 混淆完成!")
        print(f"混淆后的代码位于: {output_dir}")
        print(f"运行方式: cd {output_dir} && python3 main.py")
        print(f"或使用启动脚本: cd {output_dir} && ./start.sh")
        
    except Exception as e:
        print(f"❌ 混淆失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()