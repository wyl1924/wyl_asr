"""
项目配置文件
"""

import os

# 基础配置
PROJECT_NAME = "WYL ASR"
VERSION = "0.1.0"
DEBUG = False

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 日志配置
LOG_LEVEL = "INFO" if not DEBUG else "DEBUG"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 其他配置
DEFAULT_ENCODING = "utf-8"
MAX_WORKERS = 4