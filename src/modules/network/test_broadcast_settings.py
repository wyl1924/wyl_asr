#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕设置广播功能单元测试
=======================

测试 broadcast_settings_update 函数的基本功能。
"""

import unittest
import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../../..'))
sys.path.insert(0, project_root)

from wyl_asr.src.modules.network.websocket_manager import broadcast_settings_update
from wyl_asr.src.modules.core.server_state import ServerState


class TestBroadcastSettingsUpdate(unittest.TestCase):
    """测试字幕设置广播功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.server_state = ServerState()
        self.server_state.websocket_users = set()
        self.server_state.logger = None  # 使用print而不是logger
        
        # 创建测试设置
        self.test_settings = {
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
            "webSocketUrl": "ws://127.0.0.1:10095/"
        }
    
    def test_broadcast_settings_message_format(self):
        """测试广播消息格式是否正确"""
        # 使用patch来模拟broadcast_message函数
        with patch('wyl_asr.src.modules.network.websocket_manager.broadcast_message', new_callable=AsyncMock) as mock_broadcast:
            # 运行广播函数
            asyncio.run(broadcast_settings_update(self.test_settings, self.server_state))
            
            # 验证broadcast_message被调用
            self.assertTrue(mock_broadcast.called)
            
            # 获取调用参数
            call_args = mock_broadcast.call_args
            message_str = call_args[0][0]  # 第一个位置参数是消息字符串
            server_state_arg = call_args[0][1]  # 第二个位置参数是server_state
            
            # 验证server_state参数
            self.assertEqual(server_state_arg, self.server_state)
            
            # 验证exclude_websocket参数为None
            self.assertIsNone(call_args[1]['exclude_websocket'])
            
            # 解析消息JSON
            message = json.loads(message_str)
            
            # 验证消息结构
            self.assertIn('type', message)
            self.assertEqual(message['type'], 'settings_update')
            
            self.assertIn('data', message)
            self.assertEqual(message['data'], self.test_settings)
    
    def test_broadcast_settings_with_all_fields(self):
        """测试广播包含所有字段的设置"""
        with patch('wyl_asr.src.modules.network.websocket_manager.broadcast_message', new_callable=AsyncMock) as mock_broadcast:
            asyncio.run(broadcast_settings_update(self.test_settings, self.server_state))
            
            # 获取广播的消息
            message_str = mock_broadcast.call_args[0][0]
            message = json.loads(message_str)
            
            # 验证所有字段都存在
            data = message['data']
            expected_fields = [
                'windowWidth', 'cornerRadius', 'backgroundColor', 'backgroundOpacity',
                'fontFamily', 'fontSize', 'fontColor', 'isBold', 'isItalic',
                'showEnglish', 'maxDisplayLines', 'scrollSpeed', 'webSocketUrl'
            ]
            
            for field in expected_fields:
                self.assertIn(field, data, f"字段 {field} 应该存在于广播消息中")
    
    def test_broadcast_settings_with_chinese_characters(self):
        """测试广播包含中文字符的设置"""
        settings_with_chinese = self.test_settings.copy()
        settings_with_chinese['fontFamily'] = '微软雅黑'
        settings_with_chinese['fontColor'] = '默认'
        
        with patch('wyl_asr.src.modules.network.websocket_manager.broadcast_message', new_callable=AsyncMock) as mock_broadcast:
            asyncio.run(broadcast_settings_update(settings_with_chinese, self.server_state))
            
            # 获取广播的消息
            message_str = mock_broadcast.call_args[0][0]
            message = json.loads(message_str)
            
            # 验证中文字符正确保存
            self.assertEqual(message['data']['fontFamily'], '微软雅黑')
            self.assertEqual(message['data']['fontColor'], '默认')
    
    def test_broadcast_settings_error_handling(self):
        """测试广播过程中的错误处理"""
        # 模拟broadcast_message抛出异常
        with patch('wyl_asr.src.modules.network.websocket_manager.broadcast_message', new_callable=AsyncMock) as mock_broadcast:
            mock_broadcast.side_effect = Exception("模拟的广播错误")
            
            # 应该不会抛出异常，而是被捕获并记录
            try:
                asyncio.run(broadcast_settings_update(self.test_settings, self.server_state))
            except Exception as e:
                self.fail(f"broadcast_settings_update 不应该抛出异常，但抛出了: {e}")


def run_tests():
    """运行所有测试"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    print("=" * 60)
    print("字幕设置广播功能单元测试")
    print("=" * 60)
    run_tests()
