#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕设置API单元测试
==================

测试字幕设置API的基本功能。
"""

import unittest
import json
from unittest.mock import MagicMock, patch
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
sys.path.insert(0, project_root)

from wyl_asr.src.modules.database.database_api import create_app
from wyl_asr.src.modules.core.server_state import ServerState
from wyl_asr.src.api.subtitle_settings import init_subtitle_settings_api


class TestSubtitleSettingsAPI(unittest.TestCase):
    """测试字幕设置API"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试用的server_state
        self.server_state = ServerState()
        self.server_state.subtitle_settings = None
        self.server_state.websocket_users = set()
        
        # 创建测试应用
        self.app = create_app({'TESTING': True}, server_state=self.server_state)
        self.client = self.app.test_client()
    
    def test_get_default_settings(self):
        """测试获取默认设置"""
        response = self.client.get('/api/subtitle-settings')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        # 验证默认值
        settings = data['data']
        self.assertEqual(settings['windowWidth'], 80)
        self.assertEqual(settings['cornerRadius'], 10)
        self.assertEqual(settings['backgroundColor'], '#000000')
        self.assertEqual(settings['backgroundOpacity'], 75)
        self.assertEqual(settings['fontFamily'], '宋体')
        self.assertEqual(settings['fontSize'], 14)
        self.assertEqual(settings['fontColor'], '默认')
        self.assertFalse(settings['isBold'])
        self.assertFalse(settings['isItalic'])
        self.assertFalse(settings['showEnglish'])
        self.assertEqual(settings['maxDisplayLines'], 2)
        self.assertEqual(settings['scrollSpeed'], 60)
        self.assertEqual(settings['webSocketUrl'], 'ws://127.0.0.1:10095/')
    
    def test_save_valid_settings(self):
        """测试保存有效设置"""
        valid_settings = {
            "windowWidth": 90,
            "cornerRadius": 15,
            "backgroundColor": "#FF0000",
            "backgroundOpacity": 80,
            "fontFamily": "微软雅黑",
            "fontSize": 16,
            "fontColor": "#FFFFFF",
            "isBold": True,
            "isItalic": False,
            "showEnglish": True,
            "maxDisplayLines": 3,
            "scrollSpeed": 80,
            "webSocketUrl": "ws://192.168.1.100:10095/"
        }
        
        response = self.client.post(
            '/api/subtitle-settings',
            data=json.dumps(valid_settings),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        
        # 验证设置已保存
        self.assertIsNotNone(self.server_state.subtitle_settings)
        self.assertEqual(self.server_state.subtitle_settings['windowWidth'], 90)
        self.assertEqual(self.server_state.subtitle_settings['fontFamily'], '微软雅黑')
    
    def test_save_settings_with_invalid_window_width(self):
        """测试保存无效的窗口宽度"""
        invalid_settings = {
            "windowWidth": 5,  # 小于最小值10
            "cornerRadius": 10,
            "backgroundColor": "#000000",
            "backgroundOpacity": 75,
            "fontFamily": "宋体",
            "fontSize": 14,
            "fontColor": "默认",
            "isBold": False,
            "isItalic": False,
            "showEnglish": False,
            "maxDisplayLines": 2,
            "scrollSpeed": 60,
            "webSocketUrl": "ws://127.0.0.1:10095/"
        }
        
        response = self.client.post(
            '/api/subtitle-settings',
            data=json.dumps(invalid_settings),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('errors', data['data'])
    
    def test_save_settings_with_invalid_color(self):
        """测试保存无效的颜色格式"""
        invalid_settings = {
            "windowWidth": 80,
            "cornerRadius": 10,
            "backgroundColor": "red",  # 无效格式
            "backgroundOpacity": 75,
            "fontFamily": "宋体",
            "fontSize": 14,
            "fontColor": "默认",
            "isBold": False,
            "isItalic": False,
            "showEnglish": False,
            "maxDisplayLines": 2,
            "scrollSpeed": 60,
            "webSocketUrl": "ws://127.0.0.1:10095/"
        }
        
        response = self.client.post(
            '/api/subtitle-settings',
            data=json.dumps(invalid_settings),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_save_settings_with_invalid_websocket_url(self):
        """测试保存无效的WebSocket URL"""
        invalid_settings = {
            "windowWidth": 80,
            "cornerRadius": 10,
            "backgroundColor": "#000000",
            "backgroundOpacity": 75,
            "fontFamily": "宋体",
            "fontSize": 14,
            "fontColor": "默认",
            "isBold": False,
            "isItalic": False,
            "showEnglish": False,
            "maxDisplayLines": 2,
            "scrollSpeed": 60,
            "webSocketUrl": "http://127.0.0.1:10095/"  # 应该是ws://或wss://
        }
        
        response = self.client.post(
            '/api/subtitle-settings',
            data=json.dumps(invalid_settings),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
    
    def test_get_saved_settings(self):
        """测试获取已保存的设置"""
        # 先保存设置
        settings_to_save = {
            "windowWidth": 85,
            "cornerRadius": 12,
            "backgroundColor": "#00FF00",
            "backgroundOpacity": 70,
            "fontFamily": "黑体",
            "fontSize": 18,
            "fontColor": "#000000",
            "isBold": False,
            "isItalic": True,
            "showEnglish": False,
            "maxDisplayLines": 4,
            "scrollSpeed": 100,
            "webSocketUrl": "ws://localhost:8080/"
        }
        
        self.client.post(
            '/api/subtitle-settings',
            data=json.dumps(settings_to_save),
            content_type='application/json'
        )
        
        # 获取设置
        response = self.client.get('/api/subtitle-settings')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # 验证返回的设置与保存的一致
        settings = data['data']
        self.assertEqual(settings['windowWidth'], 85)
        self.assertEqual(settings['fontFamily'], '黑体')
        self.assertEqual(settings['fontSize'], 18)
        self.assertTrue(settings['isItalic'])
    
    def test_save_empty_request(self):
        """测试保存空请求"""
        response = self.client.post(
            '/api/subtitle-settings',
            data='',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('请求数据不能为空', data['message'])
    
    def test_settings_persistence_across_requests(self):
        """测试设置在多次请求间的持久性"""
        # 保存设置
        settings1 = {
            "windowWidth": 75,
            "cornerRadius": 8,
            "backgroundColor": "#0000FF",
            "backgroundOpacity": 65,
            "fontFamily": "楷体",
            "fontSize": 20,
            "fontColor": "#FFFF00",
            "isBold": True,
            "isItalic": True,
            "showEnglish": True,
            "maxDisplayLines": 5,
            "scrollSpeed": 120,
            "webSocketUrl": "wss://secure.example.com:443/"
        }
        
        self.client.post(
            '/api/subtitle-settings',
            data=json.dumps(settings1),
            content_type='application/json'
        )
        
        # 第一次获取
        response1 = self.client.get('/api/subtitle-settings')
        data1 = json.loads(response1.data)
        
        # 第二次获取
        response2 = self.client.get('/api/subtitle-settings')
        data2 = json.loads(response2.data)
        
        # 验证两次获取的结果一致
        self.assertEqual(data1['data'], data2['data'])
        self.assertEqual(data1['data']['windowWidth'], 75)
        self.assertEqual(data1['data']['fontFamily'], '楷体')


if __name__ == '__main__':
    unittest.main(verbosity=2)
