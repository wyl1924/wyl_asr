#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕设置广播功能属性测试

使用 Hypothesis 进行基于属性的测试，验证广播功能的通用属性。
"""

import pytest
import json
import asyncio
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../../..'))
sys.path.insert(0, project_root)

from wyl_asr.src.modules.network.websocket_manager import broadcast_settings_update, broadcast_message
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
# 属性测试
# ============================================================================

class TestBroadcastSettingsProperties:
    """字幕设置广播功能属性测试"""
    
    # ========================================================================
    # 属性 6: 广播消息结构
    # ========================================================================
    
    @given(settings_data=valid_subtitle_settings())
    @settings(max_examples=100)
    def test_property_6_broadcast_message_structure(self, settings_data):
        """
        **属性 6: 广播消息结构**
        
        对于任何有效的设置对象通过 WebSocket 广播，消息应该具有类型 "settings_update"，
        并且 data 字段应该包含所有设置属性及其正确的值。
        
        **Validates: Requirements 3.2**
        """
        # 创建服务器状态
        server_state = ServerState()
        server_state.websocket_users = set()
        server_state.logger = None
        
        # 使用 patch 模拟 broadcast_message
        with patch('wyl_asr.src.modules.network.websocket_manager.broadcast_message', new_callable=AsyncMock) as mock_broadcast:
            # 调用广播函数
            asyncio.run(broadcast_settings_update(settings_data, server_state))
            
            # 验证 broadcast_message 被调用
            assert mock_broadcast.called, "broadcast_message should be called"
            
            # 获取调用参数
            call_args = mock_broadcast.call_args
            message_str = call_args[0][0]  # 第一个位置参数是消息字符串
            
            # 解析消息 JSON
            message = json.loads(message_str)
            
            # 验证消息结构：必须有 type 字段
            assert 'type' in message, "Message must have 'type' field"
            assert message['type'] == 'settings_update', \
                f"Message type should be 'settings_update', got '{message['type']}'"
            
            # 验证消息结构：必须有 data 字段
            assert 'data' in message, "Message must have 'data' field"
            
            # 验证 data 字段包含所有设置属性
            data = message['data']
            expected_fields = [
                'windowWidth', 'cornerRadius', 'backgroundColor', 'backgroundOpacity',
                'fontFamily', 'fontSize', 'fontColor', 'isBold', 'isItalic',
                'showEnglish', 'maxDisplayLines', 'scrollSpeed', 'webSocketUrl'
            ]
            
            for field in expected_fields:
                assert field in data, f"Field '{field}' should be in message data"
            
            # 验证所有字段的值与原始设置匹配
            assert data['windowWidth'] == settings_data['windowWidth'], \
                f"windowWidth mismatch: expected {settings_data['windowWidth']}, got {data['windowWidth']}"
            assert data['cornerRadius'] == settings_data['cornerRadius'], \
                f"cornerRadius mismatch"
            assert data['backgroundColor'] == settings_data['backgroundColor'], \
                f"backgroundColor mismatch"
            assert data['backgroundOpacity'] == settings_data['backgroundOpacity'], \
                f"backgroundOpacity mismatch"
            assert data['fontFamily'] == settings_data['fontFamily'], \
                f"fontFamily mismatch"
            assert data['fontSize'] == settings_data['fontSize'], \
                f"fontSize mismatch"
            assert data['fontColor'] == settings_data['fontColor'], \
                f"fontColor mismatch"
            assert data['isBold'] == settings_data['isBold'], \
                f"isBold mismatch"
            assert data['isItalic'] == settings_data['isItalic'], \
                f"isItalic mismatch"
            assert data['showEnglish'] == settings_data['showEnglish'], \
                f"showEnglish mismatch"
            assert data['maxDisplayLines'] == settings_data['maxDisplayLines'], \
                f"maxDisplayLines mismatch"
            assert data['scrollSpeed'] == settings_data['scrollSpeed'], \
                f"scrollSpeed mismatch"
            assert data['webSocketUrl'] == settings_data['webSocketUrl'], \
                f"webSocketUrl mismatch"
    
    # ========================================================================
    # 属性 7: 广播到所有连接的客户端
    # ========================================================================
    
    @given(
        settings_data=valid_subtitle_settings(),
        num_clients=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100)
    def test_property_7_broadcast_to_all_connected_clients(self, settings_data, num_clients):
        """
        **属性 7: 广播到所有连接的客户端**
        
        对于任何设置广播，websocket_users 集合中的所有客户端都应该接收到广播消息
        （排除传输过程中失败的客户端）。
        
        **Validates: Requirements 3.1, 3.4, 7.1, 7.4**
        """
        # 创建服务器状态
        server_state = ServerState()
        server_state.logger = None
        
        # 创建多个模拟客户端（都不会失败）
        mock_clients = [MockWebSocket(should_fail=False) for _ in range(num_clients)]
        server_state.websocket_users = set(mock_clients)
        
        # 格式化消息
        message = json.dumps({
            "type": "settings_update",
            "data": settings_data
        })
        
        # 调用广播函数
        asyncio.run(broadcast_message(message, server_state, exclude_websocket=None))
        
        # 验证所有客户端都收到了消息
        for i, client in enumerate(mock_clients):
            assert len(client.messages_received) == 1, \
                f"Client {i} should receive exactly 1 message, got {len(client.messages_received)}"
            assert client.messages_received[0] == message, \
                f"Client {i} received incorrect message"
        
        # 验证所有客户端仍在 websocket_users 中（没有被移除）
        assert len(server_state.websocket_users) == num_clients, \
            f"All {num_clients} clients should remain in websocket_users"
    
    @given(
        settings_data=valid_subtitle_settings(),
        num_clients=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=50)
    def test_property_7_broadcast_excludes_no_clients(self, settings_data, num_clients):
        """
        **属性 7: 广播到所有连接的客户端（无排除）**
        
        对于设置广播，不应该排除任何客户端（exclude_websocket=None）。
        
        **Validates: Requirements 3.4**
        """
        # 创建服务器状态
        server_state = ServerState()
        server_state.logger = None
        
        # 创建多个模拟客户端
        mock_clients = [MockWebSocket(should_fail=False) for _ in range(num_clients)]
        server_state.websocket_users = set(mock_clients)
        
        # 使用 patch 验证 broadcast_message 的调用参数
        with patch('wyl_asr.src.modules.network.websocket_manager.broadcast_message', new_callable=AsyncMock) as mock_broadcast:
            # 调用广播函数
            asyncio.run(broadcast_settings_update(settings_data, server_state))
            
            # 验证 broadcast_message 被调用
            assert mock_broadcast.called, "broadcast_message should be called"
            
            # 获取调用参数
            call_args = mock_broadcast.call_args
            
            # 验证 exclude_websocket 参数为 None
            assert call_args[1]['exclude_websocket'] is None, \
                "exclude_websocket should be None for settings broadcasts"
    
    # ========================================================================
    # 属性 8: 失败客户端移除
    # ========================================================================
    
    @given(
        settings_data=valid_subtitle_settings(),
        num_successful=st.integers(min_value=1, max_value=5),
        num_failed=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=100)
    def test_property_8_failed_client_removal(self, settings_data, num_successful, num_failed):
        """
        **属性 8: 失败客户端移除**
        
        对于任何广播，其中一个或多个客户端无法接收消息，这些失败的客户端应该从
        websocket_users 中移除，并且广播应该继续到所有剩余的客户端。
        
        **Validates: Requirements 3.5, 7.5**
        """
        # 创建服务器状态
        server_state = ServerState()
        server_state.logger = None
        
        # 创建成功的客户端和失败的客户端
        successful_clients = [MockWebSocket(should_fail=False) for _ in range(num_successful)]
        failed_clients = [MockWebSocket(should_fail=True) for _ in range(num_failed)]
        
        # 将所有客户端添加到 websocket_users
        all_clients = successful_clients + failed_clients
        server_state.websocket_users = set(all_clients)
        
        initial_count = len(server_state.websocket_users)
        assert initial_count == num_successful + num_failed, \
            f"Initial client count should be {num_successful + num_failed}"
        
        # 格式化消息
        message = json.dumps({
            "type": "settings_update",
            "data": settings_data
        })
        
        # 调用广播函数
        asyncio.run(broadcast_message(message, server_state, exclude_websocket=None))
        
        # 验证成功的客户端收到了消息
        for i, client in enumerate(successful_clients):
            assert len(client.messages_received) == 1, \
                f"Successful client {i} should receive exactly 1 message"
            assert client.messages_received[0] == message, \
                f"Successful client {i} received incorrect message"
        
        # 验证失败的客户端没有收到消息（因为发送失败）
        for i, client in enumerate(failed_clients):
            # 客户端尝试发送但失败了
            assert client.send_count >= 1, \
                f"Failed client {i} should have attempted to send"
            # 由于失败，消息不应该被添加到 messages_received
            assert len(client.messages_received) == 0, \
                f"Failed client {i} should not have received message"
        
        # 验证失败的客户端已从 websocket_users 中移除
        assert len(server_state.websocket_users) == num_successful, \
            f"Only {num_successful} successful clients should remain, but got {len(server_state.websocket_users)}"
        
        # 验证成功的客户端仍在 websocket_users 中
        for client in successful_clients:
            assert client in server_state.websocket_users, \
                "Successful clients should remain in websocket_users"
        
        # 验证失败的客户端不在 websocket_users 中
        for client in failed_clients:
            assert client not in server_state.websocket_users, \
                "Failed clients should be removed from websocket_users"
    
    @given(
        settings_data=valid_subtitle_settings(),
        num_clients=st.integers(min_value=3, max_value=10)
    )
    @settings(max_examples=50)
    def test_property_8_partial_failure_continues_broadcast(self, settings_data, num_clients):
        """
        **属性 8: 失败客户端移除（部分失败继续广播）**
        
        当部分客户端失败时，广播应该继续到所有剩余的客户端，而不是完全失败。
        
        **Validates: Requirements 3.5, 7.5**
        """
        # 创建服务器状态
        server_state = ServerState()
        server_state.logger = None
        
        # 创建客户端：第一个失败，其余成功
        clients = [MockWebSocket(should_fail=(i == 0)) for i in range(num_clients)]
        server_state.websocket_users = set(clients)
        
        # 格式化消息
        message = json.dumps({
            "type": "settings_update",
            "data": settings_data
        })
        
        # 调用广播函数
        asyncio.run(broadcast_message(message, server_state, exclude_websocket=None))
        
        # 验证第一个客户端（失败的）被移除
        assert clients[0] not in server_state.websocket_users, \
            "Failed client should be removed"
        
        # 验证其余客户端（成功的）仍在集合中并收到消息
        for i in range(1, num_clients):
            assert clients[i] in server_state.websocket_users, \
                f"Successful client {i} should remain in websocket_users"
            assert len(clients[i].messages_received) == 1, \
                f"Successful client {i} should receive message"
        
        # 验证最终客户端数量正确
        assert len(server_state.websocket_users) == num_clients - 1, \
            f"Should have {num_clients - 1} clients remaining"
    
    @given(settings_data=valid_subtitle_settings())
    @settings(max_examples=50)
    def test_property_8_all_clients_fail(self, settings_data):
        """
        **属性 8: 失败客户端移除（所有客户端失败）**
        
        当所有客户端都失败时，所有客户端应该被移除，websocket_users 应该为空。
        
        **Validates: Requirements 3.5, 7.5**
        """
        # 创建服务器状态
        server_state = ServerState()
        server_state.logger = None
        
        # 创建多个失败的客户端
        num_clients = 5
        failed_clients = [MockWebSocket(should_fail=True) for _ in range(num_clients)]
        server_state.websocket_users = set(failed_clients)
        
        # 格式化消息
        message = json.dumps({
            "type": "settings_update",
            "data": settings_data
        })
        
        # 调用广播函数
        asyncio.run(broadcast_message(message, server_state, exclude_websocket=None))
        
        # 验证所有客户端都被移除
        assert len(server_state.websocket_users) == 0, \
            "All failed clients should be removed, websocket_users should be empty"
        
        # 验证所有客户端都不在集合中
        for client in failed_clients:
            assert client not in server_state.websocket_users, \
                "Failed client should not be in websocket_users"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
