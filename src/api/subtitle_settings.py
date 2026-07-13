#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕设置API模块
==============

提供字幕显示设置的RESTful API接口。
"""

import logging
from typing import Dict, Any
from flask import Blueprint, request, jsonify, Response
from datetime import datetime

from ..models.subtitle_settings import SubtitleSettingsModel
from ..modules.core.server_state import ServerState
from pydantic import ValidationError

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
subtitle_settings_bp = Blueprint('subtitle_settings', __name__)


def create_response(data: Any = None, message: str = "success", 
                   status_code: int = 200) -> tuple:
    """创建统一的API响应格式
    
    Args:
        data: 响应数据
        message: 响应消息
        status_code: HTTP状态码
        
    Returns:
        (响应JSON, 状态码) 元组
    """
    response_data = {
        "success": status_code < 400,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    return jsonify(response_data), status_code


# 全局server_state引用（将在应用初始化时设置）
_server_state: ServerState = None


def init_subtitle_settings_api(server_state: ServerState):
    """初始化字幕设置API
    
    Args:
        server_state: 服务器状态对象
    """
    global _server_state
    _server_state = server_state
    logger.info("✅ 字幕设置API已初始化")


@subtitle_settings_bp.route('/api/subtitle-settings', methods=['POST'])
def save_subtitle_settings():
    """保存字幕显示设置并广播到所有客户端
    
    请求体:
        JSON格式的SubtitleSettingsModel
        
    返回:
        成功: {"success": True, "message": "...", "data": {...}}
        失败: {"success": False, "message": "...", "errors": [...]}
    """
    try:
        # 获取请求数据
        try:
            data = request.get_json()
        except Exception as e:
            return create_response(
                None, 
                "请求数据不能为空或格式无效", 
                400
            )
        
        if not data:
            return create_response(
                None, 
                "请求数据不能为空", 
                400
            )
        
        # 验证设置模型
        try:
            settings = SubtitleSettingsModel(**data)
        except ValidationError as e:
            # 提取所有验证错误
            errors = []
            for error in e.errors():
                field = error['loc'][0] if error['loc'] else 'unknown'
                msg = error['msg']
                errors.append(f"{field}: {msg}")
            
            logger.warning(f"设置验证失败: {errors}")
            return create_response(
                {"errors": errors},
                "设置验证失败",
                400
            )
        
        # 检查server_state是否可用
        if _server_state is None:
            logger.error("server_state未初始化")
            return create_response(
                None,
                "服务器状态未初始化",
                500
            )
        
        # 将设置存储到server_state
        settings_dict = settings.model_dump()
        _server_state.subtitle_settings = settings_dict
        
        logger.info(f"✅ 字幕设置已保存: {settings_dict}")
        
        # 获取当前连接数
        client_count = len(_server_state.websocket_users) if hasattr(_server_state, 'websocket_users') else 0
        
        # 广播设置到所有连接的客户端
        import asyncio
        from ..modules.network.websocket_manager import broadcast_settings_update
        
        # 在新的事件循环中执行广播（因为Flask是同步的）
        broadcast_success = True
        broadcast_error = None
        
        try:
            # 尝试获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果循环正在运行，创建任务
                asyncio.create_task(
                    broadcast_settings_update(settings_dict, _server_state)
                )
            else:
                # 如果循环未运行，直接运行
                loop.run_until_complete(
                    broadcast_settings_update(settings_dict, _server_state)
                )
            logger.info(f"📡 设置已广播到 {client_count} 个客户端")
        except RuntimeError:
            # 如果没有事件循环，创建新的
            try:
                asyncio.run(
                    broadcast_settings_update(settings_dict, _server_state)
                )
                logger.info(f"📡 设置已广播到 {client_count} 个客户端")
            except Exception as e:
                # 广播失败不应阻止设置保存
                broadcast_success = False
                broadcast_error = str(e)
                logger.error(f"⚠️ 广播设置失败，但设置已保存: {e}")
        except Exception as e:
            # 广播失败不应阻止设置保存
            broadcast_success = False
            broadcast_error = str(e)
            logger.error(f"⚠️ 广播设置失败，但设置已保存: {e}")
        
        # 构造响应消息
        if broadcast_success:
            message = f"设置已保存并广播到 {client_count} 个客户端"
        else:
            message = f"设置已保存，但广播失败: {broadcast_error}"
        
        return create_response(
            settings_dict,
            message,
            200
        )
        
    except Exception as e:
        logger.error(f"保存字幕设置失败: {e}", exc_info=True)
        return create_response(
            None,
            f"保存设置失败: {str(e)}",
            500
        )


@subtitle_settings_bp.route('/api/subtitle-settings', methods=['GET'])
def get_subtitle_settings():
    """获取当前字幕显示设置
    
    返回:
        成功: {"success": True, "message": "...", "data": {...}}
        如果没有设置，返回默认值
    """
    try:
        # 检查server_state是否可用
        if _server_state is None:
            logger.error("server_state未初始化")
            return create_response(
                None,
                "服务器状态未初始化",
                500
            )
        
        # 获取存储的设置或使用默认值
        if _server_state.subtitle_settings is not None:
            settings_dict = _server_state.subtitle_settings
            logger.info("✅ 返回已保存的字幕设置")
        else:
            # 返回默认设置
            default_settings = SubtitleSettingsModel()
            settings_dict = default_settings.model_dump()
            logger.info("✅ 返回默认字幕设置")
        
        return create_response(
            settings_dict,
            "获取设置成功",
            200
        )
        
    except Exception as e:
        logger.error(f"获取字幕设置失败: {e}", exc_info=True)
        return create_response(
            None,
            f"获取设置失败: {str(e)}",
            500
        )
