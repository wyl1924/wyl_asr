#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket连接管理模块
==================

负责WebSocket连接的管理、重置和清理操作。
"""

import json
import logging
from ..core.server_state import ServerState
from ..config.arg_parser import reset_vad_config


async def ws_reset(websocket, server_state: ServerState = None) -> None:
    """重置WebSocket连接状态并关闭连接"""
    try:
        # 安全地清理状态字典，避免属性不存在的错误
        if hasattr(websocket, 'status_dict_asr_online'):
            websocket.status_dict_asr_online["cache"] = {}
            websocket.status_dict_asr_online["is_final"] = True
        
        if hasattr(websocket, 'status_dict_vad'):
            # 重置VAD状态时从配置文件读取参数
            if server_state and hasattr(server_state, 'args'):
                websocket.status_dict_vad = reset_vad_config(server_state.args)
            else:
                # 如果没有server_state，保持原有逻辑作为后备
                websocket.status_dict_vad["cache"] = {}
                websocket.status_dict_vad["is_final"] = True
        
        if hasattr(websocket, 'status_dict_punc'):
            websocket.status_dict_punc["cache"] = {}
        
        # 清理其他可能的状态
        if hasattr(websocket, 'status_dict_asr'):
            websocket.status_dict_asr.clear()
        
        # 重置连接相关状态
        if hasattr(websocket, 'is_speaking'):
            websocket.is_speaking = False
        
        if hasattr(websocket, 'vad_pre_idx'):
            websocket.vad_pre_idx = 0
    
    except Exception as e:
        print(f"Warning: Error during websocket state reset: {e}")
    
    try:
        # 安全地关闭连接
        if not websocket.closed:
            await websocket.close()
    except Exception as e:
        print(f"Warning: Error closing websocket: {e}")


async def clear_websocket(websocket, server_state: ServerState) -> None:
    """清理WebSocket连接并从服务器状态中移除"""
    try:
        # 记录连接清理
        if hasattr(server_state, 'logger') and server_state.logger:
            server_state.logger.info(f"🧹 清理WebSocket连接: {websocket.remote_address if hasattr(websocket, 'remote_address') else 'unknown'}")
        else:
            print(f"🧹 清理WebSocket连接")
        
        # 重置连接状态
        await ws_reset(websocket, server_state)
        
        # 从服务器状态中安全移除连接
        if hasattr(server_state, 'websocket_users') and websocket in server_state.websocket_users:
            server_state.websocket_users.discard(websocket)
            if hasattr(server_state, 'logger') and server_state.logger:
                server_state.logger.info(f"✅ 连接已从用户列表中移除，当前连接数: {len(server_state.websocket_users)}")
            else:
                print(f"✅ 连接已移除，当前连接数: {len(server_state.websocket_users)}")
        
    except Exception as e:
        error_msg = f"❌ 清理WebSocket连接时发生错误: {e}"
        if hasattr(server_state, 'logger') and server_state.logger:
            server_state.logger.error(error_msg)
        else:
            print(error_msg)


async def broadcast_message(message: str, server_state: ServerState, exclude_websocket=None) -> None:
    """广播消息给所有连接的WebSocket客户端
    
    Args:
        message: 要广播的消息（JSON字符串）
        server_state: 服务器状态对象
        exclude_websocket: 可选，要排除的WebSocket连接（通常是发送音频的客户端）
    """
    logger = server_state.logger if hasattr(server_state, 'logger') else None
    
    if not hasattr(server_state, 'websocket_users'):
        if logger:
            logger.warning("⚠️ server_state 没有 websocket_users 属性")
        return
    
    # 获取所有活跃的连接
    active_connections = list(server_state.websocket_users)
    
    if not active_connections:
        if logger:
            logger.debug("📭 没有活跃的WebSocket连接，跳过广播")
        return
    
    # 广播给所有连接（可选排除某个连接）
    broadcast_count = 0
    failed_connections = []
    
    for ws in active_connections:
        # 跳过要排除的连接
        if exclude_websocket and ws == exclude_websocket:
            continue
            
        try:
            # 检查连接是否仍然打开
            if not ws.closed:
                await ws.send(message)
                broadcast_count += 1
            else:
                failed_connections.append(ws)
        except Exception as e:
            if logger:
                logger.warning(f"⚠️ 向客户端广播消息失败: {e}")
            failed_connections.append(ws)
    
    # 清理失败的连接
    for ws in failed_connections:
        try:
            server_state.websocket_users.discard(ws)
        except:
            pass
    
    if logger and broadcast_count > 0:
        logger.debug(f"📡 消息已广播给 {broadcast_count} 个客户端")


async def broadcast_settings_update(settings: dict, server_state: ServerState) -> None:
    """广播字幕设置更新给所有连接的客户端
    
    将字幕显示设置格式化为 JSON 消息并广播给所有连接的 WebSocket 客户端。
    消息格式为 {"type": "settings_update", "data": settings}
    
    Args:
        settings: 要广播的设置字典，包含所有字幕显示配置参数
        server_state: 服务器状态对象，包含 websocket_users 集合
        
    Example:
        settings = {
            "windowWidth": 80,
            "cornerRadius": 10,
            "backgroundColor": "#000000",
            "backgroundOpacity": 75,
            ...
        }
        await broadcast_settings_update(settings, server_state)
    """
    logger = server_state.logger if hasattr(server_state, 'logger') else None
    
    try:
        # 格式化设置为 JSON 消息，类型为 "settings_update"
        message = json.dumps({
            "type": "settings_update",
            "data": settings
        }, ensure_ascii=False)
        
        if logger:
            logger.info(f"📤 广播字幕设置更新给所有客户端")
        
        # 使用现有的 broadcast_message() 函数广播给所有客户端
        # exclude_websocket=None 表示不排除任何客户端
        await broadcast_message(message, server_state, exclude_websocket=None)
        
        if logger:
            logger.info(f"✅ 字幕设置更新广播完成")
            
    except Exception as e:
        error_msg = f"❌ 广播字幕设置更新时发生错误: {e}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
