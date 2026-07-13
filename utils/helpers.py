"""
辅助工具函数
"""

import os
import json
from datetime import datetime

def get_current_time():
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_json_file(file_path):
    """加载JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"文件未找到: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"JSON格式错误: {file_path}")
        return None

def save_json_file(data, file_path):
    """保存数据到JSON文件"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存文件失败: {e}")
        return False

def ensure_dir_exists(dir_path):
    """确保目录存在"""
    os.makedirs(dir_path, exist_ok=True)