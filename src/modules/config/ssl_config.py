#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSL配置模块
===========

提供SSL/TLS安全连接的配置功能，支持HTTPS和WSS协议。
"""

import ssl
import os
import logging
import argparse
from typing import Optional


def setup_ssl_context(args: argparse.Namespace, logger: logging.Logger) -> Optional[ssl.SSLContext]:
    """
    配置SSL上下文，用于HTTPS/WSS连接
    
    Args:
        args: 命令行参数，包含证书文件路径
        logger: 日志记录器
        
    Returns:
        ssl.SSLContext or None: 配置好的SSL上下文，如果不使用SSL则返回None
    """
    if not args.certfile or not args.keyfile:
        logger.info("🔓 未配置SSL证书，将使用非加密连接 (WS)")
        return None
    
    try:
        logger.info("🔐 正在配置SSL上下文...")
        
        # 检查证书文件是否存在
        if not os.path.exists(args.certfile):
            logger.error(f"❌ SSL证书文件不存在: {args.certfile}")
            return None
            
        if not os.path.exists(args.keyfile):
            logger.error(f"❌ SSL私钥文件不存在: {args.keyfile}")
            return None
        
        # 创建SSL上下文
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(args.certfile, keyfile=args.keyfile)
        
        logger.info(f"✅ SSL配置成功，证书: {args.certfile}")
        logger.info("🔒 服务器将使用加密连接 (WSS)")
        
        return ssl_context
        
    except Exception as e:
        logger.error(f"❌ SSL配置失败: {e}")
        logger.error("将回退到非加密连接")
        return None