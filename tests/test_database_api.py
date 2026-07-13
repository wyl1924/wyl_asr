#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库API接口测试

测试所有数据库API接口的功能，包括：
- 会议管理API测试
- 音频文件管理API测试
- 语音识别结果API测试
- 语音识别模式API测试
- 翻译内容API测试
- 说话人管理API测试
- 会议纪要API测试
- 系统配置API测试
- 数据库信息API测试

作者: WYL ASR Team
版本: 1.0.0
创建时间: 2024年
"""

import os
import sys
import unittest
import tempfile
import json
from unittest.mock import patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.database_api import create_app
from src.modules.database_manager import DatabaseManager


class TestDatabaseAPI(unittest.TestCase):
    """数据库API测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时数据库文件
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # 创建测试应用
        self.app = create_app({'TESTING': True})
        self.client = self.app.test_client()
        
        # 使用临时数据库
        with patch('src.modules.database_api.db') as mock_db:
            mock_db.return_value = DatabaseManager(self.db_path)
            self.db = DatabaseManager(self.db_path)
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时数据库文件
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_health_check(self):
        """测试健康检查接口"""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['message'], '服务正常')
        self.assertIn('status', data['data'])
        self.assertEqual(data['data']['status'], 'healthy')
    
    def test_create_meeting(self):
        """测试创建会议接口"""
        # 正常创建会议
        meeting_data = {
            'title': 'API测试会议',
            'description': '测试API接口功能'
        }
        
        response = self.client.post('/api/meetings', 
                                  json=meeting_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 201)
        self.assertEqual(data['message'], '会议创建成功')
        self.assertIn('meeting_id', data['data'])
        self.assertEqual(data['data']['title'], 'API测试会议')
        
        # 测试缺少标题
        invalid_data = {'description': '缺少标题'}
        response = self.client.post('/api/meetings', 
                                  json=invalid_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        
        # 测试空请求
        response = self.client.post('/api/meetings')
        self.assertEqual(response.status_code, 400)
    
    def test_get_meeting(self):
        """测试获取会议信息接口"""
        # 先创建会议
        meeting_id = self.db.create_meeting('测试会议', '测试描述')
        
        # 获取会议信息
        response = self.client.get(f'/api/meetings/{meeting_id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['message'], '获取会议信息成功')
        self.assertEqual(data['data']['id'], meeting_id)
        self.assertEqual(data['data']['title'], '测试会议')
        
        # 测试不存在的会议
        response = self.client.get('/api/meetings/99999')
        self.assertEqual(response.status_code, 404)
    
    def test_end_meeting(self):
        """测试结束会议接口"""
        # 先创建会议
        meeting_id = self.db.create_meeting('测试会议')
        
        # 结束会议
        response = self.client.put(f'/api/meetings/{meeting_id}/end')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['message'], '会议已结束')
        self.assertEqual(data['data']['meeting_id'], meeting_id)
        
        # 测试不存在的会议
        response = self.client.put('/api/meetings/99999/end')
        self.assertEqual(response.status_code, 404)
    
    def test_upload_audio_file(self):
        """测试上传音频文件接口"""
        # 先创建会议
        meeting_id = self.db.create_meeting('音频测试会议')
        
        # 上传音频文件
        audio_data = {
            'file_name': 'test_audio.wav',
            'file_path': '/path/to/test_audio.wav',
            'file_size': 1024000,
            'duration': 120.5,
            'format': 'wav',
            'sample_rate': 16000,
            'channels': 1
        }
        
        response = self.client.post(f'/api/meetings/{meeting_id}/audio-files',
                                  json=audio_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 201)
        self.assertEqual(data['message'], '音频文件上传成功')
        self.assertIn('audio_id', data['data'])
        self.assertEqual(data['data']['meeting_id'], meeting_id)
        
        # 测试缺少必需字段
        invalid_data = {'file_name': 'test.wav'}
        response = self.client.post(f'/api/meetings/{meeting_id}/audio-files',
                                  json=invalid_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
    
    def test_get_meeting_audio_files(self):
        """测试获取会议音频文件列表接口"""
        # 先创建会议和音频文件
        meeting_id = self.db.create_meeting('音频测试会议')
        audio_id = self.db.save_audio_file(
            meeting_id, 'test.wav', '/path/to/test.wav'
        )
        
        # 获取音频文件列表
        response = self.client.get(f'/api/meetings/{meeting_id}/audio-files')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['message'], '获取音频文件列表成功')
        self.assertEqual(data['data']['meeting_id'], meeting_id)
        self.assertEqual(data['data']['count'], 1)
        self.assertEqual(len(data['data']['audio_files']), 1)
    
    def test_save_speech_result(self):
        """测试保存语音识别结果接口"""
        # 先创建会议
        meeting_id = self.db.create_meeting('语音识别测试会议')
        
        # 保存语音识别结果
        speech_data = {
            'speaker_id': 'speaker_001',
            'speaker_name': '张三',
            'text_content': '这是API测试的语音识别内容',
            'confidence': 0.95,
            'start_time': 0.0,
            'end_time': 5.2,
            'language': 'zh'
        }
        
        response = self.client.post(f'/api/meetings/{meeting_id}/speech-results',
                                  json=speech_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 201)
        self.assertEqual(data['message'], '语音识别结果保存成功')
        self.assertIn('speech_id', data['data'])
        self.assertEqual(data['data']['meeting_id'], meeting_id)
        
        # 测试缺少必需字段
        invalid_data = {'speaker_id': 'speaker_001'}
        response = self.client.post(f'/api/meetings/{meeting_id}/speech-results',
                                  json=invalid_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
    
    def test_save_recognition_mode(self):
        """测试保存语音识别模式结果接口"""
        # 先创建会议和音频文件
        meeting_id = self.db.create_meeting('模式测试会议')
        audio_id = self.db.save_audio_file(
            meeting_id, 'mode_test.wav', '/path/to/mode_test.wav'
        )
        
        # 保存语音识别模式结果
        mode_data = {
            'audio_file_id': audio_id,
            'mode_type': 'speaker_diarization',
            'text_content': '张三：这是区分说话人的测试内容',
            'confidence': 0.95,
            'start_time': 0.0,
            'end_time': 5.2,
            'language': 'zh'
        }
        
        response = self.client.post(f'/api/meetings/{meeting_id}/recognition-modes',
                                  json=mode_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 201)
        self.assertEqual(data['message'], '语音识别模式结果保存成功')
        self.assertIn('mode_id', data['data'])
        self.assertEqual(data['data']['mode_type'], 'speaker_diarization')
        
        # 测试无效的模式类型
        invalid_mode_data = {
            'audio_file_id': audio_id,
            'mode_type': 'invalid_mode',
            'text_content': '测试内容'
        }
        response = self.client.post(f'/api/meetings/{meeting_id}/recognition-modes',
                                  json=invalid_mode_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
    
    def test_save_meeting_translation(self):
        """测试保存会议翻译内容接口"""
        # 先创建会议、音频文件和识别模式结果
        meeting_id = self.db.create_meeting('翻译测试会议')
        audio_id = self.db.save_audio_file(
            meeting_id, 'trans_test.wav', '/path/to/trans_test.wav'
        )
        mode_id = self.db.save_speech_recognition_mode(
            meeting_id, audio_id, 'speaker_diarization', '张三：你好世界', 0.95
        )
        
        # 保存翻译内容
        translation_data = {
            'source_type': 'mode_result',
            'source_id': mode_id,
            'original_text': '张三：你好世界',
            'translated_text': 'Zhang San: Hello World',
            'source_language': 'zh',
            'target_language': 'en',
            'confidence': 0.94
        }
        
        response = self.client.post(f'/api/meetings/{meeting_id}/translations',
                                  json=translation_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 201)
        self.assertEqual(data['message'], '翻译内容保存成功')
        self.assertIn('translation_id', data['data'])
        self.assertEqual(data['data']['source_type'], 'mode_result')
        
        # 测试无效的源类型
        invalid_translation_data = {
            'source_type': 'invalid_source',
            'source_id': mode_id,
            'original_text': '测试',
            'translated_text': 'Test',
            'source_language': 'zh',
            'target_language': 'en'
        }
        response = self.client.post(f'/api/meetings/{meeting_id}/translations',
                                  json=invalid_translation_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
    
    def test_save_speaker(self):
        """测试保存说话人信息接口"""
        speaker_data = {
            'speaker_id': 'api_speaker_001',
            'name': 'API测试用户',
            'email': 'api_test@example.com',
            'voice_features': {
                'mfcc': [1.2, 3.4, 5.6],
                'pitch': 150.5,
                'energy': 0.8
            }
        }
        
        response = self.client.post('/api/speakers',
                                  json=speaker_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 201)
        self.assertEqual(data['message'], '说话人信息保存成功')
        self.assertIn('id', data['data'])
        self.assertEqual(data['data']['speaker_id'], 'api_speaker_001')
        
        # 测试缺少speaker_id
        invalid_data = {'name': '测试用户'}
        response = self.client.post('/api/speakers',
                                  json=invalid_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
    
    def test_get_speaker(self):
        """测试获取说话人信息接口"""
        # 先保存说话人信息
        voice_features = {'mfcc': [1.2, 3.4], 'pitch': 150.5}
        self.db.save_speaker(
            'api_speaker_002', 'API测试用户2', 
            'test2@example.com', voice_features
        )
        
        # 获取说话人信息
        response = self.client.get('/api/speakers/api_speaker_002')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['message'], '获取说话人信息成功')
        self.assertEqual(data['data']['speaker_id'], 'api_speaker_002')
        self.assertEqual(data['data']['name'], 'API测试用户2')
        self.assertIsInstance(data['data']['voice_features'], dict)
        
        # 测试不存在的说话人
        response = self.client.get('/api/speakers/nonexistent')
        self.assertEqual(response.status_code, 404)
    
    def test_save_meeting_minutes(self):
        """测试保存会议纪要接口"""
        # 先创建会议
        meeting_id = self.db.create_meeting('纪要测试会议')
        
        # 保存会议纪要
        minutes_data = {
            'summary': 'API测试会议纪要摘要',
            'key_points': ['要点1', '要点2', '要点3'],
            'action_items': ['行动项1', '行动项2'],
            'decisions': ['决议1', '决议2'],
            'participants': ['张三', '李四', 'API测试用户']
        }
        
        response = self.client.post(f'/api/meetings/{meeting_id}/minutes',
                                  json=minutes_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 201)
        self.assertEqual(data['message'], '会议纪要保存成功')
        self.assertIn('minutes_id', data['data'])
        self.assertEqual(data['data']['meeting_id'], meeting_id)
    
    def test_get_meeting_minutes(self):
        """测试获取会议纪要接口"""
        # 先创建会议和纪要
        meeting_id = self.db.create_meeting('纪要测试会议')
        key_points = ['API测试要点1', 'API测试要点2']
        self.db.save_meeting_minutes(
            meeting_id, 'API测试摘要', key_points, ['行动项'], ['决议'], ['参与者']
        )
        
        # 获取会议纪要
        response = self.client.get(f'/api/meetings/{meeting_id}/minutes')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['message'], '获取会议纪要成功')
        self.assertEqual(data['data']['meeting_id'], meeting_id)
        self.assertEqual(data['data']['summary'], 'API测试摘要')
        self.assertIsInstance(data['data']['key_points'], list)
        self.assertEqual(len(data['data']['key_points']), 2)
        
        # 测试不存在的会议纪要
        response = self.client.get('/api/meetings/99999/minutes')
        self.assertEqual(response.status_code, 404)
    
    def test_set_config(self):
        """测试设置系统配置接口"""
        config_data = {
            'key': 'api_test_config',
            'value': 'api_test_value',
            'description': 'API测试配置项'
        }
        
        response = self.client.post('/api/config',
                                  json=config_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 201)
        self.assertEqual(data['message'], '配置设置成功')
        self.assertIn('config_id', data['data'])
        self.assertEqual(data['data']['key'], 'api_test_config')
        self.assertEqual(data['data']['value'], 'api_test_value')
        
        # 测试缺少必需字段
        invalid_data = {'key': 'test_key'}
        response = self.client.post('/api/config',
                                  json=invalid_data,
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
    
    def test_get_config(self):
        """测试获取系统配置接口"""
        # 先设置配置
        self.db.set_config('api_test_key', 'api_test_value', 'API测试配置')
        
        # 获取配置
        response = self.client.get('/api/config/api_test_key')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['message'], '获取配置成功')
        self.assertEqual(data['data']['key'], 'api_test_key')
        self.assertEqual(data['data']['value'], 'api_test_value')
        
        # 测试不存在的配置
        response = self.client.get('/api/config/nonexistent_key')
        self.assertEqual(response.status_code, 404)
    
    def test_get_database_info(self):
        """测试获取数据库信息接口"""
        response = self.client.get('/api/database/info')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['message'], '获取数据库信息成功')
        self.assertIn('database_path', data['data'])
        self.assertIn('database_size', data['data'])
        self.assertIn('tables', data['data'])
        self.assertIsInstance(data['data']['tables'], list)
    
    def test_vacuum_database(self):
        """测试优化数据库接口"""
        response = self.client.post('/api/database/vacuum')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['message'], '数据库优化完成')
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试404错误
        response = self.client.get('/api/nonexistent')
        self.assertEqual(response.status_code, 404)
        
        # 测试无效JSON
        response = self.client.post('/api/meetings',
                                  data='invalid json',
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
    
    def test_query_parameters(self):
        """测试查询参数"""
        # 先创建测试数据
        meeting_id = self.db.create_meeting('查询参数测试会议')
        audio_id = self.db.save_audio_file(
            meeting_id, 'query_test.wav', '/path/to/query_test.wav'
        )
        
        # 保存两种模式的识别结果
        self.db.save_speech_recognition_mode(
            meeting_id, audio_id, 'speaker_diarization', '区分说话人内容', 0.95
        )
        self.db.save_speech_recognition_mode(
            meeting_id, audio_id, 'no_speaker_diarization', '不区分说话人内容', 0.92
        )
        
        # 测试带查询参数的请求
        response = self.client.get(
            f'/api/meetings/{meeting_id}/recognition-modes?mode_type=speaker_diarization'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['data']['count'], 1)
        self.assertEqual(data['data']['mode_type'], 'speaker_diarization')


class TestDatabaseAPIIntegration(unittest.TestCase):
    """数据库API集成测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        self.app = create_app({'TESTING': True})
        self.client = self.app.test_client()
        
        with patch('src.modules.database_api.db') as mock_db:
            mock_db.return_value = DatabaseManager(self.db_path)
            self.db = DatabaseManager(self.db_path)
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_complete_workflow_api(self):
        """测试完整的API工作流程"""
        # 1. 创建会议
        meeting_data = {
            'title': 'API集成测试会议',
            'description': '测试完整的API工作流程'
        }
        response = self.client.post('/api/meetings', json=meeting_data)
        self.assertEqual(response.status_code, 201)
        meeting_id = json.loads(response.data)['data']['meeting_id']
        
        # 2. 上传音频文件
        audio_data = {
            'file_name': 'integration_test.wav',
            'file_path': '/path/to/integration_test.wav',
            'file_size': 2048000,
            'duration': 180.0,
            'format': 'wav',
            'sample_rate': 16000,
            'channels': 1
        }
        response = self.client.post(f'/api/meetings/{meeting_id}/audio-files', json=audio_data)
        self.assertEqual(response.status_code, 201)
        audio_id = json.loads(response.data)['data']['audio_id']
        
        # 3. 保存说话人信息
        speaker_data = {
            'speaker_id': 'integration_speaker',
            'name': '集成测试用户',
            'email': 'integration@example.com'
        }
        response = self.client.post('/api/speakers', json=speaker_data)
        self.assertEqual(response.status_code, 201)
        
        # 4. 保存语音识别结果
        speech_data = {
            'speaker_id': 'integration_speaker',
            'speaker_name': '集成测试用户',
            'text_content': '这是集成测试的语音识别内容',
            'confidence': 0.98
        }
        response = self.client.post(f'/api/meetings/{meeting_id}/speech-results', json=speech_data)
        self.assertEqual(response.status_code, 201)
        speech_id = json.loads(response.data)['data']['speech_id']
        
        # 5. 保存语音识别模式结果
        mode_data = {
            'audio_file_id': audio_id,
            'mode_type': 'speaker_diarization',
            'text_content': '集成测试用户：这是集成测试的语音识别内容',
            'confidence': 0.96
        }
        response = self.client.post(f'/api/meetings/{meeting_id}/recognition-modes', json=mode_data)
        self.assertEqual(response.status_code, 201)
        mode_id = json.loads(response.data)['data']['mode_id']
        
        # 6. 保存传统翻译结果
        translation_data = {
            'original_text': '这是集成测试的语音识别内容',
            'translated_text': 'This is the speech recognition content of integration test',
            'source_language': 'zh',
            'target_language': 'en',
            'confidence': 0.95
        }
        response = self.client.post(f'/api/speech-results/{speech_id}/translations', json=translation_data)
        self.assertEqual(response.status_code, 201)
        
        # 7. 保存会议翻译内容
        meeting_translation_data = {
            'source_type': 'mode_result',
            'source_id': mode_id,
            'original_text': '集成测试用户：这是集成测试的语音识别内容',
            'translated_text': 'Integration Test User: This is the speech recognition content of integration test',
            'source_language': 'zh',
            'target_language': 'en',
            'confidence': 0.93
        }
        response = self.client.post(f'/api/meetings/{meeting_id}/translations', json=meeting_translation_data)
        self.assertEqual(response.status_code, 201)
        
        # 8. 保存会议纪要
        minutes_data = {
            'summary': '集成测试会议纪要摘要',
            'key_points': ['测试API功能', '验证工作流程', '确保集成正常'],
            'action_items': ['完善API文档', '优化性能', '添加更多测试'],
            'decisions': ['采用RESTful API设计', '使用Flask框架'],
            'participants': ['集成测试用户']
        }
        response = self.client.post(f'/api/meetings/{meeting_id}/minutes', json=minutes_data)
        self.assertEqual(response.status_code, 201)
        
        # 9. 结束会议
        response = self.client.put(f'/api/meetings/{meeting_id}/end')
        self.assertEqual(response.status_code, 200)
        
        # 10. 验证所有数据
        # 验证会议信息
        response = self.client.get(f'/api/meetings/{meeting_id}')
        self.assertEqual(response.status_code, 200)
        meeting_info = json.loads(response.data)['data']
        self.assertEqual(meeting_info['status'], 'completed')
        
        # 验证音频文件
        response = self.client.get(f'/api/meetings/{meeting_id}/audio-files')
        self.assertEqual(response.status_code, 200)
        audio_files = json.loads(response.data)['data']
        self.assertEqual(audio_files['count'], 1)
        
        # 验证语音识别结果
        response = self.client.get(f'/api/meetings/{meeting_id}/speech-results')
        self.assertEqual(response.status_code, 200)
        speech_results = json.loads(response.data)['data']
        self.assertEqual(speech_results['count'], 1)
        
        # 验证识别模式结果
        response = self.client.get(f'/api/meetings/{meeting_id}/recognition-modes')
        self.assertEqual(response.status_code, 200)
        mode_results = json.loads(response.data)['data']
        self.assertEqual(mode_results['count'], 1)
        
        # 验证翻译内容
        response = self.client.get(f'/api/meetings/{meeting_id}/translations')
        self.assertEqual(response.status_code, 200)
        translations = json.loads(response.data)['data']
        self.assertEqual(translations['count'], 1)
        
        # 验证会议纪要
        response = self.client.get(f'/api/meetings/{meeting_id}/minutes')
        self.assertEqual(response.status_code, 200)
        minutes = json.loads(response.data)['data']
        self.assertEqual(minutes['summary'], '集成测试会议纪要摘要')
        
        # 验证说话人信息
        response = self.client.get('/api/speakers/integration_speaker')
        self.assertEqual(response.status_code, 200)
        speaker = json.loads(response.data)['data']
        self.assertEqual(speaker['name'], '集成测试用户')
        
        print("API集成测试完成，所有功能正常")


if __name__ == '__main__':
    # 设置日志级别
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 运行测试
    unittest.main(verbosity=2)