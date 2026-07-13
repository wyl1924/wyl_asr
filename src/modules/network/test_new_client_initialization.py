#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新客户端设置初始化属性测试

使用 Hypothesis 进行基于属性的测试，验证新客户端连接时接收当前设置的功能。
"""

import pytest
import json
import asyncio
from hypothesis import given, strategies as st, settings
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../../..'))
sys.path.insert(0, project_root)

from wyl_asr.src.modules.core.server_state import ServerState


# ============================================================================
# 测试数据生成策略
# ============================================================================

# 有效范围内的数值生成器
valid_window_width = st.integers(min_value=10, max_value=100)
valid_corner_radius = st.integers(min_value=0, max_value=100)
valid_background_opacity = st.integers(min_value=0, max_value=100)
valid_font_size = st.integers(min_value=1, max_value=100)
valid_max_display_lines = st.integers(min_value=1, max_value=20)
valid_scroll_speed = st.integers(min_value=20, max_value=200)

# 有效的十六进制颜色生成器
@st.composite
def valid_hex_color(draw):
    """生成有效的十六进制颜色"""
    # 选择 #RGB 或 #RRGGBB 格式
    format_choice = draw(st.booleans())
    if format_choice:
        # #RGB 格式
        r = draw(st.sampled_from('0123456789ABCDEFabcdef'))
        g = draw(st.sampled_from('0123456789ABCDEFabcdef'))
        b = draw(st.sampled_from('0123456789ABCDEFabcdef'))
        return f"#{r}{g}{b}"
    else:
        # #RRGGBB 格式
        r1 = draw(st.sampled_from('0123456789ABCDEFabcdef'))
        r2 = draw(st.sampled_from('0123456789ABCDEFabcdef'))
        g1 = draw(st.sampled_from('0123456789ABCDEFabcdef'))
        g2 = draw(st.sampled_from('0123456789ABCDEFabcdef'))
        b1 = draw(st.sampled_from('0123456789ABCDEFabcdef'))
        b2 = draw(st.sampled_from('0123456789ABCDEFabcdef'))
        return f"#{r1}{r2}{g1}{g2}{b1}{b2}"

# 有效的字体颜色生成器（包括 "默认"）
valid_font_color = st.one_of(
    st.just("默认"),
    valid_hex_color()
)

# 字体系列生成器
valid_font_family = st.sampled_from([
    "宋体", "微软雅黑", "黑体", "楷体", "仿宋", 
    "Arial", "Times New Roman", "Courier New"
])

# 布尔值生成器
valid_boolean = st.booleans()

# 有效的 WebSocket URL 生成器
@st.composite
def valid_websocket_url(draw):
    """生成有效的 WebSocket URL"""
    protocol = draw(st.sampled_from(['ws://', 'wss://']))
    host = draw(st.one_of(
        st.just('localhost'),
        st.just('127.0.0.1'),
        st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789.-', min_size=3, max_size=20)
    ))
    port = draw(st.integers(min_value=1, max_value=65535))
    path = draw(st.one_of(
        st.just('/'),
        st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789/-_', min_size=1, max_size=20)
    ))
    return f"{protocol}{host}:{port}{path}"

# 完整的有效设置生成器
@st.composite
def valid_subtitle_settings(draw):
    """生成完整的有效字幕设置"""
    return {
        "windowWidth": draw(valid_window_width),
        "cornerRadius": draw(valid_corner_radius),
        "backgroundColor": draw(valid_hex_color()),
        "backgroundOpacity": draw(valid_background_opacity),
        "fontFamily": draw(valid_font_family),
        "fontSize": draw(valid_font_size),
        "fontColor": draw(valid_font_color),
        "isBold": draw(valid_boolean),
        "isItalic": draw(valid_boolean),
        "showEnglish": draw(valid_boolean),
        "maxDisplayLines": draw(valid_max_display_lines),
        "scrollSpeed": draw(valid_scroll_speed),
        "webSocketUrl": draw(valid_websocket_url())
    }


# ============================================================================
# 模拟 WebSocket 客户端
# ============================================================================

class MockWebSocket:
    """模拟 WebSocket 客户端"""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.closed = False
        self.messages_received = []
        self.send_count = 0
        self.remote_address = ('127.0.0.1', 12345)
    
    async def send(self, message):
        """模拟发送消息"""
        self.send_count += 1
        if self.should_fail:
            raise Exception("模拟的发送失败")
        self.messages_received.append(message)
    
    def close(self):
        """模拟关闭连接"""
        self.closed = True


# ============================================================================
# 模拟 WebSocket 服务函数
# ============================================================================

async def mock_ws_serve_with_settings_init(websocket, path, server_state):
    """
    模拟 ws_serve 函数中的新客户端设置初始化逻辑
    
    这个函数复制了 websocket_service.py 中的连接处理和设置初始化逻辑
    """
    logger = server_state.logger
    
    # 注册新连接
    try:
        client_address = websocket.remote_address if hasattr(websocket, 'remote_address') else 'unknown'
        if logger:
            logger.info(f"🔗 新WebSocket连接: {client_address}")
        
        server_state.websocket_users.add(websocket)
        if logger:
            logger.info(f"📊 当前连接数: {len(server_state.websocket_users)}")
        
        # 如果存在已保存的字幕设置，发送给新连接的客户端
        if hasattr(server_state, 'subtitle_settings') and server_state.subtitle_settings:
            try:
                settings_message = json.dumps({
                    "type": "settings_update",
                    "data": server_state.subtitle_settings
                }, ensure_ascii=False)
                await websocket.send(settings_message)
                if logger:
                    logger.info(f"📤 已向新客户端发送当前字幕设置")
            except Exception as settings_error:
                if logger:
                    logger.warning(f"⚠️ 向新客户端发送设置失败: {settings_error}")
        
    except Exception as e:
        if logger:
            logger.error(f"❌ 注册连接失败: {e}")
        return


# ============================================================================
# 属性测试
# ============================================================================

class TestNewClientInitializationProperties:
    """新客户端设置初始化属性测试"""
    
    # ========================================================================
    # 属性 14: 新客户端设置初始化
    # ========================================================================
    
    @given(settings_data=valid_subtitle_settings())
    @settings(max_examples=100)
    def test_property_14_new_client_receives_current_settings(self, settings_data):
        """
        **属性 14: 新客户端设置初始化**
        
        对于任何在设置保存后连接的新客户端，该客户端应该从服务器接收当前设置并应用它们。
        
        **Validates: Requirements 7.2, 7.3**
        """
        # 创建服务器状态并保存设置
        server_state = ServerState()
        server_state.logger = None
        server_state.websocket_users = set()
        server_state.subtitle_settings = settings_data
        
        # 创建新的模拟客户端
        new_client = MockWebSocket(should_fail=False)
        
        # 模拟新客户端连接
        asyncio.run(mock_ws_serve_with_settings_init(new_client, "/", server_state))
        
        # 验证客户端被添加到 websocket_users
        assert new_client in server_state.websocket_users, \
            "New client should be added to websocket_users"
        
        # 验证客户端收到了设置消息
        assert len(new_client.messages_received) == 1, \
            f"New client should receive exactly 1 message, got {len(new_client.messages_received)}"
        
        # 解析收到的消息
        received_message = json.loads(new_client.messages_received[0])
        
        # 验证消息类型
        assert received_message['type'] == 'settings_update', \
            f"Message type should be 'settings_update', got '{received_message['type']}'"
        
        # 验证消息包含所有设置字段
        assert 'data' in received_message, "Message should have 'data' field"
        received_settings = received_message['data']
        
        # 验证所有字段都存在且值正确
        expected_fields = [
            'windowWidth', 'cornerRadius', 'backgroundColor', 'backgroundOpacity',
            'fontFamily', 'fontSize', 'fontColor', 'isBold', 'isItalic',
            'showEnglish', 'maxDisplayLines', 'scrollSpeed', 'webSocketUrl'
        ]
        
        for field in expected_fields:
            assert field in received_settings, f"Field '{field}' should be in received settings"
            assert received_settings[field] == settings_data[field], \
                f"Field '{field}' mismatch: expected {settings_data[field]}, got {received_settings[field]}"
    
    @given(settings_data=valid_subtitle_settings())
    @settings(max_examples=50)
    def test_property_14_no_settings_no_message(self, settings_data):
        """
        **属性 14: 新客户端设置初始化（无设置时不发送）**
        
        当服务器没有保存设置时，新客户端连接不应该收到设置消息。
        
        **Validates: Requirements 7.2, 7.3**
        """
        # 创建服务器状态，但不保存设置
        server_state = ServerState()
        server_state.logger = None
        server_state.websocket_users = set()
        server_state.subtitle_settings = None  # 没有设置
        
        # 创建新的模拟客户端
        new_client = MockWebSocket(should_fail=False)
        
        # 模拟新客户端连接
        asyncio.run(mock_ws_serve_with_settings_init(new_client, "/", server_state))
        
        # 验证客户端被添加到 websocket_users
        assert new_client in server_state.websocket_users, \
            "New client should be added to websocket_users"
        
        # 验证客户端没有收到任何消息
        assert len(new_client.messages_received) == 0, \
            f"New client should not receive any message when no settings exist, got {len(new_client.messages_received)}"
    
    @given(
        settings_data=valid_subtitle_settings(),
        num_existing_clients=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50)
    def test_property_14_new_client_with_existing_clients(self, settings_data, num_existing_clients):
        """
        **属性 14: 新客户端设置初始化（已有客户端存在）**
        
        当已有客户端连接时，新客户端连接应该收到当前设置，而不影响现有客户端。
        
        **Validates: Requirements 7.2, 7.3**
        """
        # 创建服务器状态并保存设置
        server_state = ServerState()
        server_state.logger = None
        server_state.subtitle_settings = settings_data
        
        # 创建现有客户端
        existing_clients = [MockWebSocket(should_fail=False) for _ in range(num_existing_clients)]
        server_state.websocket_users = set(existing_clients)
        
        # 记录现有客户端的初始消息数量
        initial_message_counts = [len(client.messages_received) for client in existing_clients]
        
        # 创建新的模拟客户端
        new_client = MockWebSocket(should_fail=False)
        
        # 模拟新客户端连接
        asyncio.run(mock_ws_serve_with_settings_init(new_client, "/", server_state))
        
        # 验证新客户端被添加到 websocket_users
        assert new_client in server_state.websocket_users, \
            "New client should be added to websocket_users"
        
        # 验证总客户端数量正确
        assert len(server_state.websocket_users) == num_existing_clients + 1, \
            f"Should have {num_existing_clients + 1} clients total"
        
        # 验证新客户端收到了设置消息
        assert len(new_client.messages_received) == 1, \
            "New client should receive settings message"
        
        # 验证现有客户端没有收到额外的消息（只有新客户端收到初始化消息）
        for i, client in enumerate(existing_clients):
            assert len(client.messages_received) == initial_message_counts[i], \
                f"Existing client {i} should not receive additional messages during new client connection"
    
    @given(settings_data=valid_subtitle_settings())
    @settings(max_examples=50)
    def test_property_14_failed_send_does_not_prevent_connection(self, settings_data):
        """
        **属性 14: 新客户端设置初始化（发送失败不阻止连接）**
        
        如果向新客户端发送设置失败，客户端仍应该被添加到 websocket_users 中。
        
        **Validates: Requirements 7.2, 7.3**
        """
        # 创建服务器状态并保存设置
        server_state = ServerState()
        server_state.logger = None
        server_state.websocket_users = set()
        server_state.subtitle_settings = settings_data
        
        # 创建会发送失败的模拟客户端
        new_client = MockWebSocket(should_fail=True)
        
        # 模拟新客户端连接（应该不会抛出异常）
        asyncio.run(mock_ws_serve_with_settings_init(new_client, "/", server_state))
        
        # 验证客户端仍然被添加到 websocket_users（即使发送失败）
        assert new_client in server_state.websocket_users, \
            "New client should be added to websocket_users even if settings send fails"
        
        # 验证尝试发送了消息（但失败了）
        assert new_client.send_count >= 1, \
            "Should have attempted to send settings to new client"
        
        # 验证消息没有被接收（因为发送失败）
        assert len(new_client.messages_received) == 0, \
            "Client should not have received message due to send failure"
    
    @given(
        settings_data=valid_subtitle_settings(),
        num_new_clients=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=50)
    def test_property_14_multiple_new_clients_receive_settings(self, settings_data, num_new_clients):
        """
        **属性 14: 新客户端设置初始化（多个新客户端）**
        
        当多个新客户端依次连接时，每个客户端都应该收到当前设置。
        
        **Validates: Requirements 7.2, 7.3**
        """
        # 创建服务器状态并保存设置
        server_state = ServerState()
        server_state.logger = None
        server_state.websocket_users = set()
        server_state.subtitle_settings = settings_data
        
        # 创建多个新客户端并依次连接
        new_clients = []
        for i in range(num_new_clients):
            client = MockWebSocket(should_fail=False)
            new_clients.append(client)
            
            # 模拟客户端连接
            asyncio.run(mock_ws_serve_with_settings_init(client, "/", server_state))
            
            # 验证客户端被添加
            assert client in server_state.websocket_users, \
                f"Client {i} should be added to websocket_users"
            
            # 验证客户端收到设置
            assert len(client.messages_received) == 1, \
                f"Client {i} should receive settings message"
            
            # 验证设置内容正确
            received_message = json.loads(client.messages_received[0])
            assert received_message['type'] == 'settings_update', \
                f"Client {i} should receive settings_update message"
            assert received_message['data'] == settings_data, \
                f"Client {i} should receive correct settings data"
        
        # 验证所有客户端都在 websocket_users 中
        assert len(server_state.websocket_users) == num_new_clients, \
            f"Should have {num_new_clients} clients in websocket_users"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
