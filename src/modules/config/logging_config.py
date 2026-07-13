#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日志配置模块。

提供完整的日志系统配置功能，支持多级别、多输出目标的日志记录。
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class LoggingConfigError(Exception):
    """日志配置相关异常。"""
    pass


def setup_logging(
    log_dir: Optional[str] = None,
    logger_name: str = "funasr_server",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """配置应用程序日志系统。

    设置多级别日志输出：
    - INFO级别：输出到控制台，显示基本运行信息
    - DEBUG级别：输出到文件，记录详细调试信息
    - ERROR级别：输出到错误文件，记录异常信息

    Args:
        log_dir: 日志文件目录路径，默认为 'logs'
        logger_name: 日志记录器名称，默认为 'funasr_server'
        console_level: 控制台日志级别，默认为 INFO
        file_level: 文件日志级别，默认为 DEBUG

    Returns:
        logging.Logger: 配置好的日志记录器

    Raises:
        LoggingConfigError: 当日志配置失败时抛出

    Examples:
        >>> logger = setup_logging()
        >>> logger.info("服务器启动")
        >>> logger = setup_logging(log_dir="/tmp/logs", logger_name="my_app")
    """
    if log_dir is None:
        log_dir = "logs"

    # 创建主日志记录器
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加处理器
    if logger.handlers:
        logger.handlers.clear()

    # 创建格式器
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台处理器 - 显示指定级别及以上
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器 - 记录指定级别及以上到文件
    try:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # 主日志文件
        log_file = log_path / f"{logger_name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

        # 错误日志文件
        error_file = log_path / f"{logger_name}_error_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_file, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)

    except (OSError, PermissionError) as e:
        logger.warning(f"无法创建日志文件，将仅使用控制台输出: {e}")
    except Exception as e:
        raise LoggingConfigError(f"日志配置失败: {e}") from e

    return logger