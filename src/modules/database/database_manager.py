#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite数据库管理模块

提供SQLite数据库的连接、表创建、数据操作等功能。
支持会议记录、用户管理、语音识别结果存储等业务需求。

作者: AIM ZST Team
版本: 1.0.0
创建时间: 2025年
"""

import sqlite3
import os
import logging
import json
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

# 配置日志
logger = logging.getLogger(__name__)


def _path_is_within(abs_path: str, directory: str) -> bool:
    abs_directory = os.path.abspath(directory)
    return abs_path == abs_directory or abs_path.startswith(abs_directory + os.sep)


class DatabaseError(Exception):
    """数据库操作异常类"""
    pass


class DatabaseManager:
    """
    SQLite数据库管理器
    
    提供数据库连接管理、表创建、数据操作等功能。
    支持自动创建数据库文件和表结构。
    """
    
    def __init__(self, db_path: str = "data/wyl_asr.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"创建数据库目录: {db_dir}")
    
    def _init_database(self):
        """初始化数据库和表结构"""
        try:
            with self.get_connection() as conn:
                self._create_tables(conn)
            logger.info(f"数据库初始化完成: {self.db_path}")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise DatabaseError(f"数据库初始化失败: {e}")
    
    def _create_tables(self, conn: sqlite3.Connection):
        """创建数据库表结构"""
        cursor = conn.cursor()
        
        # 会议表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        
        # 语音识别结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS speech_recognition_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                speaker_id TEXT,
                speaker_name TEXT,
                text_content TEXT NOT NULL,
                confidence REAL,
                start_time REAL,
                end_time REAL,
                language TEXT DEFAULT 'zh',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
        """)
        
        # 翻译结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                speech_result_id INTEGER,
                original_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (speech_result_id) REFERENCES speech_recognition_results (id)
            )
        """)
        
        # 说话人信息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS speakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                speaker_id TEXT UNIQUE NOT NULL,
                name TEXT,
                email TEXT,
                voice_features TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # 会议音频文件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_audio_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                duration REAL,
                format TEXT,
                sample_rate INTEGER,
                channels INTEGER,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
        """)
        
        # 语音识别模式表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS speech_recognition_modes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                audio_file_id INTEGER,
                mode_type TEXT NOT NULL,  -- 'speaker_diarization' 或 'no_speaker_diarization'
                text_content TEXT NOT NULL,
                confidence REAL,
                start_time REAL,
                end_time REAL,
                language TEXT DEFAULT 'zh',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id),
                FOREIGN KEY (audio_file_id) REFERENCES meeting_audio_files (id)
            )
        """)
        
        # 会议翻译内容表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                source_type TEXT NOT NULL,  -- 'speech_result' 或 'mode_result'
                source_id INTEGER,  -- 对应speech_recognition_results.id或speech_recognition_modes.id
                original_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
        """)
        
        # 会议纪要表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_minutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                summary TEXT,
                key_points TEXT,
                action_items TEXT,
                decisions TEXT,
                participants TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
        """)

        # 会议纪要版本表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_minutes_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                summary TEXT NOT NULL,
                instruction TEXT,
                source_version_id INTEGER,
                is_current BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id),
                FOREIGN KEY (source_version_id) REFERENCES meeting_minutes_versions (id),
                UNIQUE(meeting_id, version)
            )
        """)
        
        # 会议文档文件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                document_type TEXT NOT NULL, -- 'transcription', 'minutes', 'audio_info'
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
        """)

        # 上传音视频识别任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_audio_tasks (
                task_id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                saved_file_name TEXT NOT NULL,
                saved_path TEXT NOT NULL,
                recognition_file_name TEXT,
                recognition_path TEXT,
                language TEXT DEFAULT 'zh',
                enable_speaker_diarization BOOLEAN DEFAULT 1,
                enable_voiceprint_matching BOOLEAN DEFAULT 0,
                enable_translation BOOLEAN DEFAULT 0,
                speaker_top_k INTEGER DEFAULT 3,
                expected_speakers INTEGER,
                min_speakers INTEGER,
                max_speakers INTEGER,
                hotword_text TEXT,
                status TEXT DEFAULT 'queued',
                progress INTEGER DEFAULT 0,
                stage TEXT,
                error TEXT,
                result_json TEXT,
                media_info_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # 上传识别转写段表，便于说话人整理和片段试听
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_audio_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                meeting_id INTEGER,
                segment_index INTEGER NOT NULL,
                speaker TEXT,
                speaker_type TEXT,
                speaker_confidence REAL,
                text TEXT NOT NULL,
                translation TEXT,
                start_ms INTEGER,
                end_ms INTEGER,
                mode TEXT DEFAULT 'uploaded-audio',
                speaker_result_json TEXT,
                FOREIGN KEY (task_id) REFERENCES uploaded_audio_tasks (task_id),
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
        """)

        uploaded_segment_cols = {
            row[1] for row in cursor.execute("PRAGMA table_info(uploaded_audio_segments)").fetchall()
        }
        if "meeting_id" not in uploaded_segment_cols:
            cursor.execute("ALTER TABLE uploaded_audio_segments ADD COLUMN meeting_id INTEGER")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_uploaded_audio_segments_meeting_id "
            "ON uploaded_audio_segments(meeting_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_uploaded_audio_segments_task_id "
            "ON uploaded_audio_segments(task_id)"
        )

        uploaded_task_cols = {
            row[1] for row in cursor.execute("PRAGMA table_info(uploaded_audio_tasks)").fetchall()
        }
        upload_task_migrations = {
            "recognition_file_name": "TEXT",
            "recognition_path": "TEXT",
            "enable_voiceprint_matching": "BOOLEAN DEFAULT 0",
            "expected_speakers": "INTEGER",
            "min_speakers": "INTEGER",
            "max_speakers": "INTEGER",
            "hotword_text": "TEXT",
            "media_info_json": "TEXT",
            "completed_at": "TIMESTAMP",
        }
        for column, definition in upload_task_migrations.items():
            if column not in uploaded_task_cols:
                cursor.execute(f"ALTER TABLE uploaded_audio_tasks ADD COLUMN {column} {definition}")
        
        # 系统配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        logger.info("数据库表结构创建完成")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise DatabaseError(f"数据库操作失败: {e}")
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """执行查询语句"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """执行更新语句，返回影响的行数"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """执行插入语句，返回新插入记录的ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
    
    # 会议管理方法
    def create_meeting(self, title: str, description: str = None) -> int:
        """创建会议"""
        query = "INSERT INTO meetings (title, description, start_time) VALUES (?, ?, ?)"
        return self.execute_insert(query, (title, description, datetime.now()))
    
    def get_meeting(self, meeting_id: int) -> Optional[sqlite3.Row]:
        """获取会议信息"""
        query = "SELECT * FROM meetings WHERE id = ?"
        results = self.execute_query(query, (meeting_id,))
        return results[0] if results else None
    
    def get_all_meetings(self) -> List[sqlite3.Row]:
        """获取所有会议列表"""
        query = "SELECT * FROM meetings ORDER BY start_time DESC"
        return self.execute_query(query)
    
    def end_meeting(self, meeting_id: int) -> int:
        """结束会议"""
        query = "UPDATE meetings SET end_time = ?, status = 'completed' WHERE id = ?"
        return self.execute_update(query, (datetime.now(), meeting_id))
    
    def delete_meeting(self, meeting_id: int) -> int:
        """删除会议及其相关数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            document_rows = cursor.execute(
                "SELECT file_path FROM meeting_documents WHERE meeting_id = ?",
                (meeting_id,)
            ).fetchall()
            documents_dir = os.path.abspath(os.path.join(os.getcwd(), 'data', 'documents'))
            for document in document_rows:
                file_path = document['file_path']
                abs_file_path = os.path.abspath(file_path)
                if not _path_is_within(abs_file_path, documents_dir):
                    logger.warning(f"跳过会议文档文件删除，路径不在文档目录内: {file_path}")
                    continue
                if os.path.isfile(abs_file_path):
                    os.remove(abs_file_path)
                    logger.info(f"已删除会议文档文件: {abs_file_path}")
            
            # 删除相关的语音识别结果
            cursor.execute("DELETE FROM speech_recognition_results WHERE meeting_id = ?", (meeting_id,))
            
            # 删除相关的音频文件记录
            cursor.execute("DELETE FROM meeting_audio_files WHERE meeting_id = ?", (meeting_id,))
            
            # 删除相关的语音识别模式
            cursor.execute("DELETE FROM speech_recognition_modes WHERE meeting_id = ?", (meeting_id,))
            
            # 删除相关的翻译内容
            cursor.execute("DELETE FROM meeting_translations WHERE meeting_id = ?", (meeting_id,))
            
            # 删除相关的会议纪要
            cursor.execute("DELETE FROM meeting_minutes WHERE meeting_id = ?", (meeting_id,))
            cursor.execute("DELETE FROM meeting_minutes_versions WHERE meeting_id = ?", (meeting_id,))

            # 删除已明确绑定到该会议的上传识别片段
            cursor.execute("DELETE FROM uploaded_audio_segments WHERE meeting_id = ?", (meeting_id,))

            # 删除相关的会议文档记录
            cursor.execute("DELETE FROM meeting_documents WHERE meeting_id = ?", (meeting_id,))
            
            # 最后删除会议本身
            cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
            deleted_count = cursor.rowcount
            
            conn.commit()
            return deleted_count
    
    # 语音识别结果管理
    def save_speech_result(self, meeting_id: int, speaker_id: str, 
                          speaker_name: str, text_content: str, 
                          confidence: float = None, start_time: float = None, 
                          end_time: float = None, language: str = 'zh') -> int:
        """保存语音识别结果"""
        query = """
            INSERT INTO speech_recognition_results 
            (meeting_id, speaker_id, speaker_name, text_content, confidence, 
             start_time, end_time, language) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_insert(query, (meeting_id, speaker_id, speaker_name, 
                                         text_content, confidence, start_time, 
                                         end_time, language))
    
    def get_meeting_speech_results(self, meeting_id: int) -> List[sqlite3.Row]:
        """获取会议的所有语音识别结果"""
        query = """
            SELECT * FROM speech_recognition_results 
            WHERE meeting_id = ? 
            ORDER BY created_at ASC
        """
        return self.execute_query(query, (meeting_id,))
    
    # 翻译结果管理
    def save_translation_result(self, speech_result_id: int, original_text: str,
                               translated_text: str, source_language: str,
                               target_language: str, confidence: float = None) -> int:
        """保存翻译结果"""
        query = """
            INSERT INTO translation_results 
            (speech_result_id, original_text, translated_text, 
             source_language, target_language, confidence) 
            VALUES (?, ?, ?, ?, ?, ?)
        """
        return self.execute_insert(query, (speech_result_id, original_text, 
                                         translated_text, source_language, 
                                         target_language, confidence))
    
    # 说话人管理
    def save_speaker(self, speaker_id: str, name: str = None, 
                    email: str = None, voice_features: dict = None) -> int:
        """保存说话人信息"""
        features_json = json.dumps(voice_features) if voice_features else None
        query = """
            INSERT OR REPLACE INTO speakers 
            (speaker_id, name, email, voice_features, updated_at) 
            VALUES (?, ?, ?, ?, ?)
        """
        return self.execute_insert(query, (speaker_id, name, email, 
                                         features_json, datetime.now()))
    
    def get_speaker(self, speaker_id: str) -> Optional[sqlite3.Row]:
        """获取说话人信息"""
        query = "SELECT * FROM speakers WHERE speaker_id = ?"
        results = self.execute_query(query, (speaker_id,))
        return results[0] if results else None
    
    # 会议音频文件管理
    def save_audio_file(self, meeting_id: int, file_name: str, file_path: str,
                       file_size: int = None, duration: float = None,
                       format: str = None, sample_rate: int = None,
                       channels: int = None) -> int:
        """保存会议音频文件信息"""
        query = """
            INSERT INTO meeting_audio_files 
            (meeting_id, file_name, file_path, file_size, duration, 
             format, sample_rate, channels) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_insert(query, (meeting_id, file_name, file_path,
                                         file_size, duration, format,
                                         sample_rate, channels))
    
    def get_meeting_audio_files(self, meeting_id: int) -> List[sqlite3.Row]:
        """获取会议的所有音频文件"""
        query = """
            SELECT * FROM meeting_audio_files 
            WHERE meeting_id = ? AND status = 'active'
            ORDER BY upload_time ASC
        """
        return self.execute_query(query, (meeting_id,))
    
    def get_audio_file(self, audio_file_id: int) -> Optional[sqlite3.Row]:
        """根据ID获取音频文件信息"""
        query = "SELECT * FROM meeting_audio_files WHERE id = ?"
        results = self.execute_query(query, (audio_file_id,))
        return results[0] if results else None
    
    def delete_audio_file(self, audio_file_id: int) -> int:
        """删除音频文件（软删除）"""
        query = "UPDATE meeting_audio_files SET status = 'deleted' WHERE id = ?"
        return self.execute_update(query, (audio_file_id,))
    
    # 语音识别模式管理
    def save_speech_recognition_mode(self, meeting_id: int, audio_file_id: int,
                                   mode_type: str, text_content: str,
                                   confidence: float = None, start_time: float = None,
                                   end_time: float = None, language: str = 'zh') -> int:
        """保存语音识别模式结果
        
        Args:
            mode_type: 'speaker_diarization' 或 'no_speaker_diarization'
        """
        query = """
            INSERT INTO speech_recognition_modes 
            (meeting_id, audio_file_id, mode_type, text_content, confidence, 
             start_time, end_time, language) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_insert(query, (meeting_id, audio_file_id, mode_type,
                                         text_content, confidence, start_time,
                                         end_time, language))
    
    def get_speech_recognition_modes(self, meeting_id: int, 
                                   mode_type: str = None) -> List[sqlite3.Row]:
        """获取会议的语音识别模式结果"""
        if mode_type:
            query = """
                SELECT * FROM speech_recognition_modes 
                WHERE meeting_id = ? AND mode_type = ?
                ORDER BY created_at ASC
            """
            return self.execute_query(query, (meeting_id, mode_type))
        else:
            query = """
                SELECT * FROM speech_recognition_modes 
                WHERE meeting_id = ?
                ORDER BY created_at ASC
            """
            return self.execute_query(query, (meeting_id,))
    
    def get_audio_file_recognition_modes(self, audio_file_id: int) -> List[sqlite3.Row]:
        """获取音频文件的语音识别模式结果"""
        query = """
            SELECT * FROM speech_recognition_modes 
            WHERE audio_file_id = ?
            ORDER BY created_at ASC
        """
        return self.execute_query(query, (audio_file_id,))
    
    # 会议翻译内容管理
    def save_meeting_translation(self, meeting_id: int, source_type: str,
                               source_id: int, original_text: str,
                               translated_text: str, source_language: str,
                               target_language: str, confidence: float = None) -> int:
        """保存会议翻译内容
        
        Args:
            source_type: 'speech_result' 或 'mode_result'
            source_id: 对应的源记录ID
        """
        query = """
            INSERT INTO meeting_translations 
            (meeting_id, source_type, source_id, original_text, translated_text, 
             source_language, target_language, confidence) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_insert(query, (meeting_id, source_type, source_id,
                                         original_text, translated_text,
                                         source_language, target_language,
                                         confidence))
    
    def get_meeting_translations(self, meeting_id: int, 
                               source_type: str = None) -> List[sqlite3.Row]:
        """获取会议的翻译内容"""
        if source_type:
            query = """
                SELECT * FROM meeting_translations 
                WHERE meeting_id = ? AND source_type = ?
                ORDER BY created_at ASC
            """
            return self.execute_query(query, (meeting_id, source_type))
        else:
            query = """
                SELECT * FROM meeting_translations 
                WHERE meeting_id = ?
                ORDER BY created_at ASC
            """
            return self.execute_query(query, (meeting_id,))
    
    def get_translation_by_source(self, source_type: str, source_id: int) -> List[sqlite3.Row]:
        """根据源记录获取翻译内容"""
        query = """
            SELECT * FROM meeting_translations 
            WHERE source_type = ? AND source_id = ?
            ORDER BY created_at ASC
        """
        return self.execute_query(query, (source_type, source_id))
    
    # 会议纪要管理
    def save_meeting_minutes(self, meeting_id: int, summary: str = None,
                           key_points: List[str] = None, 
                           action_items: List[str] = None,
                           decisions: List[str] = None,
                           participants: List[str] = None,
                           create_version: bool = True) -> int:
        """保存会议纪要"""
        query = """
            INSERT OR REPLACE INTO meeting_minutes 
            (meeting_id, summary, key_points, action_items, decisions, participants) 
            VALUES (?, ?, ?, ?, ?, ?)
        """
        minutes_id = self.execute_insert(query, (
            meeting_id, summary,
            json.dumps(key_points) if key_points else None,
            json.dumps(action_items) if action_items else None,
            json.dumps(decisions) if decisions else None,
            json.dumps(participants) if participants else None
        ))
        if create_version and summary and summary.strip():
            self.save_meeting_minutes_version(
                meeting_id=meeting_id,
                summary=summary,
                instruction="原始纪要"
            )
        return minutes_id
    
    def get_meeting_minutes(self, meeting_id: int) -> Optional[sqlite3.Row]:
        """获取会议纪要"""
        query = "SELECT * FROM meeting_minutes WHERE meeting_id = ? ORDER BY created_at DESC, id DESC"
        results = self.execute_query(query, (meeting_id,))
        return results[0] if results else None

    def save_meeting_minutes_version(self, meeting_id: int, summary: str,
                                     instruction: str = None,
                                     source_version_id: int = None,
                                     is_current: bool = True) -> int:
        """保存会议纪要版本"""
        clean_summary = (summary or '').strip()
        if not clean_summary:
            raise DatabaseError("会议纪要版本内容不能为空")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if is_current:
                cursor.execute(
                    "UPDATE meeting_minutes_versions SET is_current = 0 WHERE meeting_id = ?",
                    (meeting_id,)
                )
            cursor.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM meeting_minutes_versions WHERE meeting_id = ?",
                (meeting_id,)
            )
            version = cursor.fetchone()["next_version"]
            cursor.execute(
                """
                INSERT INTO meeting_minutes_versions
                (meeting_id, version, summary, instruction, source_version_id, is_current)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    meeting_id,
                    version,
                    clean_summary,
                    instruction,
                    source_version_id,
                    1 if is_current else 0
                )
            )
            conn.commit()
            return cursor.lastrowid

    def ensure_meeting_minutes_version(self, meeting_id: int, summary: str,
                                       instruction: str = "原始纪要") -> Optional[int]:
        """当会议没有纪要版本时，用已有纪要补一个初始版本"""
        existing = self.get_meeting_minutes_versions(meeting_id)
        if existing:
            return existing[-1]["id"]
        if not summary or not summary.strip():
            return None
        return self.save_meeting_minutes_version(
            meeting_id=meeting_id,
            summary=summary,
            instruction=instruction,
            is_current=True
        )

    def get_meeting_minutes_versions(self, meeting_id: int) -> List[sqlite3.Row]:
        """获取会议纪要版本列表"""
        query = """
            SELECT * FROM meeting_minutes_versions
            WHERE meeting_id = ?
            ORDER BY version DESC
        """
        return self.execute_query(query, (meeting_id,))

    def get_current_meeting_minutes_version(self, meeting_id: int) -> Optional[sqlite3.Row]:
        """获取当前会议纪要版本"""
        query = """
            SELECT * FROM meeting_minutes_versions
            WHERE meeting_id = ?
            ORDER BY is_current DESC, version DESC
            LIMIT 1
        """
        results = self.execute_query(query, (meeting_id,))
        return results[0] if results else None

    def get_meeting_minutes_version(self, version_id: int) -> Optional[sqlite3.Row]:
        """按ID获取会议纪要版本"""
        query = "SELECT * FROM meeting_minutes_versions WHERE id = ?"
        results = self.execute_query(query, (version_id,))
        return results[0] if results else None
    
    # 会议文档管理
    def save_meeting_document(self, meeting_id: int, document_type: str, 
                            file_name: str, file_path: str, file_size: int = None) -> int:
        """保存会议文档文件信息"""
        query = """
            INSERT OR REPLACE INTO meeting_documents 
            (meeting_id, document_type, file_name, file_path, file_size, updated_at) 
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        return self.execute_insert(query, (meeting_id, document_type, file_name, file_path, file_size))
    
    def get_meeting_documents(self, meeting_id: int, document_type: str = None) -> List[sqlite3.Row]:
        """获取会议文档列表"""
        if document_type:
            query = "SELECT * FROM meeting_documents WHERE meeting_id = ? AND document_type = ? ORDER BY created_at DESC"
            return self.execute_query(query, (meeting_id, document_type))
        else:
            query = "SELECT * FROM meeting_documents WHERE meeting_id = ? ORDER BY created_at DESC"
            return self.execute_query(query, (meeting_id,))
    
    def get_all_meeting_documents(self, document_type: str = None) -> List[sqlite3.Row]:
        """获取所有会议文档"""
        if document_type:
            query = """
                SELECT md.*, m.title as meeting_title, m.start_time as meeting_start_time
                FROM meeting_documents md
                JOIN meetings m ON md.meeting_id = m.id
                WHERE md.document_type = ?
                ORDER BY md.created_at DESC
            """
            return self.execute_query(query, (document_type,))
        else:
            query = """
                SELECT md.*, m.title as meeting_title, m.start_time as meeting_start_time
                FROM meeting_documents md
                JOIN meetings m ON md.meeting_id = m.id
                ORDER BY md.created_at DESC
            """
            return self.execute_query(query)
    
    def delete_meeting_document(self, document_id: int) -> int:
        """删除会议文档记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM meeting_documents WHERE id = ?", (document_id,))
            conn.commit()
            return cursor.rowcount
    
    def get_meeting_document_by_path(self, file_path: str) -> Optional[sqlite3.Row]:
        """根据文件路径获取文档记录"""
        query = "SELECT * FROM meeting_documents WHERE file_path = ?"
        results = self.execute_query(query, (file_path,))
        return results[0] if results else None
    
    def get_meeting_document_by_id(self, document_id: int) -> Optional[sqlite3.Row]:
        """根据文档ID获取文档记录"""
        query = "SELECT * FROM meeting_documents WHERE id = ?"
        results = self.execute_query(query, (document_id,))
        return results[0] if results else None

    def update_meeting_document_file_size(self, document_id: int, file_size: int) -> int:
        """更新会议文档文件大小和更新时间"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE meeting_documents
                SET file_size = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (file_size, document_id)
            )
            conn.commit()
            return cursor.rowcount
    
    # 系统配置管理
    def set_config(self, key: str, value: str, description: str = None) -> int:
        """设置系统配置"""
        query = """
            INSERT OR REPLACE INTO system_config 
            (config_key, config_value, description, updated_at) 
            VALUES (?, ?, ?, ?)
        """
        return self.execute_insert(query, (key, value, description, datetime.now()))
    
    def get_config(self, key: str) -> Optional[str]:
        """获取系统配置"""
        query = "SELECT config_value FROM system_config WHERE config_key = ?"
        results = self.execute_query(query, (key,))
        return results[0]['config_value'] if results else None
    
    # 数据库维护方法
    def vacuum(self):
        """优化数据库"""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
            logger.info("数据库优化完成")
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        info = {
            'database_path': self.db_path,
            'database_size': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
            'tables': []
        }
        
        query = "SELECT name FROM sqlite_master WHERE type='table'"
        tables = self.execute_query(query)
        
        for table in tables:
            table_name = table['name']
            count_query = f"SELECT COUNT(*) as count FROM {table_name}"
            count_result = self.execute_query(count_query)
            info['tables'].append({
                'name': table_name,
                'row_count': count_result[0]['count']
            })
        
        return info


# 全局数据库管理器实例
_db_manager = None
_db_manager_lock = threading.Lock()


def get_database_manager(db_path: str = "data/wyl_asr.db") -> DatabaseManager:
    """获取数据库管理器实例（单例模式）"""
    global _db_manager
    if _db_manager is None:
        with _db_manager_lock:
            if _db_manager is None:
                _db_manager = DatabaseManager(db_path)
    return _db_manager


def init_database(db_path: str = "data/wyl_asr.db") -> DatabaseManager:
    """初始化数据库"""
    return get_database_manager(db_path)


if __name__ == "__main__":
    # 测试代码
    try:
        db = DatabaseManager("test.db")
        
        # 创建测试会议
        meeting_id = db.create_meeting("测试会议", "这是一个测试会议")
        print(f"创建会议ID: {meeting_id}")
        
        # 保存语音识别结果
        speech_id = db.save_speech_result(
            meeting_id, "speaker_001", "张三", 
            "这是一段测试语音识别结果", 0.95
        )
        print(f"保存语音识别结果ID: {speech_id}")
        
        # 获取数据库信息
        info = db.get_database_info()
        print(f"数据库信息: {info}")
        
        print("数据库测试完成")
        
    except Exception as e:
        print(f"测试失败: {e}")
    finally:
        # 清理测试文件
        if os.path.exists("test.db"):
            os.remove("test.db")
