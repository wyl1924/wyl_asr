#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理模块测试

测试SQLite数据库管理器的各项功能，包括：
- 数据库初始化
- 用户管理
- 会议管理
- 语音识别结果存储
- 翻译结果存储
- 说话人管理
- 会议纪要管理
- 系统配置管理

作者: AIM ZST Team
版本: 1.0.0
创建时间: 2024年
"""

import os
import sys
import unittest
import tempfile
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.database_manager import DatabaseManager, DatabaseError, get_database_manager


class TestDatabaseManager(unittest.TestCase):
    """数据库管理器测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时数据库文件
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # 初始化数据库管理器
        self.db = DatabaseManager(self.db_path)
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时数据库文件
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_database_initialization(self):
        """测试数据库初始化"""
        # 检查数据库文件是否创建
        self.assertTrue(os.path.exists(self.db_path))
        
        # 检查表是否创建
        info = self.db.get_database_info()
        expected_tables = {
            'meetings', 'speech_recognition_results',
            'translation_results', 'speakers', 'meeting_minutes',
            'system_config', 'meeting_audio_files', 'speech_recognition_modes',
            'meeting_translations'
        }
        actual_tables = {table['name'] for table in info['tables']}
        self.assertTrue(expected_tables.issubset(actual_tables))
    
    def test_meeting_management(self):
        """测试会议管理功能"""
        # 创建会议
        meeting_id = self.db.create_meeting(
            title="测试会议",
            description="这是一个测试会议"
        )
        self.assertIsInstance(meeting_id, int)
        self.assertGreater(meeting_id, 0)
        
        # 获取会议信息
        meeting = self.db.get_meeting(meeting_id)
        self.assertIsNotNone(meeting)
        self.assertEqual(meeting['title'], "测试会议")
        self.assertEqual(meeting['description'], "这是一个测试会议")
        self.assertEqual(meeting['status'], 'active')
        
        # 结束会议
        affected_rows = self.db.end_meeting(meeting_id)
        self.assertEqual(affected_rows, 1)
        
        # 检查会议状态
        updated_meeting = self.db.get_meeting(meeting_id)
        self.assertEqual(updated_meeting['status'], 'completed')
        self.assertIsNotNone(updated_meeting['end_time'])
    
    def test_speech_recognition_results(self):
        """测试语音识别结果存储"""
        # 创建会议
        meeting_id = self.db.create_meeting("语音测试会议")
        
        # 保存语音识别结果
        speech_id = self.db.save_speech_result(
            meeting_id=meeting_id,
            speaker_id="speaker_001",
            speaker_name="张三",
            text_content="这是一段测试语音识别结果",
            confidence=0.95,
            start_time=0.0,
            end_time=3.5,
            language="zh"
        )
        self.assertIsInstance(speech_id, int)
        self.assertGreater(speech_id, 0)
        
        # 获取会议的语音识别结果
        results = self.db.get_meeting_speech_results(meeting_id)
        self.assertEqual(len(results), 1)
        
        result = results[0]
        self.assertEqual(result['meeting_id'], meeting_id)
        self.assertEqual(result['speaker_id'], "speaker_001")
        self.assertEqual(result['speaker_name'], "张三")
        self.assertEqual(result['text_content'], "这是一段测试语音识别结果")
        self.assertEqual(result['confidence'], 0.95)
        self.assertEqual(result['language'], "zh")
    
    def test_translation_results(self):
        """测试翻译结果存储"""
        # 创建会议和语音识别结果
        meeting_id = self.db.create_meeting("翻译测试会议")
        speech_id = self.db.save_speech_result(
            meeting_id, "speaker_001", "张三", "你好世界", 0.9
        )
        
        # 保存翻译结果
        translation_id = self.db.save_translation_result(
            speech_result_id=speech_id,
            original_text="你好世界",
            translated_text="Hello World",
            source_language="zh",
            target_language="en",
            confidence=0.92
        )
        self.assertIsInstance(translation_id, int)
        self.assertGreater(translation_id, 0)
        
        # 验证翻译结果
        query = "SELECT * FROM translation_results WHERE id = ?"
        results = self.db.execute_query(query, (translation_id,))
        self.assertEqual(len(results), 1)
        
        result = results[0]
        self.assertEqual(result['speech_result_id'], speech_id)
        self.assertEqual(result['original_text'], "你好世界")
        self.assertEqual(result['translated_text'], "Hello World")
        self.assertEqual(result['source_language'], "zh")
        self.assertEqual(result['target_language'], "en")
    
    def test_speaker_management(self):
        """测试说话人管理功能"""
        # 保存说话人信息
        voice_features = {
            "mfcc": [1.2, 3.4, 5.6],
            "pitch": 150.5,
            "energy": 0.8
        }
        
        speaker_id = self.db.save_speaker(
            speaker_id="speaker_001",
            name="张三",
            email="zhangsan@example.com",
            voice_features=voice_features
        )
        self.assertIsInstance(speaker_id, int)
        self.assertGreater(speaker_id, 0)
        
        # 获取说话人信息
        speaker = self.db.get_speaker("speaker_001")
        self.assertIsNotNone(speaker)
        self.assertEqual(speaker['speaker_id'], "speaker_001")
        self.assertEqual(speaker['name'], "张三")
        self.assertEqual(speaker['email'], "zhangsan@example.com")
        
        # 验证声纹特征
        stored_features = json.loads(speaker['voice_features'])
        self.assertEqual(stored_features, voice_features)
        
        # 测试更新说话人信息
        updated_features = {"mfcc": [2.1, 4.3, 6.5]}
        self.db.save_speaker(
            speaker_id="speaker_001",
            name="张三（更新）",
            voice_features=updated_features
        )
        
        updated_speaker = self.db.get_speaker("speaker_001")
        self.assertEqual(updated_speaker['name'], "张三（更新）")
        updated_stored_features = json.loads(updated_speaker['voice_features'])
        self.assertEqual(updated_stored_features, updated_features)
    
    def test_meeting_minutes(self):
        """测试会议纪要管理"""
        # 创建会议
        meeting_id = self.db.create_meeting("纪要测试会议")
        
        # 保存会议纪要
        key_points = ["要点1", "要点2", "要点3"]
        action_items = ["行动项1", "行动项2"]
        decisions = ["决议1", "决议2"]
        participants = ["张三", "李四", "王五"]
        
        minutes_id = self.db.save_meeting_minutes(
            meeting_id=meeting_id,
            summary="这是会议摘要",
            key_points=key_points,
            action_items=action_items,
            decisions=decisions,
            participants=participants
        )
        self.assertIsInstance(minutes_id, int)
        self.assertGreater(minutes_id, 0)
        
        # 获取会议纪要
        minutes = self.db.get_meeting_minutes(meeting_id)
        self.assertIsNotNone(minutes)
        self.assertEqual(minutes['meeting_id'], meeting_id)
        self.assertEqual(minutes['summary'], "这是会议摘要")
        
        # 验证JSON数据
        self.assertEqual(json.loads(minutes['key_points']), key_points)
        self.assertEqual(json.loads(minutes['action_items']), action_items)
        self.assertEqual(json.loads(minutes['decisions']), decisions)
        self.assertEqual(json.loads(minutes['participants']), participants)
    
    def test_system_config(self):
        """测试系统配置管理"""
        # 设置配置
        config_id = self.db.set_config(
            key="test_config",
            value="test_value",
            description="测试配置项"
        )
        self.assertIsInstance(config_id, int)
        self.assertGreater(config_id, 0)
        
        # 获取配置
        value = self.db.get_config("test_config")
        self.assertEqual(value, "test_value")
        
        # 更新配置
        self.db.set_config("test_config", "updated_value", "更新的测试配置")
        updated_value = self.db.get_config("test_config")
        self.assertEqual(updated_value, "updated_value")
        
        # 获取不存在的配置
        non_existent = self.db.get_config("non_existent_key")
        self.assertIsNone(non_existent)
    
    def test_database_info(self):
        """测试数据库信息获取"""
        info = self.db.get_database_info()
        
        # 检查基本信息
        self.assertEqual(info['database_path'], self.db_path)
        self.assertGreater(info['database_size'], 0)
        self.assertIsInstance(info['tables'], list)
        
        # 检查表信息
        table_names = {table['name'] for table in info['tables']}
        expected_tables = {
            'users', 'meetings', 'speech_recognition_results',
            'translation_results', 'speakers', 'meeting_minutes',
            'system_config'
        }
        self.assertTrue(expected_tables.issubset(table_names))
        
        # 检查行数统计
        for table in info['tables']:
            self.assertIsInstance(table['row_count'], int)
            self.assertGreaterEqual(table['row_count'], 0)
    
    def test_vacuum(self):
        """测试数据库优化"""
        # 添加一些数据
        user_id = self.db.create_user("vacuum_user", "vacuum@example.com")
        meeting_id = self.db.create_meeting("优化测试会议", created_by=user_id)
        
        # 执行优化
        try:
            self.db.vacuum()
        except Exception as e:
            self.fail(f"数据库优化失败: {e}")
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        # 获取两个实例
        db1 = get_database_manager(self.db_path)
        db2 = get_database_manager(self.db_path)
        
        # 应该是同一个实例
        self.assertIs(db1, db2)
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试无效路径
        with self.assertRaises(DatabaseError):
            invalid_db = DatabaseManager("/invalid/path/database.db")
        
        # 测试SQL错误
        with self.assertRaises(DatabaseError):
            self.db.execute_query("INVALID SQL QUERY")


class TestDatabaseIntegration(unittest.TestCase):
    """数据库集成测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.db = DatabaseManager(self.db_path)
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_audio_file_management(self):
        """测试音频文件管理功能"""
        # 创建会议
        meeting_id = self.db.create_meeting("音频测试会议")
        
        # 保存音频文件
        audio_id = self.db.save_audio_file(
            meeting_id=meeting_id,
            file_name="test_audio.wav",
            file_path="/path/to/test_audio.wav",
            file_size=1024000,
            duration=120.5,
            format="wav",
            sample_rate=16000,
            channels=1
        )
        self.assertIsInstance(audio_id, int)
        self.assertGreater(audio_id, 0)
        
        # 获取音频文件信息
        audio_file = self.db.get_audio_file(audio_id)
        self.assertIsNotNone(audio_file)
        self.assertEqual(audio_file['meeting_id'], meeting_id)
        self.assertEqual(audio_file['file_name'], "test_audio.wav")
        self.assertEqual(audio_file['file_size'], 1024000)
        self.assertEqual(audio_file['duration'], 120.5)
        
        # 获取会议的所有音频文件
        audio_files = self.db.get_meeting_audio_files(meeting_id)
        self.assertEqual(len(audio_files), 1)
        self.assertEqual(audio_files[0]['id'], audio_id)
        
        # 删除音频文件
        affected_rows = self.db.delete_audio_file(audio_id)
        self.assertEqual(affected_rows, 1)
        
        # 验证软删除
        active_files = self.db.get_meeting_audio_files(meeting_id)
        self.assertEqual(len(active_files), 0)
    
    def test_speech_recognition_modes(self):
        """测试语音识别模式功能"""
        # 创建会议和音频文件
        meeting_id = self.db.create_meeting("模式测试会议")
        audio_id = self.db.save_audio_file(
            meeting_id, "mode_test.wav", "/path/to/mode_test.wav"
        )
        
        # 保存区分说话人模式结果
        mode_id1 = self.db.save_speech_recognition_mode(
            meeting_id=meeting_id,
            audio_file_id=audio_id,
            mode_type="speaker_diarization",
            text_content="张三：大家好，今天我们开会讨论项目进展。",
            confidence=0.95,
            start_time=0.0,
            end_time=5.2
        )
        
        # 保存不区分说话人模式结果
        mode_id2 = self.db.save_speech_recognition_mode(
            meeting_id=meeting_id,
            audio_file_id=audio_id,
            mode_type="no_speaker_diarization",
            text_content="大家好，今天我们开会讨论项目进展。",
            confidence=0.92,
            start_time=0.0,
            end_time=5.2
        )
        
        # 获取所有模式结果
        all_modes = self.db.get_speech_recognition_modes(meeting_id)
        self.assertEqual(len(all_modes), 2)
        
        # 获取特定模式结果
        speaker_modes = self.db.get_speech_recognition_modes(
            meeting_id, "speaker_diarization"
        )
        self.assertEqual(len(speaker_modes), 1)
        self.assertEqual(speaker_modes[0]['mode_type'], "speaker_diarization")
        
        no_speaker_modes = self.db.get_speech_recognition_modes(
            meeting_id, "no_speaker_diarization"
        )
        self.assertEqual(len(no_speaker_modes), 1)
        self.assertEqual(no_speaker_modes[0]['mode_type'], "no_speaker_diarization")
        
        # 获取音频文件的识别结果
        audio_modes = self.db.get_audio_file_recognition_modes(audio_id)
        self.assertEqual(len(audio_modes), 2)
    
    def test_meeting_translations(self):
        """测试会议翻译内容管理"""
        # 创建会议和音频文件
        meeting_id = self.db.create_meeting("翻译测试会议")
        audio_id = self.db.save_audio_file(
            meeting_id, "trans_test.wav", "/path/to/trans_test.wav"
        )
        
        # 创建语音识别结果
        speech_id = self.db.save_speech_result(
            meeting_id, "speaker_001", "张三", "你好，世界！", 0.95
        )
        
        # 创建模式识别结果
        mode_id = self.db.save_speech_recognition_mode(
            meeting_id, audio_id, "speaker_diarization", 
            "张三：你好，世界！", 0.93
        )
        
        # 保存基于语音识别结果的翻译
        trans_id1 = self.db.save_meeting_translation(
            meeting_id=meeting_id,
            source_type="speech_result",
            source_id=speech_id,
            original_text="你好，世界！",
            translated_text="Hello, World!",
            source_language="zh",
            target_language="en",
            confidence=0.96
        )
        
        # 保存基于模式识别结果的翻译
        trans_id2 = self.db.save_meeting_translation(
            meeting_id=meeting_id,
            source_type="mode_result",
            source_id=mode_id,
            original_text="张三：你好，世界！",
            translated_text="Zhang San: Hello, World!",
            source_language="zh",
            target_language="en",
            confidence=0.94
        )
        
        # 获取所有翻译内容
        all_translations = self.db.get_meeting_translations(meeting_id)
        self.assertEqual(len(all_translations), 2)
        
        # 获取特定类型的翻译内容
        speech_translations = self.db.get_meeting_translations(
            meeting_id, "speech_result"
        )
        self.assertEqual(len(speech_translations), 1)
        self.assertEqual(speech_translations[0]['source_id'], speech_id)
        
        mode_translations = self.db.get_meeting_translations(
            meeting_id, "mode_result"
        )
        self.assertEqual(len(mode_translations), 1)
        self.assertEqual(mode_translations[0]['source_id'], mode_id)
        
        # 根据源记录获取翻译
        source_translations = self.db.get_translation_by_source(
            "speech_result", speech_id
        )
        self.assertEqual(len(source_translations), 1)
        self.assertEqual(source_translations[0]['translated_text'], "Hello, World!")
    
    def test_complete_workflow(self):
        """测试完整的工作流程"""
        # 1. 创建会议
        meeting_id = self.db.create_meeting(
            title="完整流程测试会议",
            description="测试完整的数据库操作流程"
        )
        
        # 2. 上传音频文件
        audio_id = self.db.save_audio_file(
            meeting_id=meeting_id,
            file_name="workflow_audio.wav",
            file_path="/path/to/workflow_audio.wav",
            file_size=2048000,
            duration=180.0,
            format="wav",
            sample_rate=16000,
            channels=1
        )
        
        # 3. 保存说话人信息
        self.db.save_speaker(
            speaker_id="workflow_speaker",
            name="工作流测试用户",
            email="workflow_speaker@example.com"
        )
        
        # 4. 保存传统语音识别结果
        speech_id = self.db.save_speech_result(
            meeting_id=meeting_id,
            speaker_id="workflow_speaker",
            speaker_name="工作流测试用户",
            text_content="这是完整流程测试的语音内容",
            confidence=0.98
        )
        
        # 5. 保存语音识别模式结果
        mode_id1 = self.db.save_speech_recognition_mode(
            meeting_id=meeting_id,
            audio_file_id=audio_id,
            mode_type="speaker_diarization",
            text_content="工作流测试用户：这是完整流程测试的语音内容",
            confidence=0.96
        )
        
        mode_id2 = self.db.save_speech_recognition_mode(
            meeting_id=meeting_id,
            audio_file_id=audio_id,
            mode_type="no_speaker_diarization",
            text_content="这是完整流程测试的语音内容",
            confidence=0.94
        )
        
        # 6. 保存传统翻译结果
        translation_id = self.db.save_translation_result(
            speech_result_id=speech_id,
            original_text="这是完整流程测试的语音内容",
            translated_text="This is the voice content of the complete process test",
            source_language="zh",
            target_language="en",
            confidence=0.95
        )
        
        # 7. 保存会议翻译内容
        meeting_trans_id1 = self.db.save_meeting_translation(
            meeting_id=meeting_id,
            source_type="mode_result",
            source_id=mode_id1,
            original_text="工作流测试用户：这是完整流程测试的语音内容",
            translated_text="Workflow Test User: This is the voice content of the complete process test",
            source_language="zh",
            target_language="en",
            confidence=0.93
        )
        
        # 8. 保存会议纪要
        minutes_id = self.db.save_meeting_minutes(
            meeting_id=meeting_id,
            summary="完整流程测试会议总结",
            key_points=["测试数据库功能", "验证工作流程", "测试新增功能"],
            action_items=["完善测试用例", "优化性能", "添加音频文件管理"],
            decisions=["采用SQLite作为数据库", "支持多种识别模式"],
            participants=["工作流测试用户"]
        )
        
        # 9. 结束会议
        self.db.end_meeting(meeting_id)
        
        # 10. 验证所有数据
        meeting = self.db.get_meeting(meeting_id)
        speaker = self.db.get_speaker("workflow_speaker")
        audio_files = self.db.get_meeting_audio_files(meeting_id)
        speech_results = self.db.get_meeting_speech_results(meeting_id)
        mode_results = self.db.get_speech_recognition_modes(meeting_id)
        meeting_translations = self.db.get_meeting_translations(meeting_id)
        minutes = self.db.get_meeting_minutes(meeting_id)
        
        # 断言验证
        self.assertIsNotNone(meeting)
        self.assertIsNotNone(speaker)
        self.assertEqual(len(audio_files), 1)
        self.assertEqual(len(speech_results), 1)
        self.assertEqual(len(mode_results), 2)
        self.assertEqual(len(meeting_translations), 1)
        self.assertIsNotNone(minutes)
        self.assertEqual(meeting['status'], 'completed')
        
        # 11. 获取数据库信息
        info = self.db.get_database_info()
        self.assertGreater(info['database_size'], 0)
        
        # 验证各表都有数据
        table_data = {table['name']: table['row_count'] for table in info['tables']}
        self.assertGreater(table_data.get('meetings', 0), 0)
        self.assertGreater(table_data.get('speakers', 0), 0)
        self.assertGreater(table_data.get('meeting_audio_files', 0), 0)
        self.assertGreater(table_data.get('speech_recognition_results', 0), 0)
        self.assertGreater(table_data.get('speech_recognition_modes', 0), 0)
        self.assertGreater(table_data.get('meeting_translations', 0), 0)
        self.assertGreater(table_data.get('translation_results', 0), 0)
        self.assertGreater(table_data.get('meeting_minutes', 0), 0)


if __name__ == '__main__':
    # 设置日志级别
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 运行测试
    unittest.main(verbosity=2)