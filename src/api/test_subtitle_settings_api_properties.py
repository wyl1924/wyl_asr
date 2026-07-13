#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕设置API属性测试

使用 Hypothesis 进行基于属性的测试，验证设置 API 的通用属性。
"""

import pytest
import json
from hypothesis import given, strategies as st, settings, HealthCheck
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
sys.path.insert(0, project_root)

from wyl_asr.src.modules.database.database_api import create_app
from wyl_asr.src.modules.core.server_state import ServerState
from wyl_asr.src.models.subtitle_settings import SubtitleSettingsModel


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
# 属性测试
# ============================================================================

@pytest.fixture(scope="module")
def test_app():
    """为整个测试模块创建一个测试应用"""
    # 创建 server_state
    server_state = ServerState()
    server_state.subtitle_settings = None
    server_state.websocket_users = set()
    
    # 创建测试应用
    app = create_app({'TESTING': True}, server_state=server_state)
    app.config['TESTING'] = True
    
    # 返回应用和服务器状态
    yield app, server_state


@pytest.fixture(scope="function")
def test_client(test_app):
    """为每个测试创建新的测试客户端"""
    app, server_state = test_app
    
    # 清理之前的设置
    server_state.subtitle_settings = None
    
    # 创建客户端
    client = app.test_client()
    
    # 返回客户端和服务器状态
    yield client, server_state
    
    # 清理
    server_state.subtitle_settings = None


class TestSubtitleSettingsAPIProperties:
    """字幕设置 API 属性测试"""
    
    # ========================================================================
    # 属性 5: 设置存储和检索
    # ========================================================================
    
    @given(settings_data=valid_subtitle_settings())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_5_settings_storage_and_retrieval(self, test_client, settings_data):
        """
        **属性 5: 设置存储和检索**
        
        对于任何有效的 Settings_Model 对象，在通过 POST 端点存储后，
        通过 GET 端点检索应该返回等效的设置对象。
        
        **Validates: Requirements 2.3, 2.5**
        """
        client, server_state = test_client
        
        # 首先验证设置是有效的（通过 Pydantic 模型）
        validated_settings = SubtitleSettingsModel(**settings_data)
        
        # 通过 POST 端点保存设置
        post_response = client.post(
            '/api/subtitle-settings',
            data=json.dumps(settings_data),
            content_type='application/json'
        )
        
        # 验证 POST 请求成功
        assert post_response.status_code == 200, \
            f"POST request failed with status {post_response.status_code}: {post_response.data}"
        
        post_data = json.loads(post_response.data)
        assert post_data['success'] is True, \
            f"POST request returned success=False: {post_data.get('message')}"
        
        # 通过 GET 端点检索设置
        get_response = client.get('/api/subtitle-settings')
        
        # 验证 GET 请求成功
        assert get_response.status_code == 200, \
            f"GET request failed with status {get_response.status_code}: {get_response.data}"
        
        get_data = json.loads(get_response.data)
        assert get_data['success'] is True, \
            f"GET request returned success=False: {get_data.get('message')}"
        
        # 验证检索到的设置与保存的设置等效
        retrieved_settings = get_data['data']
        
        # 比较所有字段
        assert retrieved_settings['windowWidth'] == settings_data['windowWidth'], \
            f"windowWidth mismatch: expected {settings_data['windowWidth']}, got {retrieved_settings['windowWidth']}"
        
        assert retrieved_settings['cornerRadius'] == settings_data['cornerRadius'], \
            f"cornerRadius mismatch: expected {settings_data['cornerRadius']}, got {retrieved_settings['cornerRadius']}"
        
        assert retrieved_settings['backgroundColor'] == settings_data['backgroundColor'], \
            f"backgroundColor mismatch: expected {settings_data['backgroundColor']}, got {retrieved_settings['backgroundColor']}"
        
        assert retrieved_settings['backgroundOpacity'] == settings_data['backgroundOpacity'], \
            f"backgroundOpacity mismatch: expected {settings_data['backgroundOpacity']}, got {retrieved_settings['backgroundOpacity']}"
        
        assert retrieved_settings['fontFamily'] == settings_data['fontFamily'], \
            f"fontFamily mismatch: expected {settings_data['fontFamily']}, got {retrieved_settings['fontFamily']}"
        
        assert retrieved_settings['fontSize'] == settings_data['fontSize'], \
            f"fontSize mismatch: expected {settings_data['fontSize']}, got {retrieved_settings['fontSize']}"
        
        assert retrieved_settings['fontColor'] == settings_data['fontColor'], \
            f"fontColor mismatch: expected {settings_data['fontColor']}, got {retrieved_settings['fontColor']}"
        
        assert retrieved_settings['isBold'] == settings_data['isBold'], \
            f"isBold mismatch: expected {settings_data['isBold']}, got {retrieved_settings['isBold']}"
        
        assert retrieved_settings['isItalic'] == settings_data['isItalic'], \
            f"isItalic mismatch: expected {settings_data['isItalic']}, got {retrieved_settings['isItalic']}"
        
        assert retrieved_settings['showEnglish'] == settings_data['showEnglish'], \
            f"showEnglish mismatch: expected {settings_data['showEnglish']}, got {retrieved_settings['showEnglish']}"
        
        assert retrieved_settings['maxDisplayLines'] == settings_data['maxDisplayLines'], \
            f"maxDisplayLines mismatch: expected {settings_data['maxDisplayLines']}, got {retrieved_settings['maxDisplayLines']}"
        
        assert retrieved_settings['scrollSpeed'] == settings_data['scrollSpeed'], \
            f"scrollSpeed mismatch: expected {settings_data['scrollSpeed']}, got {retrieved_settings['scrollSpeed']}"
        
        assert retrieved_settings['webSocketUrl'] == settings_data['webSocketUrl'], \
            f"webSocketUrl mismatch: expected {settings_data['webSocketUrl']}, got {retrieved_settings['webSocketUrl']}"
    
    @given(
        settings1=valid_subtitle_settings(),
        settings2=valid_subtitle_settings()
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_5_settings_overwrite(self, test_client, settings1, settings2):
        """
        **属性 5: 设置存储和检索（覆盖测试）**
        
        对于任何两个不同的有效设置对象，先保存第一个，再保存第二个，
        然后检索应该返回第二个设置对象（验证覆盖行为）。
        
        **Validates: Requirements 2.3, 2.5**
        """
        client, server_state = test_client
        
        # 保存第一个设置
        post_response1 = client.post(
            '/api/subtitle-settings',
            data=json.dumps(settings1),
            content_type='application/json'
        )
        assert post_response1.status_code == 200
        
        # 保存第二个设置（应该覆盖第一个）
        post_response2 = client.post(
            '/api/subtitle-settings',
            data=json.dumps(settings2),
            content_type='application/json'
        )
        assert post_response2.status_code == 200
        
        # 检索设置
        get_response = client.get('/api/subtitle-settings')
        assert get_response.status_code == 200
        
        get_data = json.loads(get_response.data)
        retrieved_settings = get_data['data']
        
        # 验证检索到的是第二个设置，而不是第一个
        assert retrieved_settings['windowWidth'] == settings2['windowWidth']
        assert retrieved_settings['fontSize'] == settings2['fontSize']
        assert retrieved_settings['backgroundColor'] == settings2['backgroundColor']
        assert retrieved_settings['fontFamily'] == settings2['fontFamily']
    
    @given(settings_data=valid_subtitle_settings())
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_5_settings_persistence_across_multiple_gets(self, test_client, settings_data):
        """
        **属性 5: 设置存储和检索（多次检索一致性）**
        
        对于任何有效的设置对象，保存后多次检索应该返回相同的结果。
        
        **Validates: Requirements 2.3, 2.5**
        """
        client, server_state = test_client
        
        # 保存设置
        post_response = client.post(
            '/api/subtitle-settings',
            data=json.dumps(settings_data),
            content_type='application/json'
        )
        assert post_response.status_code == 200
        
        # 多次检索设置
        get_responses = []
        for _ in range(3):
            response = client.get('/api/subtitle-settings')
            assert response.status_code == 200
            data = json.loads(response.data)
            get_responses.append(data['data'])
        
        # 验证所有检索结果相同
        first_result = get_responses[0]
        for result in get_responses[1:]:
            assert result == first_result, \
                "Multiple GET requests returned different results"
    
    @given(settings_data=valid_subtitle_settings())
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_property_5_settings_stored_in_server_state(self, test_client, settings_data):
        """
        **属性 5: 设置存储和检索（服务器状态验证）**
        
        对于任何有效的设置对象，保存后应该能在 server_state 中找到。
        
        **Validates: Requirements 2.3**
        """
        client, server_state = test_client
        
        # 保存设置
        post_response = client.post(
            '/api/subtitle-settings',
            data=json.dumps(settings_data),
            content_type='application/json'
        )
        assert post_response.status_code == 200
        
        # 验证设置已存储在 server_state 中
        assert server_state.subtitle_settings is not None, \
            "Settings not stored in server_state"
        
        # 验证存储的设置与发送的设置匹配
        stored_settings = server_state.subtitle_settings
        assert stored_settings['windowWidth'] == settings_data['windowWidth']
        assert stored_settings['fontSize'] == settings_data['fontSize']
        assert stored_settings['backgroundColor'] == settings_data['backgroundColor']
        assert stored_settings['fontColor'] == settings_data['fontColor']
        assert stored_settings['webSocketUrl'] == settings_data['webSocketUrl']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
