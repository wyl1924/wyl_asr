#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库API接口模块

提供RESTful API接口来操作数据库功能，包括：
- 会议管理API
- 音频文件管理API
- 语音识别结果API
- 翻译内容API
- 会议纪要API
- 说话人管理API
- 系统配置API

作者: WYL ASR Team
版本: 1.0.0
创建时间: 2024年
"""

import json
import logging
import mimetypes
import re
import time
import uuid
import gc
import asyncio
import shutil
import zipfile
import csv
import functools
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO, StringIO
from threading import Lock, Thread
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlencode, urlparse
from xml.sax.saxutils import escape as xml_escape
import yaml
from flask import Flask, request, jsonify, Response, send_file, send_from_directory, after_this_request
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError, RequestEntityTooLarge
from werkzeug.utils import secure_filename
import os
import tempfile
import requests

from ..database.database_manager import get_database_manager, DatabaseError
from ..core.document_segmentation_service import (
    segment, segment_batch, get_status as get_segmentation_status,
    init_document_segmentation, DocumentSegmentationError
)
from ...api.audio_stats_api import audio_stats_bp
from ...api.audio_devices_api import get_audio_devices
from ...api.subtitle_settings import subtitle_settings_bp, init_subtitle_settings_api

# 配置日志
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 支持中文JSON响应

# Flask应用配置
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB - 支持大型会议音视频上传
app.config['UPLOAD_FOLDER'] = 'data/uploads'
app.config['JSON_SORT_KEYS'] = False

HOTWORDS_DATA_DIR = 'data'
HOTWORDS_TXT_PATH = os.path.join(HOTWORDS_DATA_DIR, 'hotwords.txt')
HOTWORDS_ASSET_PATH = os.path.join(HOTWORDS_DATA_DIR, 'hotwords_assets.json')
UI_DIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../ui/dist"))
HOTWORDS_DEFAULT_WEIGHT = 90
HOTWORDS_DEFAULT_CATEGORY = '通用'
HOTWORDS_DEFAULT_SOURCE = '手动'
HOTWORDS_LEGACY_SOURCE = '旧版文件'

ALLOWED_RECOGNITION_AUDIO_EXTENSIONS = {
    '.wav', '.mp3', '.flac', '.m4a', '.aac', '.ogg', '.webm',
    '.mp4', '.mov', '.mkv', '.avi', '.wmv', '.m4v', '.amr',
    '.opus', '.wma'
}
UPLOAD_ASR_DEFAULT_MAX_MB = 2048
UPLOAD_ASR_GPU_MEMORY_MULTIPLIER = 4.0
UPLOAD_SPEAKER_REGISTRATION_MAX_MS = 15000
UPLOAD_SPEAKER_CLUSTER_WINDOW_MS = 12000
UPLOAD_SPEAKER_CLUSTER_MIN_AUDIO_MS = 30000
UPLOAD_SPEAKER_SEGMENT_MIN_MS = 600
UPLOAD_SPEAKER_SEGMENT_TARGET_MS = 7000
UPLOAD_SPEAKER_SEGMENT_MAX_MS = 10000
UPLOAD_SPEAKER_SEGMENT_PADDING_MS = 180
UPLOAD_SPEAKER_MAX_VAD_SEGMENTS = 120
UPLOAD_INTERNAL_SPEAKER_CPU_MAX_SECONDS = 0
UPLOAD_MODELSCOPE_DIARIZATION_MODEL_DIR = "speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx"
UPLOAD_VOICEPRINT_MATCH_SAMPLE_LIMIT = 8
UPLOAD_VOICEPRINT_MIN_SAMPLE_MS = 2000
UPLOAD_VOICEPRINT_MAX_SAMPLE_MS = 14000
UPLOAD_VOICEPRINT_MATCH_MARGIN = 0.08
UPLOAD_VOICEPRINT_MATCH_MIN_HITS = 2
UPLOAD_TASK_MAX_WORKERS = int(os.getenv('UPLOAD_ASR_TASK_MAX_WORKERS', '2'))
UPLOAD_RECOVER_PENDING_TASKS = os.getenv('UPLOAD_RECOVER_PENDING_TASKS', '').lower() in {'1', 'true', 'yes'}
UPLOAD_DISFLUENCY_FILLERS = (
    "嗯", "呃", "啊", "哦", "额", "唔", "哎", "诶"
)
UPLOAD_DISFLUENCY_PREFIX_PHRASES = (
    "然后那个", "然后这个", "那个就是", "这个就是",
    "嗯然后", "嗯那个", "嗯这个", "呃那个", "呃这个"
)

def _get_cors_origins() -> Any:
    raw_origins = os.getenv('WYL_ASR_CORS_ORIGINS', '*')
    origins = [origin.strip() for origin in raw_origins.split(',') if origin.strip()]
    if not origins or origins == ['*']:
        return '*'
    return origins


cors_origins = _get_cors_origins()

# 启用CORS支持。默认不携带凭据，生产环境可通过 WYL_ASR_CORS_ORIGINS 配置具体域名。
CORS(app,
     origins=cors_origins,
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'X-API-Key'],
     expose_headers=['Content-Disposition'],
     supports_credentials=cors_origins != '*')

# 注册API蓝图
app.register_blueprint(audio_stats_bp)
app.register_blueprint(subtitle_settings_bp)

# 获取数据库管理器实例
db = get_database_manager()

# LLM任务队列：本地30B模型容易被并发请求打爆，默认串行处理
LLM_TASK_MAX_WORKERS = int(os.getenv('LLM_TASK_MAX_WORKERS', '1'))
LLM_TASK_TIMEOUT = int(os.getenv('LLM_TASK_TIMEOUT', '600'))
llm_task_executor = ThreadPoolExecutor(max_workers=max(1, LLM_TASK_MAX_WORKERS))
llm_tasks: Dict[str, Dict[str, Any]] = {}
llm_tasks_lock = Lock()
summary_tasks: Dict[str, Dict[str, Any]] = {}
summary_tasks_lock = Lock()
upload_asr_lock = Lock()
upload_vad_lock = Lock()
upload_diarization_lock = Lock()
hotword_asset_lock = Lock()
upload_vad_model = None
upload_diarization_pipeline = None
upload_diarization_pipeline_path = None
upload_task_executor = ThreadPoolExecutor(max_workers=max(1, UPLOAD_TASK_MAX_WORKERS))
upload_task_futures: Dict[str, Any] = {}
upload_task_futures_lock = Lock()

SUMMARY_MODEL_CONFIG = {
    'max_context_tokens': 128000,
    'max_output_tokens': 64000,
    'min_output_tokens': 8192,
    'chinese_char_to_token_ratio': 0.8,
    'english_word_to_token_ratio': 1.3,
    'direct_max_chars': 50000,
    'segment_max_chars': 35000,
    'segment_max_output_tokens': 8192,
    'merge_max_output_tokens': 12000
}

SUMMARY_TEMPLATE_STANDARD = 'standard'
SUMMARY_TEMPLATE_PROJECT_REVIEW = 'project_review'
SUMMARY_TEMPLATE_IDS = {SUMMARY_TEMPLATE_STANDARD, SUMMARY_TEMPLATE_PROJECT_REVIEW}

DEFAULT_LLM_CONFIG = {
    'activeServiceType': 'xinference',
    'services': {
        'ollama': {
            'endpoint': 'https://10.1.0.27/ollama/api/chat',
            'model': 'qwen3:30b-a3b-q4_K_M'
        },
        'xinference': {
            'endpoint': 'http://10.1.0.26:9997/v1/chat/completions',
            'model': 'DeepSeek-R1-671B-1'
        },
        'vllm': {
            'endpoint': 'http://localhost:8000/v1/chat/completions',
            'model': 'meta-llama/Llama-2-7b-chat-hf'
        },
        'sglang': {
            'endpoint': 'http://localhost:30000/v1/chat/completions',
            'model': 'meta-llama/Llama-2-7b-chat-hf'
        }
    }
}

LEGACY_DEFAULT_LLM_CONFIG = {
    'activeServiceType': 'ollama',
    'services': {
        'ollama': {
            'endpoint': 'https://10.1.0.27/ollama/api/chat',
            'model': 'qwen3:30b-a3b-q4_K_M'
        },
        'xinference': {
            'endpoint': 'http://localhost:9997/v1/chat/completions',
            'model': 'qwen-chat'
        },
        'vllm': {
            'endpoint': 'http://localhost:8000/v1/chat/completions',
            'model': 'meta-llama/Llama-2-7b-chat-hf'
        },
        'sglang': {
            'endpoint': 'http://localhost:30000/v1/chat/completions',
            'model': 'meta-llama/Llama-2-7b-chat-hf'
        }
    }
}


class APIError(Exception):
    """API异常类"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class UploadTaskCancelled(Exception):
    """上传识别任务已取消。"""


def _build_upload_log_context(
    task_id: Optional[str] = None,
    original_filename: Optional[str] = None,
    saved_path: Optional[str] = None,
) -> str:
    parts = []
    if task_id:
        parts.append(f"task_id={task_id}")
    if original_filename:
        parts.append(f"file={original_filename}")
    if saved_path:
        parts.append(f"saved_file={os.path.basename(saved_path)}")
    return ", ".join(parts) if parts else "upload"


def create_response(data: Any = None, message: str = "success",
                   status_code: int = 200) -> Response:
    """创建统一的API响应格式"""
    response_data = {
        "code": status_code,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    return jsonify(response_data), status_code


def _extract_bearer_token(value: Optional[str]) -> str:
    if not value:
        return ''
    prefix = 'Bearer '
    return value[len(prefix):].strip() if value.startswith(prefix) else ''


@app.before_request
def require_api_key_if_configured():
    """启用 WYL_ASR_API_KEY 后，所有 /api 端点都需要 X-API-Key 或 Bearer token。"""
    required_key = os.getenv('WYL_ASR_API_KEY', '').strip()
    if not required_key or request.method == 'OPTIONS' or not request.path.startswith('/api/'):
        return None

    provided_key = request.headers.get('X-API-Key', '').strip()
    if not provided_key:
        provided_key = _extract_bearer_token(request.headers.get('Authorization'))

    if provided_key != required_key:
        return create_response(None, "未授权", 401)
    return None


def handle_database_error(func):
    """数据库错误处理装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RequestEntityTooLarge as e:
            max_size = app.config.get('MAX_CONTENT_LENGTH', 500 * 1024 * 1024)
            max_mb = max_size / (1024 * 1024)
            logger.error(f"请求数据过大: {e}")
            return create_response(None, f"请求数据过大，最大允许: {max_mb:.0f}MB", 413)
        except DatabaseError as e:
            logger.error(f"数据库错误: {e}", exc_info=True)
            return create_response(None, "数据库操作失败", 500)
        except APIError as e:
            logger.error(f"API错误: {e.message}")
            return create_response(None, e.message, e.status_code)
        except Exception as e:
            logger.error(f"未知错误: {e}", exc_info=True)
            return create_response(None, "服务器内部错误", 500)

    return wrapper


def _get_request_bool(name: str, default: bool = False) -> bool:
    value = request.form.get(name)
    if value is None and request.is_json:
        payload = request.get_json(silent=True) or {}
        value = payload.get(name)
    return _coerce_bool(value, default)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _clean_asr_text(text: str, server_state) -> str:
    if not text:
        return ''

    text = re.sub(r'<\|[^|]*\|>', '', text).strip()

    try:
        from ..audio.text_processor import TextProcessor
        text_processor = TextProcessor()
        return text_processor.process_text(
            text,
            enable_rich_postprocess=True,
            enable_punctuation_cleaning=True,
            enable_hotword_boost=True
        )
    except Exception as e:
        logger.warning(f"上传音频文本后处理失败，使用原始文本: {e}")
        return text


def _run_upload_text_processor(text: str, server_state=None) -> str:
    if not text:
        return ''

    try:
        from ..audio.text_processor import TextProcessor

        hotword_map = getattr(server_state, 'hotword_map', {}) if server_state else {}
        text_processor = TextProcessor(hotword_map=hotword_map)
        return text_processor.process_text(
            text,
            enable_rich_postprocess=True,
            enable_punctuation_cleaning=True,
            enable_hotword_boost=True
        )
    except Exception as e:
        logger.warning(f"上传文本按2pass后处理失败，使用原始文本: {e}")
        return text


def _normalize_upload_disfluency_text(text: str) -> str:
    """清理上传转写里的轻量语气词和口吃式重复。"""
    if not text:
        return ''

    normalized = _clean_sentence_text(text)
    if not normalized:
        return ''

    filler_pattern = "|".join(re.escape(item) for item in UPLOAD_DISFLUENCY_FILLERS)
    prefix_pattern = "|".join(re.escape(item) for item in UPLOAD_DISFLUENCY_PREFIX_PHRASES)

    normalized = re.sub(r'(对){2,}', '对', normalized)
    normalized = re.sub(r'(嗯){2,}', '嗯', normalized)
    normalized = re.sub(r'(呃|啊|哦|额){2,}', r'\1', normalized)
    normalized = re.sub(r'([就都也又还])\1+', r'\1', normalized)
    normalized = re.sub(r'([\u4e00-\u9fff]{2,4})\1+', r'\1', normalized)

    if prefix_pattern:
        normalized = re.sub(rf'(^|[，。！？；：,.!?;:\s])(?:{prefix_pattern})[，,、\s]*', r'\1', normalized)
    normalized = re.sub(rf'(^|[，。！？；：,.!?;:\s])(?:{filler_pattern})+[，,、。\.\s]*', r'\1', normalized)
    normalized = re.sub(r'(^|[。！？!?；;])(?:就是|然后|这个|那个)[，,、。\.\s]+(?=[\u4e00-\u9fff])', r'\1', normalized)
    normalized = re.sub(r'(?<=[\u4e00-\u9fff])(?:嗯|呃|额)[，,、。\.\s]*(?=[\u4e00-\u9fff])', '', normalized)
    normalized = re.sub(r'(^|[，。！？；：,.!?;:\s])(?:然后|就是)[，,、\s]+', r'\1', normalized)

    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'([，。！？；：,.!?;:])\1+', r'\1', normalized)
    normalized = re.sub(r'^[，,、。\.\s]+', '', normalized)
    normalized = re.sub(r'\s+([，。！？；：,.!?;:])', r'\1', normalized)
    return normalized.strip()


def _postprocess_uploaded_transcript_text(
    text: str,
    server_state=None,
    enable_disfluency_cleanup: Optional[bool] = None
) -> str:
    if not text:
        return ''

    processed = _run_upload_text_processor(_clean_sentence_text(text), server_state)
    if enable_disfluency_cleanup is None:
        enable_disfluency_cleanup = _coerce_bool(os.getenv('UPLOAD_ASR_ENABLE_DISFLUENCY_CLEANUP'), True)
    if enable_disfluency_cleanup:
        processed = _normalize_upload_disfluency_text(processed)
    return processed


def _uploaded_plain_text_from_segments(segments: List[Dict[str, Any]]) -> str:
    parts = [
        (segment.get("text") or "").strip()
        for segment in segments or []
        if (segment.get("text") or "").strip()
    ]
    return "".join(parts)


def _get_env_int(name: str, default: int, min_value: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
        return max(min_value, value)
    except (TypeError, ValueError):
        logger.warning(f"环境变量 {name} 配置无效，使用默认值 {default}")
        return default


def _get_env_float(name: str, default: float, min_value: float = 0.0) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        return max(min_value, value)
    except (TypeError, ValueError):
        logger.warning(f"环境变量 {name} 配置无效，使用默认值 {default}")
        return default


def _get_upload_asr_limits() -> Tuple[int, int]:
    max_audio_mb = _get_env_int('UPLOAD_ASR_MAX_AUDIO_MB', UPLOAD_ASR_DEFAULT_MAX_MB)
    max_audio_bytes = max_audio_mb * 1024 * 1024
    return max_audio_bytes, max_audio_bytes


def _get_uploaded_audio_upload_dir() -> str:
    return os.path.join(_get_audio_dir(), 'uploads')


def _get_uploaded_recognition_audio_dir() -> str:
    return os.path.join(_get_uploaded_audio_upload_dir(), 'recognition')


def _get_audio_dir() -> str:
    return os.path.join(os.getcwd(), 'data', 'audio')


def _get_documents_dir() -> str:
    return os.path.join(os.getcwd(), 'data', 'documents')


def _get_user_upload_dir() -> str:
    upload_folder = app.config.get('UPLOAD_FOLDER', 'data/uploads')
    return upload_folder if os.path.isabs(upload_folder) else os.path.join(os.getcwd(), upload_folder)


def _normalize_abs_path(path: str, message: str = "无效的文件路径") -> str:
    try:
        return os.path.abspath(os.fspath(path))
    except (TypeError, ValueError, OSError) as e:
        logger.warning(f"路径规范化失败: {path}, 错误: {e}")
        raise APIError(message, 400)


def _path_is_within(abs_path: str, directory: str) -> bool:
    abs_directory = os.path.abspath(directory)
    return abs_path == abs_directory or abs_path.startswith(abs_directory + os.sep)


def _require_path_in_dirs(path: str, allowed_dirs: List[str], message: str = "无效的文件路径") -> str:
    abs_path = _normalize_abs_path(path, message)
    if any(_path_is_within(abs_path, allowed_dir) for allowed_dir in allowed_dirs):
        return abs_path
    raise APIError(message, 400)


def _require_existing_file_in_dirs(path: str, allowed_dirs: List[str], message: str = "无效的文件路径") -> str:
    abs_path = _require_path_in_dirs(path, allowed_dirs, message)
    if not os.path.isfile(abs_path):
        raise APIError("文件不存在", 404)
    return abs_path


def _resolve_user_audio_input_path(path: str) -> str:
    return _require_existing_file_in_dirs(
        path,
        [_get_audio_dir(), _get_user_upload_dir()],
        "audio_file_path 不允许访问应用数据目录外的文件"
    )


def _document_download_url(document: Any) -> str:
    document_id = document['id']
    return f"/api/meetings/documents/download?{urlencode({'document_id': document_id})}"


def _get_llm_verify_setting() -> Any:
    ca_bundle = os.getenv('LLM_CA_BUNDLE', '').strip()
    if ca_bundle:
        return ca_bundle
    raw_verify = os.getenv('LLM_VERIFY_SSL')
    if raw_verify is not None:
        return _coerce_bool(raw_verify, True)
    return True


def _get_upload_task_timestamp() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _safe_json_loads(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _parse_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _paginate_items(items: List[Any]) -> Tuple[List[Any], Optional[Dict[str, int]]]:
    if request.args.get('page') is None and request.args.get('page_size') is None:
        return items, None

    page = max(1, _parse_int(request.args.get('page'), 1) or 1)
    page_size = max(1, min(_parse_int(request.args.get('page_size'), 20) or 20, 100))
    total = len(items)
    start = (page - 1) * page_size
    return items[start:start + page_size], {
        'page': page,
        'page_size': page_size,
        'total': total
    }


def _normalize_upload_speaker_bounds(
    expected_speakers: Optional[int],
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    expected_speakers = expected_speakers if expected_speakers and 2 <= expected_speakers <= 50 else None
    if expected_speakers:
        return expected_speakers, expected_speakers, expected_speakers

    min_speakers = min_speakers if min_speakers and 2 <= min_speakers <= 50 else None
    max_speakers = max_speakers if max_speakers and 2 <= max_speakers <= 50 else None
    if min_speakers is None and max_speakers is None:
        return None, None, None
    if min_speakers is None:
        min_speakers = 2
    if max_speakers is None:
        max_speakers = min_speakers
    if min_speakers > max_speakers:
        min_speakers, max_speakers = max_speakers, min_speakers
    if min_speakers == max_speakers:
        return min_speakers, min_speakers, max_speakers
    return None, min_speakers, max_speakers


def _parse_upload_speaker_bounds(
    raw_expected: Any,
    raw_min: Any = None,
    raw_max: Any = None
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    expected_speakers = None
    min_speakers = _parse_int(raw_min)
    max_speakers = _parse_int(raw_max)

    if raw_expected is not None:
        text = str(raw_expected).strip()
        numbers = [int(value) for value in re.findall(r"\d+", text)]
        if len(numbers) == 1:
            expected_speakers = numbers[0]
        elif len(numbers) >= 2:
            min_speakers = numbers[0]
            max_speakers = numbers[1]

    return _normalize_upload_speaker_bounds(expected_speakers, min_speakers, max_speakers)


def _get_upload_task_row(task_id: str) -> Optional[Dict[str, Any]]:
    rows = db.execute_query("SELECT * FROM uploaded_audio_tasks WHERE task_id = ?", (task_id,))
    return dict(rows[0]) if rows else None


def _upload_task_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(row)
    payload["result"] = _safe_json_loads(payload.pop("result_json", None), None)
    payload["media_info"] = _safe_json_loads(payload.pop("media_info_json", None), {})
    payload["enable_speaker_diarization"] = bool(payload.get("enable_speaker_diarization"))
    payload["enable_voiceprint_matching"] = bool(payload.get("enable_voiceprint_matching"))
    payload["enable_translation"] = bool(payload.get("enable_translation"))
    if payload.get("status") == "queued":
        payload["queue_position"] = _get_upload_queue_position(str(payload.get("task_id") or ""))
    return payload


def _get_upload_queue_position(task_id: str) -> Optional[int]:
    if not task_id:
        return None
    rows = db.execute_query(
        "SELECT task_id FROM uploaded_audio_tasks WHERE status = 'queued' ORDER BY created_at, task_id"
    )
    for index, queued_row in enumerate(rows, start=1):
        if queued_row["task_id"] == task_id:
            return index
    return None


def _clean_upload_task_updates(updates: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "recognition_file_name",
        "recognition_path",
        "status",
        "progress",
        "stage",
        "error",
        "result_json",
        "media_info_json",
        "completed_at",
    }
    return {key: value for key, value in updates.items() if key in allowed}


def _update_upload_task(task_id: str, **updates: Any) -> None:
    clean_updates = _clean_upload_task_updates(updates)
    if not clean_updates:
        return
    clean_updates["updated_at"] = _get_upload_task_timestamp()
    assignments = ", ".join(f"{key} = ?" for key in clean_updates.keys())
    db.execute_update(
        f"UPDATE uploaded_audio_tasks SET {assignments} WHERE task_id = ?",
        (*clean_updates.values(), task_id),
    )


def _update_upload_task_if_active(task_id: str, **updates: Any) -> bool:
    clean_updates = _clean_upload_task_updates(updates)
    if not clean_updates:
        return True
    clean_updates["updated_at"] = _get_upload_task_timestamp()
    assignments = ", ".join(f"{key} = ?" for key in clean_updates.keys())
    affected = db.execute_update(
        f"UPDATE uploaded_audio_tasks SET {assignments} WHERE task_id = ? AND status != 'cancelled'",
        (*clean_updates.values(), task_id),
    )
    return affected > 0


def _is_upload_task_cancelled(task_id: str) -> bool:
    row = _get_upload_task_row(task_id)
    return bool(row and row.get("status") == "cancelled")


def _raise_if_upload_task_cancelled(task_id: str) -> None:
    if _is_upload_task_cancelled(task_id):
        raise UploadTaskCancelled("上传识别任务已取消")


def _cancel_upload_task(task_id: str) -> Dict[str, Any]:
    row = _get_upload_task_row(task_id)
    if not row:
        raise APIError("上传识别任务不存在", 404)

    if row.get("status") in {"succeeded", "failed", "cancelled"}:
        return _upload_task_payload(row)

    with upload_task_futures_lock:
        future = upload_task_futures.pop(task_id, None)
    if future is not None:
        future.cancel()

    _update_upload_task(
        task_id,
        status="cancelled",
        progress=100,
        stage="已取消上传识别任务",
        error="用户已取消上传识别任务",
        completed_at=_get_upload_task_timestamp(),
    )
    return _upload_task_payload(_get_upload_task_row(task_id))


def _save_uploaded_recognition_file(audio_file, original_filename: str) -> Tuple[str, str, int]:
    max_audio_bytes, _ = _get_upload_asr_limits()
    audio_dir = _get_uploaded_audio_upload_dir()
    os.makedirs(audio_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    saved_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{original_filename}"
    saved_path = os.path.join(audio_dir, saved_filename)
    written = 0

    try:
        with open(saved_path, 'wb') as output:
            while True:
                chunk = audio_file.stream.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_audio_bytes:
                    raise APIError(
                        f"上传音频过大: {written / 1024 / 1024:.1f}MB，最大允许: {max_audio_bytes / 1024 / 1024:.0f}MB",
                        413,
                    )
                output.write(chunk)
    except Exception:
        if os.path.exists(saved_path):
            os.unlink(saved_path)
        raise

    if written == 0:
        if os.path.exists(saved_path):
            os.unlink(saved_path)
        raise APIError("音频文件不能为空", 400)

    return saved_filename, saved_path, written


def _create_upload_task(
    *,
    file_name: str,
    saved_file_name: str,
    saved_path: str,
    language: str,
    enable_speaker_diarization: bool,
    enable_voiceprint_matching: bool,
    enable_translation: bool,
    speaker_top_k: int,
    expected_speakers: Optional[int],
    min_speakers: Optional[int],
    max_speakers: Optional[int],
    hotword_text: str,
    media_info: Dict[str, Any],
) -> str:
    task_id = str(uuid.uuid4())
    timestamp = _get_upload_task_timestamp()
    db.execute_insert(
        """
        INSERT INTO uploaded_audio_tasks (
            task_id, file_name, saved_file_name, saved_path, language,
            enable_speaker_diarization, enable_voiceprint_matching, enable_translation, speaker_top_k,
            expected_speakers, min_speakers, max_speakers, hotword_text, status, progress, stage, media_info_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            file_name,
            saved_file_name,
            saved_path,
            language,
            1 if enable_speaker_diarization else 0,
            1 if enable_voiceprint_matching else 0,
            1 if enable_translation else 0,
            speaker_top_k,
            expected_speakers,
            min_speakers,
            max_speakers,
            hotword_text,
            "queued",
            0,
            "已加入上传识别队列",
            json.dumps(media_info or {}, ensure_ascii=False),
            timestamp,
            timestamp,
        ),
    )
    return task_id


def _get_uploaded_task_meeting_id(task_id: str) -> Optional[int]:
    rows = db.execute_query(
        """
        SELECT meeting_id
        FROM uploaded_audio_segments
        WHERE task_id = ? AND meeting_id IS NOT NULL
        LIMIT 1
        """,
        (task_id,)
    )
    return int(rows[0]["meeting_id"]) if rows else None


def _link_upload_task_segments_to_meeting(task_id: str, meeting_id: int) -> int:
    return db.execute_update(
        "UPDATE uploaded_audio_segments SET meeting_id = ? WHERE task_id = ?",
        (meeting_id, task_id)
    )


def _get_meeting_uploaded_segment_rows(meeting_id: int) -> List[Any]:
    return db.execute_query(
        """
        SELECT
            uas.*,
            uat.file_name AS task_file_name,
            uat.saved_file_name AS task_saved_file_name,
            uat.created_at AS task_created_at
        FROM uploaded_audio_segments uas
        LEFT JOIN uploaded_audio_tasks uat ON uat.task_id = uas.task_id
        WHERE uas.meeting_id = ?
        ORDER BY COALESCE(uat.created_at, ''), uas.task_id, uas.segment_index, uas.id
        """,
        (meeting_id,)
    )


def _get_meeting_transcription_source(meeting_id: int) -> Tuple[str, Optional[str]]:
    rows = db.execute_query(
        """
        SELECT task_id
        FROM uploaded_audio_segments
        WHERE meeting_id = ?
        ORDER BY id
        LIMIT 1
        """,
        (meeting_id,)
    )
    if rows:
        return "upload", rows[0]["task_id"]
    return "realtime", None


def _uploaded_segment_row_to_response(row: Any) -> Dict[str, Any]:
    data = dict(row)
    start_ms = data.get("start_ms")
    end_ms = data.get("end_ms")
    return {
        "task_id": data.get("task_id"),
        "segment_index": data.get("segment_index"),
        "speaker": data.get("speaker") or "",
        "speaker_type": data.get("speaker_type") or "",
        "speaker_confidence": data.get("speaker_confidence"),
        "text": data.get("text") or "",
        "translation": data.get("translation") or "",
        "mode": data.get("mode") or "uploaded-audio",
        "timestamp": [[start_ms, end_ms]] if start_ms is not None and end_ms is not None else None,
        "startMs": start_ms,
        "endMs": end_ms,
        "startTime": _format_ms(start_ms),
        "endTime": _format_ms(end_ms),
        "speaker_result": _safe_json_loads(data.get("speaker_result_json"), None),
    }


def _uploaded_segments_to_markdown(segments: List[Dict[str, Any]]) -> str:
    blocks = []
    for index, segment in enumerate(segments):
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        speaker = (segment.get("speaker") or "").strip()
        time_range = ""
        if segment.get("startTime") and segment.get("endTime"):
            time_range = f"{segment['startTime']} - {segment['endTime']}"

        header_parts = []
        if speaker:
            header_parts.append(f"**{speaker}**")
        elif len(segments) > 1:
            header_parts.append(f"**说话人{index + 1}**")
        if time_range:
            header_parts.append(f"[{time_range}]")

        body = text
        translation = (segment.get("translation") or "").strip()
        if translation:
            body = f"{body}\n\n翻译：{translation}"
        blocks.append(f"{' '.join(header_parts)}\n{body}" if header_parts else body)
    return "\n\n".join(blocks)


def _persist_uploaded_task_segments(task_id: str, segments: List[Dict[str, Any]]) -> None:
    meeting_id = _get_uploaded_task_meeting_id(task_id)
    db.execute_update("DELETE FROM uploaded_audio_segments WHERE task_id = ?", (task_id,))
    for index, segment in enumerate(segments):
        db.execute_insert(
            """
            INSERT INTO uploaded_audio_segments (
                task_id, meeting_id, segment_index, speaker, speaker_type, speaker_confidence,
                text, translation, start_ms, end_ms, mode, speaker_result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                meeting_id,
                index,
                segment.get("speaker"),
                segment.get("speaker_type"),
                segment.get("speaker_confidence"),
                segment.get("text") or "",
                segment.get("translation"),
                segment.get("startMs"),
                segment.get("endMs"),
                segment.get("mode") or "uploaded-audio",
                json.dumps(segment.get("speaker_result"), ensure_ascii=False) if segment.get("speaker_result") else None,
            ),
        )


def _complete_upload_task(task_id: str, result: Dict[str, Any]) -> None:
    if _is_upload_task_cancelled(task_id):
        logger.info(f"上传识别任务已取消，丢弃完成结果: task_id={task_id}")
        return
    _persist_uploaded_task_segments(task_id, result.get("segments") or [])
    _update_upload_task_if_active(
        task_id,
        status="succeeded",
        progress=100,
        stage="上传识别完成",
        result_json=json.dumps(result, ensure_ascii=False),
        completed_at=_get_upload_task_timestamp(),
        error=None,
    )


def _valid_upload_hotword(text: str) -> bool:
    value = text.strip()
    if len(value) < 2 or len(value) > _get_env_int('UPLOAD_ASR_HOTWORD_MAX_LEN', 16, 4):
        return False
    if value.isdigit():
        return False
    return True


def _parse_upload_hotwords(raw_hotwords: Optional[str]) -> Dict[str, int]:
    terms: Dict[str, int] = {}
    if not raw_hotwords:
        return terms

    raw_hotwords = raw_hotwords.replace("\\r\\n", "\n").replace("\\n", "\n").strip()
    parsed = None
    if raw_hotwords.startswith("{"):
        parsed = _safe_json_loads(raw_hotwords, {})
    if isinstance(parsed, dict):
        for word, weight in parsed.items():
            word = str(word).strip()
            if _valid_upload_hotword(word):
                terms[word] = _parse_int(weight, 50) or 50
        return terms

    for line in raw_hotwords.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        weight = 50
        if len(parts) >= 2 and parts[-1].isdigit():
            weight = int(parts[-1])
            word = " ".join(parts[:-1]).strip()
        else:
            word = line
        if _valid_upload_hotword(word):
            terms[word] = max(1, min(100, weight))
    return terms


def _build_upload_hotword_text(
    extra_hotwords: Optional[str] = None,
    include_default_hotwords: bool = True
) -> str:
    merged: Dict[str, int] = {}
    if include_default_hotwords and os.path.exists(HOTWORDS_TXT_PATH):
        try:
            with open(HOTWORDS_TXT_PATH, 'r', encoding='utf-8') as file:
                merged.update(_parse_upload_hotwords(file.read()))
        except Exception as e:
            logger.warning(f"读取上传识别热词文件失败: {e}")
    merged.update(_parse_upload_hotwords(extra_hotwords))

    limit = _get_env_int('UPLOAD_ASR_HOTWORD_LIMIT', 500, 10)
    ranked = sorted(merged.items(), key=lambda item: (item[1], len(item[0])), reverse=True)
    return " ".join(word for word, _ in ranked[:limit])


UPLOAD_DEFAULT_TEXT_CORRECTIONS: List[Tuple[str, str]] = []


def _normalize_upload_correction_pair(source: Any, target: Any) -> Optional[Tuple[str, str]]:
    source_text = str(source or "").strip()
    target_text = str(target or "").strip()
    if not source_text or source_text == target_text:
        return None
    if len(source_text) > 80 or len(target_text) > 120:
        return None
    return source_text, target_text


def _parse_upload_corrections(raw_corrections: Any) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    if not raw_corrections:
        return pairs

    if isinstance(raw_corrections, dict):
        iterable = raw_corrections.items()
    elif isinstance(raw_corrections, list):
        iterable = []
        for item in raw_corrections:
            if isinstance(item, dict):
                source = item.get("from") if item.get("from") is not None else item.get("source")
                target = item.get("to") if item.get("to") is not None else item.get("target")
                iterable.append((source, target))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                iterable.append((item[0], item[1]))
    else:
        raw_text = str(raw_corrections).replace("\\r\\n", "\n").replace("\\n", "\n")
        iterable = []
        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=>" in line:
                source, target = line.split("=>", 1)
            elif "->" in line:
                source, target = line.split("->", 1)
            else:
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                source, target = parts
            iterable.append((source, target))

    for source, target in iterable:
        pair = _normalize_upload_correction_pair(source, target)
        if pair:
            pairs.append(pair)
    return pairs


def _load_upload_text_correction_pairs(
    extra_corrections: Any = None,
    use_default: bool = True,
    include_config_file: bool = True
) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = list(UPLOAD_DEFAULT_TEXT_CORRECTIONS) if use_default else []
    corrections_file = os.path.join('data', 'upload_corrections.txt')
    if include_config_file and os.path.exists(corrections_file):
        try:
            with open(corrections_file, 'r', encoding='utf-8') as file:
                pairs.extend(_parse_upload_corrections(file.read()))
        except Exception as e:
            logger.warning(f"读取上传识别纠错文件失败: {e}")
    pairs.extend(_parse_upload_corrections(extra_corrections))

    deduped: Dict[str, str] = {}
    for source, target in pairs:
        deduped[source] = target
    return sorted(deduped.items(), key=lambda item: len(item[0]), reverse=True)


def _apply_upload_text_corrections(
    text: str,
    correction_pairs: Optional[List[Tuple[str, str]]] = None
) -> Tuple[str, int, List[Dict[str, Any]]]:
    corrected = text or ""
    pairs = correction_pairs if correction_pairs is not None else _load_upload_text_correction_pairs()
    total = 0
    details: List[Dict[str, Any]] = []
    for source, target in pairs:
        count = corrected.count(source)
        if count <= 0:
            continue
        corrected = corrected.replace(source, target)
        total += count
        details.append({"from": source, "to": target, "count": count})
    return corrected, total, details


def _merge_upload_correction_details(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[Tuple[str, str], int] = {}
    for item in details:
        key = (item.get("from", ""), item.get("to", ""))
        if not key[0]:
            continue
        merged[key] = merged.get(key, 0) + int(item.get("count") or 0)
    return [
        {"from": source, "to": target, "count": count}
        for (source, target), count in sorted(merged.items(), key=lambda item: item[1], reverse=True)
        if count > 0
    ]


def _apply_uploaded_result_corrections(
    result: Dict[str, Any],
    extra_corrections: Any = None,
    use_default: bool = True,
    include_config_file: bool = True,
    correction_pairs: Optional[List[Tuple[str, str]]] = None
) -> Dict[str, Any]:
    if correction_pairs is None:
        correction_pairs = _load_upload_text_correction_pairs(
            extra_corrections,
            use_default=use_default,
            include_config_file=include_config_file
        )
    all_details: List[Dict[str, Any]] = []
    total = 0

    for segment in result.get("segments") or []:
        corrected, count, details = _apply_upload_text_corrections(segment.get("text", ""), correction_pairs)
        if count:
            segment["text"] = corrected
            total += count
            all_details.extend(details)

    if result.get("plain_text"):
        corrected, count, details = _apply_upload_text_corrections(result.get("plain_text", ""), correction_pairs)
        if count:
            result["plain_text"] = corrected
            total += count
            all_details.extend(details)

    metadata = result.setdefault("asr_metadata", {})
    previous_count = int(metadata.get("text_correction_count") or 0)
    metadata["text_correction_count"] = previous_count + total
    metadata["text_correction_details"] = _merge_upload_correction_details(
        (metadata.get("text_correction_details") or []) + all_details
    )[:20]
    return result


def _get_upload_result_text_correction_count(result: Dict[str, Any]) -> int:
    metadata = result.get("asr_metadata") or {}
    try:
        return int(metadata.get("text_correction_count") or 0)
    except (TypeError, ValueError):
        return 0


def _resolve_uploaded_audio_path(base_dir: str, filename: str) -> str:
    if not filename or os.path.basename(filename) != filename:
        raise APIError("无效的上传音频文件名", 400)

    safe_filename = secure_filename(filename)
    if not safe_filename or safe_filename != filename:
        raise APIError("无效的上传音频文件名", 400)

    file_path = os.path.abspath(os.path.join(base_dir, safe_filename))
    abs_base_dir = os.path.abspath(base_dir)
    if not file_path.startswith(abs_base_dir + os.sep):
        raise APIError("无效的上传音频路径", 400)
    if not os.path.exists(file_path):
        raise APIError("上传音频文件不存在，请重新上传识别", 404)
    return file_path


def _persist_uploaded_recognition_audio(source_path: str, converted_audio_path: str) -> Optional[Dict[str, Any]]:
    try:
        recognition_dir = _get_uploaded_recognition_audio_dir()
        os.makedirs(recognition_dir, exist_ok=True)

        source_base = os.path.splitext(os.path.basename(source_path))[0]
        file_name = secure_filename(f"{source_base}_recognition.wav")
        if not file_name:
            file_name = f"{uuid.uuid4().hex}_recognition.wav"

        persistent_path = os.path.join(recognition_dir, file_name)
        shutil.copyfile(converted_audio_path, persistent_path)
        return {
            "path": persistent_path,
            "file_name": file_name,
            "source_file_name": os.path.basename(source_path),
            "time_base": "recognition_wav_16k_mono",
            "sample_rate": 16000,
            "channels": 1
        }
    except Exception as e:
        logger.warning(f"保存上传识别基准音频失败，后续声纹注册将回退源文件转换: {e}")
        return None


def _public_registration_audio_ref(ref: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not ref:
        return {}
    return {key: value for key, value in ref.items() if key != "path"}


def _coerce_optional_ms(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _limit_registration_ranges(
    ranges: List[Tuple[int, int]],
    max_duration_ms: int = UPLOAD_SPEAKER_REGISTRATION_MAX_MS
) -> List[Tuple[int, int]]:
    limited = []
    remaining_ms = max(1, max_duration_ms)

    for start_ms, end_ms in sorted(ranges, key=lambda item: item[0]):
        if end_ms <= start_ms or remaining_ms <= 0:
            continue

        duration_ms = min(end_ms - start_ms, remaining_ms)
        limited.append((start_ms, start_ms + duration_ms))
        remaining_ms -= duration_ms

    return limited


def _collect_registration_audio_ranges(data: Dict[str, Any]) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    raw_segments = data.get("segments") or []

    if isinstance(raw_segments, list):
        for segment in raw_segments:
            if not isinstance(segment, dict):
                continue

            start_ms = _coerce_optional_ms(
                segment.get("start_ms") if segment.get("start_ms") is not None else segment.get("startMs")
            )
            end_ms = _coerce_optional_ms(
                segment.get("end_ms") if segment.get("end_ms") is not None else segment.get("endMs")
            )
            if start_ms is not None and end_ms is not None and end_ms > start_ms:
                ranges.append((max(0, start_ms), max(0, end_ms)))

    if not ranges:
        start_ms = _coerce_optional_ms(data.get("start_ms") if data.get("start_ms") is not None else data.get("startMs"))
        end_ms = _coerce_optional_ms(data.get("end_ms") if data.get("end_ms") is not None else data.get("endMs"))
        duration_ms = _coerce_optional_ms(data.get("duration_ms") if data.get("duration_ms") is not None else data.get("durationMs"))
        duration_ms = duration_ms or UPLOAD_SPEAKER_REGISTRATION_MAX_MS

        if start_ms is not None:
            if end_ms is None or end_ms <= start_ms:
                end_ms = start_ms + duration_ms
            ranges.append((max(0, start_ms), max(0, end_ms)))

    max_duration_ms = _coerce_optional_ms(data.get("max_duration_ms")) or UPLOAD_SPEAKER_REGISTRATION_MAX_MS
    return _limit_registration_ranges(ranges, max_duration_ms=max_duration_ms)


def _clear_cuda_memory() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
    except Exception as e:
        logger.debug(f"清理CUDA显存失败，继续处理: {e}")


def _get_cuda_memory_info() -> Optional[Dict[str, int]]:
    try:
        import torch
        if not torch.cuda.is_available():
            return None

        device = torch.cuda.current_device()
        total = torch.cuda.get_device_properties(device).total_memory
        reserved = torch.cuda.memory_reserved(device)
        allocated = torch.cuda.memory_allocated(device)
        free = max(0, total - reserved)
        return {
            "total": int(total),
            "reserved": int(reserved),
            "allocated": int(allocated),
            "free": int(free)
        }
    except Exception as e:
        logger.debug(f"获取CUDA显存信息失败，跳过显存预检查: {e}")
        return None


def _ensure_cuda_memory_available(audio_size_bytes: int) -> bool:
    memory_info = _get_cuda_memory_info()
    if not memory_info:
        return True

    estimated_need = int(audio_size_bytes * UPLOAD_ASR_GPU_MEMORY_MULTIPLIER)
    if memory_info["free"] >= estimated_need:
        return True

    logger.warning(
        "上传音频识别显存预检查不足，尝试清理CUDA缓存: "
        f"free={memory_info['free'] / 1024 / 1024:.1f}MB, "
        f"estimated_need={estimated_need / 1024 / 1024:.1f}MB"
    )
    _clear_cuda_memory()

    memory_info = _get_cuda_memory_info()
    if not memory_info:
        return True

    if memory_info["free"] < estimated_need:
        logger.warning(
            "CUDA缓存清理后显存仍偏紧，整文件推理可能失败: "
            f"free={memory_info['free'] / 1024 / 1024:.1f}MB, "
            f"estimated_need={estimated_need / 1024 / 1024:.1f}MB"
        )
        return False
    return True


def _validate_uploaded_audio_buffer(audio_path: str, max_audio_bytes: int) -> int:
    audio_size = os.path.getsize(audio_path)
    if audio_size > max_audio_bytes:
        raise APIError(
            f"上传音频过大: {audio_size / 1024 / 1024:.1f}MB，"
            f"最大允许: {max_audio_bytes / 1024 / 1024:.0f}MB",
            413
        )
    return audio_size


def _upload_asr_has_accelerated_device(args) -> bool:
    device = str(getattr(args, 'device', '') or '').lower()
    try:
        ngpu = int(getattr(args, 'ngpu', 0) or 0)
    except (TypeError, ValueError):
        ngpu = 0
    if ngpu <= 0:
        return False
    try:
        import torch
        if device.startswith("cuda"):
            return bool(torch.cuda.is_available())
        if device.startswith("mps"):
            return bool(
                getattr(torch.backends, "mps", None) is not None
                and torch.backends.mps.is_available()
            )
    except Exception:
        return False
    return False


def _guard_uploaded_internal_speaker_runtime(
    args,
    media_duration_seconds: Optional[float],
    audio_size: int
) -> None:
    max_seconds = _get_env_int(
        'UPLOAD_INTERNAL_SPEAKER_CPU_MAX_SECONDS',
        UPLOAD_INTERNAL_SPEAKER_CPU_MAX_SECONDS,
        0
    )
    if max_seconds <= 0 or not media_duration_seconds:
        return
    if media_duration_seconds <= max_seconds:
        return
    if _upload_asr_has_accelerated_device(args):
        return

    raise APIError(
        "当前环境没有可用的CUDA/MPS加速，FunASR内置说话人分离处理长音频会长时间阻塞。"
        f"本文件时长约 {media_duration_seconds / 60:.1f} 分钟，"
        f"大小约 {audio_size / 1024 / 1024:.1f}MB，"
        f"超过CPU保护阈值 {max_seconds / 60:.0f} 分钟，已停止任务。"
        "请使用可用GPU/MPS环境、缩短音视频，或关闭上传内置说话人后重试。",
        422
    )


def _load_uploaded_asr_input(audio_path: str):
    try:
        import numpy as np
        import soundfile as sf

        audio_data, _ = sf.read(audio_path, dtype='float32', always_2d=False)
        if getattr(audio_data, 'ndim', 1) > 1:
            audio_data = np.mean(audio_data, axis=1)
        return audio_data.astype('float32', copy=False)
    except Exception as e:
        logger.warning(f"读取上传音频为波形数组失败，回退为路径输入: {e}")
        return audio_path


def _generate_uploaded_asr_chunk(
    upload_asr_model,
    audio_input,
    asr_params: Dict[str, Any],
    *,
    allow_text_fallback: bool = True,
    model_progress_callback=None,
):
    try:
        with upload_asr_lock:
            return upload_asr_model.generate(
                input=audio_input,
                progress_callback=model_progress_callback,
                **asr_params
            )
    except TypeError as e:
        if not allow_text_fallback:
            logger.warning(f"上传音频ASR内置说话人参数异常，已停止本次任务，避免长文件重复识别: {e}")
            raise APIError(
                "FunASR内置说话人分离失败，已停止本次任务，避免同一长音频重复识别。"
                "请检查人数设置或切换上传说话人模式后重试。",
                500
            ) from e
        logger.warning(f"上传音频ASR分句/说话人参数不兼容，降级为基础识别参数: {e}")
        fallback_params = dict(asr_params)
        for key in ("cache", "merge_vad", "merge_length_s", "hotword", "preset_spk_num"):
            fallback_params.pop(key, None)
        fallback_params["return_spk_res"] = False
        with upload_asr_lock:
            return upload_asr_model.generate(
                input=audio_input,
                progress_callback=model_progress_callback,
                **fallback_params
            )
    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            _clear_cuda_memory()
            raise APIError(
                "上传音频识别显存不足，已清理CUDA缓存。"
                "请降低文件大小后重试，或切换CPU/更大显存设备。",
                507
            ) from e
        raise


def _run_uploaded_audio_asr(
    audio_path: str,
    server_state,
    language: str,
    hotword_text: str = "",
    expected_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    media_duration_seconds: Optional[float] = None,
    progress_callback=None
) -> Dict[str, Any]:
    upload_asr_model = getattr(server_state, 'model_asr_upload', None) if server_state is not None else None
    if upload_asr_model is None:
        raise APIError("上传文件ASR模型未加载，请通过 main.py 启动主服务后再上传识别", 503)

    args = getattr(server_state, 'args', None)
    max_audio_bytes, _ = _get_upload_asr_limits()
    audio_size = _validate_uploaded_audio_buffer(audio_path, max_audio_bytes)

    speaker_requested = getattr(args, 'upload_asr_enable_internal_speaker', True)
    use_internal_speaker = (
        speaker_requested
        and getattr(upload_asr_model, 'spk_model', None) is not None
    )
    if speaker_requested and not use_internal_speaker:
        raise APIError(
            "上传人员分离已按官网链路强制开启，但FunASR上传模型未加载spk_model。"
            "请确认本地cam++模型存在，或重新启动服务加载上传ASR模型。",
            503
        )
    merge_vad = bool(getattr(args, 'upload_asr_merge_vad', False))
    asr_params = {
        "cache": {},
        "batch_size_s": getattr(args, 'upload_asr_batch_size_s', 60),
        "language": language or getattr(args, 'upload_asr_language', 'zh'),
        "use_itn": True,
        "merge_vad": merge_vad
    }
    if merge_vad:
        asr_params["merge_length_s"] = getattr(args, 'upload_asr_merge_length_s', 8)
    if hotword_text:
        asr_params["hotword"] = hotword_text
    if use_internal_speaker:
        asr_params["return_spk_res"] = True
        asr_params["sentence_timestamp"] = True
        asr_params["return_raw_text"] = True
        normalized_expected, normalized_min, normalized_max = _normalize_upload_speaker_bounds(
            expected_speakers,
            min_speakers,
            max_speakers
        )
        preset_speaker_count = normalized_expected or 0
        if not preset_speaker_count and normalized_min and normalized_max:
            preset_speaker_count = int((normalized_min + normalized_max + 1) // 2)
            logger.info(
                "上传音频ASR内置说话人仅支持精确人数，已从范围推导preset_spk_num: "
                f"min={normalized_min}, max={normalized_max}, preset={preset_speaker_count}"
            )
        if preset_speaker_count >= 2:
            asr_params["preset_spk_num"] = preset_speaker_count
        _guard_uploaded_internal_speaker_runtime(args, media_duration_seconds, audio_size)
    _ensure_cuda_memory_available(audio_size)
    logger.info(f"上传音频ASR整文件处理: size={audio_size / 1024 / 1024:.1f}MB")
    if progress_callback:
        progress_callback(0, 1)

    model_progress_state = {"ratio": 0.0}

    def handle_model_progress(done: int, total: int) -> None:
        if not progress_callback or not total or total <= 1:
            return
        try:
            ratio = max(0.0, min(float(done) / float(total), 0.98))
        except (TypeError, ValueError, ZeroDivisionError):
            return
        if ratio <= model_progress_state["ratio"]:
            return
        model_progress_state["ratio"] = ratio
        progress_callback(int(ratio * 100), 100)

    raw_result = _generate_uploaded_asr_chunk(
        upload_asr_model,
        audio_path,
        asr_params,
        allow_text_fallback=not use_internal_speaker,
        model_progress_callback=handle_model_progress
    )
    _clear_cuda_memory()
    if progress_callback:
        progress_callback(1, 1)

    if not raw_result:
        return {
            "text": "",
            "raw_result": {},
            "timestamp": [],
            "sentence_info": [],
            "chunk_count": 1,
            "chunked": False,
            "audio_size": audio_size
        }

    rec_result = raw_result[0]
    rec_result["text"] = _postprocess_uploaded_transcript_text(rec_result.get("text", ""), server_state)
    rec_result["audio_size"] = audio_size
    rec_result["chunk_count"] = 1
    rec_result["chunked"] = False
    return rec_result


def _get_timestamp_range(timestamp) -> tuple:
    if not timestamp or not isinstance(timestamp, list):
        return None, None

    first = timestamp[0]
    last = timestamp[-1]
    if isinstance(first, (list, tuple)) and len(first) >= 2 and isinstance(last, (list, tuple)) and len(last) >= 2:
        return int(first[0]), int(last[1])
    return None, None


def _format_ms(milliseconds: Optional[int]) -> Optional[str]:
    if milliseconds is None:
        return None
    try:
        from ..audio.audio_processing import format_timestamp_for_display
        return format_timestamp_for_display(int(milliseconds))
    except Exception:
        total_seconds = int(milliseconds) // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _extract_asr_segments(rec_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    sentence_info = rec_result.get("sentence_info") or []
    segments = []

    for sentence in sentence_info:
        text = _clean_sentence_text(sentence.get("text") or sentence.get("sentence", ""))
        if not text:
            continue

        start_ms = sentence.get("start")
        end_ms = sentence.get("end")
        if start_ms is None:
            start_ms = sentence.get("start_time")
        if end_ms is None:
            end_ms = sentence.get("end_time")

        segments.append({
            "text": text,
            "speaker_key": sentence.get("spk"),
            "start_ms": int(start_ms) if start_ms is not None else None,
            "end_ms": int(end_ms) if end_ms is not None else None
        })

    if segments:
        return segments

    raw_chunks = (rec_result.get("raw_result") or {}).get("chunks") or []
    for chunk in raw_chunks:
        text = _clean_sentence_text(chunk.get("text", ""))
        start_ms = _coerce_optional_ms(chunk.get("offset_ms"))
        duration_ms = _coerce_optional_ms(chunk.get("duration_ms"))
        if not text or start_ms is None or duration_ms is None or duration_ms <= 0:
            continue
        segments.append({
            "text": text,
            "speaker_key": "uploaded_audio",
            "start_ms": start_ms,
            "end_ms": start_ms + duration_ms
        })

    if segments:
        return segments

    text = _clean_sentence_text(rec_result.get("text", ""))
    start_ms, end_ms = _get_timestamp_range(rec_result.get("timestamp"))
    return [{
        "text": text,
        "speaker_key": None,
        "start_ms": start_ms,
        "end_ms": end_ms
    }] if text else []


def _uploaded_asr_segment_source(rec_result: Dict[str, Any]) -> str:
    if rec_result.get("sentence_info"):
        return "funasr_sentence_info"
    if (rec_result.get("raw_result") or {}).get("chunks"):
        return "asr_chunk_ranges"
    if rec_result.get("timestamp"):
        return "asr_timestamp_text"
    return "text_only"


def _has_uploaded_asr_speaker_labels(rec_result: Dict[str, Any]) -> bool:
    return any(
        segment.get("text")
        and segment.get("speaker_key") is not None
        and segment.get("start_ms") is not None
        and segment.get("end_ms") is not None
        for segment in _extract_asr_segments(rec_result or {})
    )


def _clean_sentence_text(text: str) -> str:
    return re.sub(r'<\|[^|]*\|>', '', text or '').strip()


def _write_audio_segment(audio_path: str, start_ms: Optional[int], end_ms: Optional[int]) -> Optional[str]:
    if start_ms is None or end_ms is None or end_ms <= start_ms:
        return None

    try:
        from ..audio.audio_format_handler import extract_media_segment_to_wav
        return extract_media_segment_to_wav(audio_path, int(start_ms), int(end_ms))
    except Exception as e:
        logger.debug(f"ffmpeg抽取上传音频片段失败，回退soundfile: {e}")

    try:
        import numpy as np
        import soundfile as sf

        audio_data, sample_rate = sf.read(audio_path, dtype='float32', always_2d=False)
        if getattr(audio_data, 'ndim', 1) > 1:
            audio_data = np.mean(audio_data, axis=1)

        start_sample = max(0, int(start_ms * sample_rate / 1000))
        end_sample = min(len(audio_data), int(end_ms * sample_rate / 1000))
        if end_sample <= start_sample:
            return None

        temp_segment = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_segment_path = temp_segment.name
        temp_segment.close()

        sf.write(temp_segment_path, audio_data[start_sample:end_sample], sample_rate)
        return temp_segment_path
    except Exception as e:
        logger.warning(f"截取上传音频片段失败，将使用整段音频做声纹识别: {e}")
        return None


def _write_audio_segments(audio_path: str, segments: List[Dict[str, Any]]) -> Optional[str]:
    ranges = [
        (segment.get("start_ms"), segment.get("end_ms"))
        for segment in segments
        if segment.get("start_ms") is not None and segment.get("end_ms") is not None
    ]
    if not ranges:
        return None

    try:
        import numpy as np
        import soundfile as sf

        audio_data, sample_rate = sf.read(audio_path, dtype='float32', always_2d=False)
        if getattr(audio_data, 'ndim', 1) > 1:
            audio_data = np.mean(audio_data, axis=1)

        audio_pieces = []
        for start_ms, end_ms in ranges:
            start_sample = max(0, int(start_ms * sample_rate / 1000))
            end_sample = min(len(audio_data), int(end_ms * sample_rate / 1000))
            if end_sample > start_sample:
                audio_pieces.append(audio_data[start_sample:end_sample])

        if not audio_pieces:
            return None

        merged_audio = np.concatenate(audio_pieces) if len(audio_pieces) > 1 else audio_pieces[0]
        temp_segment = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_segment_path = temp_segment.name
        temp_segment.close()

        sf.write(temp_segment_path, merged_audio, sample_rate)
        return temp_segment_path
    except Exception as e:
        logger.warning(f"合并上传音频说话人片段失败，将使用单段音频做声纹识别: {e}")
        return None


def _split_text_by_time_ranges(text: str, ranges: List[Tuple[int, int]]) -> List[str]:
    text = (text or "").strip()
    if not ranges:
        return []
    if not text:
        return ["" for _ in ranges]

    durations = [max(1, end_ms - start_ms) for start_ms, end_ms in ranges]
    total_duration = sum(durations)
    total_chars = len(text)
    pieces = []
    cursor = 0
    accumulated = 0

    for index, duration in enumerate(durations):
        accumulated += duration
        if index == len(durations) - 1:
            end_index = total_chars
        else:
            end_index = max(cursor, min(total_chars, round(total_chars * accumulated / total_duration)))
            while end_index < total_chars and text[end_index] not in "，。！？,.!?；;、 \n":
                end_index += 1
            if end_index < total_chars:
                end_index += 1
        pieces.append(text[cursor:end_index].strip())
        cursor = end_index

    return pieces


def _temporal_speaker_labels(count: int, speaker_count: int) -> List[int]:
    if count <= 0:
        return []
    speaker_count = max(1, min(speaker_count, count))
    return [min(speaker_count - 1, int(index * speaker_count / count)) for index in range(count)]


def _cluster_uploaded_speaker_windows(
    embeddings,
    expected_speakers: Optional[int],
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
) -> List[int]:
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    if len(embeddings) <= 1:
        return [0 for _ in embeddings]

    matrix = np.vstack(embeddings)
    expected_speakers, min_speakers, max_speakers = _normalize_upload_speaker_bounds(
        expected_speakers,
        min_speakers,
        max_speakers
    )
    if expected_speakers and expected_speakers >= 2:
        speaker_count = min(expected_speakers, len(embeddings))
        labels = KMeans(n_clusters=speaker_count, n_init=10, random_state=0).fit_predict(matrix).tolist()
        if len(set(labels)) < min(2, speaker_count):
            return _temporal_speaker_labels(len(embeddings), speaker_count)
        return labels

    fallback_max = max_speakers or _get_env_int('UPLOAD_SPEAKER_FALLBACK_MAX_SPEAKERS', 4, 2)
    fallback_min = min_speakers or _get_env_int('UPLOAD_SPEAKER_FALLBACK_MIN_SPEAKERS', 2, 1)
    speaker_max = min(fallback_max, len(embeddings))
    speaker_min = min(speaker_max, max(2, fallback_min))
    if speaker_max <= 1:
        return [0 for _ in embeddings]

    best_labels = None
    best_score = None
    for speaker_count in range(speaker_min, speaker_max + 1):
        labels = KMeans(n_clusters=speaker_count, n_init=10, random_state=0).fit_predict(matrix)
        if len(set(labels)) <= 1:
            continue
        try:
            score = silhouette_score(matrix, labels)
        except Exception:
            score = -1
        penalty = float(os.getenv('UPLOAD_SPEAKER_CLUSTER_COUNT_PENALTY', '0.08')) * max(0, speaker_count - 2)
        adjusted_score = score - penalty
        if best_score is None or adjusted_score > best_score:
            best_score = adjusted_score
            best_labels = labels.tolist()

    if not best_labels:
        return _temporal_speaker_labels(len(embeddings), speaker_min)
    return best_labels


def _time_overlap_ms(
    start_ms: Optional[int],
    end_ms: Optional[int],
    range_start_ms: Optional[int],
    range_end_ms: Optional[int]
) -> int:
    if start_ms is None or end_ms is None or range_start_ms is None or range_end_ms is None:
        return 0
    return max(0, min(int(end_ms), int(range_end_ms)) - max(int(start_ms), int(range_start_ms)))


def _nearest_uploaded_speaker_range(
    start_ms: Optional[int],
    end_ms: Optional[int],
    speaker_ranges: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if start_ms is None or end_ms is None or not speaker_ranges:
        return None
    midpoint = (int(start_ms) + int(end_ms)) / 2
    return min(
        speaker_ranges,
        key=lambda item: abs(midpoint - ((int(item["start_ms"]) + int(item["end_ms"])) / 2))
    )


def _speaker_for_asr_segment(
    segment: Dict[str, Any],
    speaker_ranges: List[Dict[str, Any]]
) -> Optional[str]:
    best_speaker = None
    best_overlap = 0
    for speaker_range in speaker_ranges:
        overlap = _time_overlap_ms(
            segment.get("start_ms"),
            segment.get("end_ms"),
            speaker_range.get("start_ms"),
            speaker_range.get("end_ms")
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = speaker_range.get("speaker")
    if best_speaker:
        return best_speaker
    nearest = _nearest_uploaded_speaker_range(segment.get("start_ms"), segment.get("end_ms"), speaker_ranges)
    return nearest.get("speaker") if nearest else None


def _build_uploaded_segments_from_asr_speaker_ranges(
    asr_segments: List[Dict[str, Any]],
    speaker_ranges: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    segments = []
    fallback_speaker = (speaker_ranges[0].get("speaker") if speaker_ranges else None) or "说话人1"
    for segment in asr_segments:
        text = segment.get("text") or ""
        if not text:
            continue
        start_ms = segment.get("start_ms")
        end_ms = segment.get("end_ms")
        overlapping_ranges = []
        if start_ms is not None and end_ms is not None:
            for speaker_range in speaker_ranges:
                overlap = _time_overlap_ms(
                    start_ms,
                    end_ms,
                    speaker_range.get("start_ms"),
                    speaker_range.get("end_ms")
                )
                if overlap <= 0:
                    continue
                clipped_start = max(int(start_ms), int(speaker_range["start_ms"]))
                clipped_end = min(int(end_ms), int(speaker_range["end_ms"]))
                if clipped_end <= clipped_start:
                    continue
                if (
                    overlapping_ranges
                    and overlapping_ranges[-1]["speaker"] == speaker_range.get("speaker")
                    and clipped_start <= overlapping_ranges[-1]["end_ms"] + 500
                ):
                    overlapping_ranges[-1]["end_ms"] = clipped_end
                else:
                    overlapping_ranges.append({
                        "speaker": speaker_range.get("speaker") or fallback_speaker,
                        "start_ms": clipped_start,
                        "end_ms": clipped_end,
                    })

        if len(overlapping_ranges) >= 2:
            pieces = _split_text_by_time_ranges(
                text,
                [(item["start_ms"], item["end_ms"]) for item in overlapping_ranges]
            )
            for item, piece in zip(overlapping_ranges, pieces):
                if not piece:
                    continue
                segments.append({
                    "speaker": item["speaker"],
                    "speaker_type": "dynamic",
                    "speaker_confidence": 0.0,
                    "speaker_result": None,
                    "text": piece,
                    "mode": "uploaded-audio",
                    "timestamp": [[item["start_ms"], item["end_ms"]]],
                    "startTime": _format_ms(item["start_ms"]),
                    "endTime": _format_ms(item["end_ms"]),
                    "startMs": item["start_ms"],
                    "endMs": item["end_ms"],
                })
            continue

        speaker = _speaker_for_asr_segment(segment, speaker_ranges) or fallback_speaker
        if overlapping_ranges:
            start_ms = overlapping_ranges[0]["start_ms"]
            end_ms = overlapping_ranges[0]["end_ms"]
            speaker = overlapping_ranges[0]["speaker"]
        segments.append({
            "speaker": speaker,
            "speaker_type": "dynamic",
            "speaker_confidence": 0.0,
            "speaker_result": None,
            "text": text,
            "mode": "uploaded-audio",
            "timestamp": [[start_ms, end_ms]] if start_ms is not None and end_ms is not None else None,
            "startTime": _format_ms(start_ms),
            "endTime": _format_ms(end_ms),
            "startMs": start_ms,
            "endMs": end_ms,
        })
    return segments


def _build_uploaded_segments_from_speaker_ranges_text(
    speaker_ranges: List[Dict[str, Any]],
    text: str
) -> List[Dict[str, Any]]:
    text = _clean_sentence_text(text)
    if not speaker_ranges or not text:
        return []

    pieces = _split_text_by_time_ranges(
        text,
        [(int(item["start_ms"]), int(item["end_ms"])) for item in speaker_ranges]
    )
    expected_non_empty = min(len(speaker_ranges), len(text))
    if sum(1 for piece in pieces if piece) < expected_non_empty:
        pieces = []
        cursor = 0
        total_chars = len(text)
        for index in range(len(speaker_ranges)):
            if cursor >= total_chars:
                pieces.append("")
                continue
            if index == len(speaker_ranges) - 1:
                end_index = total_chars
            else:
                end_index = max(cursor + 1, round(total_chars * (index + 1) / len(speaker_ranges)))
            pieces.append(text[cursor:end_index].strip())
            cursor = end_index

    segments = []
    for item, piece in zip(speaker_ranges, pieces):
        if not piece:
            continue
        start_ms = int(item["start_ms"])
        end_ms = int(item["end_ms"])
        segments.append({
            "speaker": item.get("speaker") or "说话人1",
            "speaker_type": "dynamic",
            "speaker_confidence": 0.0,
            "speaker_result": None,
            "text": piece,
            "mode": "uploaded-audio",
            "timestamp": [[start_ms, end_ms]],
            "startTime": _format_ms(start_ms),
            "endTime": _format_ms(end_ms),
            "startMs": start_ms,
            "endMs": end_ms,
        })
    return segments


def _project_root_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _get_uploaded_vad_model(server_state):
    global upload_vad_model
    if upload_vad_model is not None:
        return upload_vad_model

    with upload_vad_lock:
        if upload_vad_model is not None:
            return upload_vad_model

        args = getattr(server_state, 'args', None)
        vad_model_name = getattr(args, 'upload_asr_vad_model', 'fsmn-vad') if args else 'fsmn-vad'
        if not vad_model_name:
            return None

        from funasr import AutoModel
        from ..core.server_state import get_local_model_path

        vad_model_ref = get_local_model_path(vad_model_name, _project_root_dir())
        if not vad_model_ref:
            logger.warning(
                f"上传音频VAD本地模型不存在: {vad_model_name}，"
                "跳过FunASR VAD并改用本地能量切分兜底；请先运行 `.venv/bin/python organize_models.py` 准备模型"
            )
            return None
        model_kwargs = {
            "model": vad_model_ref,
            "disable_update": True,
            "disable_pbar": True,
            "disable_log": True,
        }
        device = getattr(args, 'device', None) if args else None
        if device:
            model_kwargs["device"] = device

        logger.info(f"加载上传音频VAD模型: {vad_model_ref}")
        upload_vad_model = AutoModel(**model_kwargs)
        return upload_vad_model


def _normalize_uploaded_speech_ranges(raw_ranges) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    for item in raw_ranges or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        start_ms = _coerce_optional_ms(item[0])
        end_ms = _coerce_optional_ms(item[1])
        if start_ms is None or end_ms is None or end_ms <= start_ms:
            continue
        ranges.append((start_ms, end_ms))
    ranges.sort(key=lambda value: value[0])
    return ranges


def _merge_uploaded_speech_ranges(ranges: List[Tuple[int, int]], max_gap_ms: int) -> List[Tuple[int, int]]:
    if not ranges:
        return []
    merged = [ranges[0]]
    for start_ms, end_ms in ranges[1:]:
        prev_start, prev_end = merged[-1]
        if start_ms <= prev_end + max_gap_ms:
            merged[-1] = (prev_start, max(prev_end, end_ms))
        else:
            merged.append((start_ms, end_ms))
    return merged


def _split_uploaded_long_range(start_ms: int, end_ms: int, target_ms: int, max_ms: int, min_ms: int) -> List[Tuple[int, int]]:
    duration = end_ms - start_ms
    if duration <= max_ms:
        return [(start_ms, end_ms)]

    ranges = []
    cursor = start_ms
    while end_ms - cursor > max_ms:
        boundary = min(end_ms, cursor + target_ms)
        if boundary - cursor < min_ms:
            break
        ranges.append((cursor, boundary))
        cursor = boundary

    if end_ms - cursor >= min_ms:
        ranges.append((cursor, end_ms))
    elif ranges:
        prev_start, _ = ranges[-1]
        ranges[-1] = (prev_start, end_ms)

    return ranges


def _postprocess_uploaded_speech_ranges(ranges: List[Tuple[int, int]], duration_ms: int) -> List[Tuple[int, int]]:
    min_ms = _get_env_int('UPLOAD_SPEAKER_SEGMENT_MIN_MS', UPLOAD_SPEAKER_SEGMENT_MIN_MS, 200)
    target_ms = _get_env_int('UPLOAD_SPEAKER_SEGMENT_TARGET_MS', UPLOAD_SPEAKER_SEGMENT_TARGET_MS, 1000)
    max_ms = _get_env_int('UPLOAD_SPEAKER_SEGMENT_MAX_MS', UPLOAD_SPEAKER_SEGMENT_MAX_MS, 2000)
    padding_ms = _get_env_int('UPLOAD_SPEAKER_SEGMENT_PADDING_MS', UPLOAD_SPEAKER_SEGMENT_PADDING_MS, 0)
    merge_gap_ms = _get_env_int('UPLOAD_SPEAKER_SEGMENT_MERGE_GAP_MS', 250, 0)

    max_ms = max(min_ms, max_ms)
    target_ms = max(min_ms, min(target_ms, max_ms))
    padded = [
        (max(0, start_ms - padding_ms), min(duration_ms, end_ms + padding_ms))
        for start_ms, end_ms in ranges
        if end_ms - start_ms >= min_ms
    ]
    merged = _merge_uploaded_speech_ranges(padded, merge_gap_ms)

    result: List[Tuple[int, int]] = []
    for start_ms, end_ms in merged:
        result.extend(_split_uploaded_long_range(start_ms, end_ms, target_ms, max_ms, min_ms))

    return [
        (start_ms, end_ms)
        for start_ms, end_ms in result
        if end_ms - start_ms >= min_ms
    ]


def _sample_uploaded_speech_ranges_for_speaker(
    ranges: List[Tuple[int, int]],
    max_segments: Optional[int] = None
) -> List[Tuple[int, int]]:
    if not ranges:
        return []

    max_segments = max_segments or _get_env_int(
        'UPLOAD_SPEAKER_MAX_VAD_SEGMENTS',
        UPLOAD_SPEAKER_MAX_VAD_SEGMENTS,
        1
    )
    if len(ranges) <= max_segments:
        return ranges

    if max_segments <= 1:
        return [ranges[len(ranges) // 2]]

    selected: List[Tuple[int, int]] = []
    used_indexes = set()
    last_index = -1
    for output_index in range(max_segments):
        source_index = round(output_index * (len(ranges) - 1) / (max_segments - 1))
        source_index = max(last_index + 1, min(len(ranges) - 1, source_index))
        if source_index in used_indexes:
            continue
        selected.append(ranges[source_index])
        used_indexes.add(source_index)
        last_index = source_index

    logger.warning(
        "上传音频说话人VAD片段过多，已抽样处理: "
        f"raw_ranges={len(ranges)}, sampled_ranges={len(selected)}, "
        "可通过 UPLOAD_SPEAKER_MAX_VAD_SEGMENTS 调整上限"
    )
    return selected


def _assign_sampled_speakers_to_all_ranges(
    ranges: List[Tuple[int, int]],
    sampled_speaker_ranges: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if not ranges or not sampled_speaker_ranges:
        return []

    speaker_ranges = []
    fallback_speaker = sampled_speaker_ranges[0].get("speaker") or "说话人1"
    for start_ms, end_ms in ranges:
        speaker = _speaker_for_asr_segment(
            {"start_ms": start_ms, "end_ms": end_ms},
            sampled_speaker_ranges
        ) or fallback_speaker
        speaker_ranges.append({
            "speaker": speaker,
            "start_ms": start_ms,
            "end_ms": end_ms,
        })
    return speaker_ranges


def _merge_uploaded_speaker_ranges_for_piece_asr(
    speaker_ranges: List[Dict[str, Any]],
    max_duration_ms: Optional[int] = None,
    merge_gap_ms: Optional[int] = None
) -> List[Dict[str, Any]]:
    if not speaker_ranges:
        return []

    max_duration_ms = max_duration_ms or _get_env_int(
        'UPLOAD_SPEAKER_PIECE_ASR_TARGET_MS',
        60000,
        1000
    )
    merge_gap_ms = merge_gap_ms if merge_gap_ms is not None else _get_env_int(
        'UPLOAD_SPEAKER_PIECE_ASR_MERGE_GAP_MS',
        1200,
        0
    )

    merged: List[Dict[str, Any]] = []
    ordered = sorted(
        speaker_ranges,
        key=lambda item: (int(item.get("start_ms", 0)), int(item.get("end_ms", 0)))
    )
    current: Optional[Dict[str, Any]] = None

    for item in ordered:
        start_ms = int(item.get("start_ms", 0))
        end_ms = int(item.get("end_ms", start_ms))
        if end_ms <= start_ms:
            continue

        speaker = item.get("speaker") or "说话人1"
        if current is None:
            current = {"speaker": speaker, "start_ms": start_ms, "end_ms": end_ms}
            continue

        current_end = int(current["end_ms"])
        same_speaker = speaker == (current.get("speaker") or "说话人1")
        close_enough = start_ms <= current_end + merge_gap_ms
        duration_ok = end_ms - int(current["start_ms"]) <= max_duration_ms
        if same_speaker and close_enough and duration_ok:
            current["end_ms"] = max(current_end, end_ms)
            continue

        merged.append(current)
        current = {"speaker": speaker, "start_ms": start_ms, "end_ms": end_ms}

    if current is not None:
        merged.append(current)
    return merged


def _detect_uploaded_speech_ranges(audio_path: str, server_state) -> List[Tuple[int, int]]:
    import soundfile as sf

    info = sf.info(audio_path)
    duration_ms = int(info.duration * 1000) if info.duration else 0
    if duration_ms <= 0:
        return []

    try:
        vad_model = _get_uploaded_vad_model(server_state)
        if vad_model is not None:
            with upload_asr_lock:
                vad_result = vad_model.generate(input=audio_path)
            raw_ranges = (vad_result[0].get("value") if vad_result else []) or []
            ranges = _normalize_uploaded_speech_ranges(raw_ranges)
            ranges = _postprocess_uploaded_speech_ranges(ranges, duration_ms)
            if ranges:
                logger.info(f"上传音频VAD切分完成: {len(ranges)} 段")
                return ranges
    except Exception as e:
        logger.warning(f"上传音频VAD切分失败，改用能量切分: {e}")

    try:
        import librosa
        import numpy as np

        audio_data, sample_rate = sf.read(audio_path, dtype='float32', always_2d=False)
        if getattr(audio_data, 'ndim', 1) > 1:
            audio_data = np.mean(audio_data, axis=1)
        intervals = librosa.effects.split(
            audio_data,
            top_db=float(os.getenv('UPLOAD_SPEAKER_SEGMENT_TOP_DB', '32')),
            frame_length=2048,
            hop_length=512,
        )
        ranges = [
            (int(start * 1000 / sample_rate), int(end * 1000 / sample_rate))
            for start, end in intervals
        ]
        ranges = _postprocess_uploaded_speech_ranges(ranges, duration_ms)
        if ranges:
            logger.info(f"上传音频能量切分完成: {len(ranges)} 段")
            return ranges
    except Exception as e:
        logger.warning(f"上传音频能量切分失败，将按固定短段兜底: {e}")

    return _postprocess_uploaded_speech_ranges([(0, duration_ms)], duration_ms)


def _recognize_uploaded_audio_piece(
    upload_asr_model,
    audio_path: str,
    server_state,
    language: str,
    hotword_text: str
) -> str:
    args = getattr(server_state, 'args', None)
    asr_params = {
        "cache": {},
        "batch_size_s": min(30, getattr(args, 'upload_asr_batch_size_s', 60)),
        "language": language or getattr(args, 'upload_asr_language', 'zh'),
        "use_itn": True,
    }
    if hotword_text:
        asr_params["hotword"] = hotword_text

    audio_input = _load_uploaded_asr_input(audio_path)
    raw_result = _generate_uploaded_asr_chunk(upload_asr_model, audio_input, asr_params)
    if not raw_result:
        return ""
    rec_result = raw_result[0]
    text = rec_result.get("text") or ""
    if not text and rec_result.get("sentence_info"):
        text = "".join(item.get("text", "") for item in rec_result.get("sentence_info") or [])
    return _clean_sentence_text(_clean_asr_text(text, server_state))


def _build_uploaded_vad_sensevoice_diarization_segments(
    audio_path: str,
    server_state,
    language: str,
    hotword_text: str,
    expected_speakers: Optional[int],
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    rec_result: Optional[Dict[str, Any]] = None,
    progress_callback=None
) -> List[Dict[str, Any]]:
    try:
        from ..speaker.speaker_verification import extract_embedding
    except Exception as e:
        logger.warning(f"上传音频声纹聚类依赖不可用，跳过VAD分段说话人分离: {e}")
        return []

    rec_text = _clean_sentence_text((rec_result or {}).get("text", ""))
    ranges = _detect_uploaded_speech_ranges(audio_path, server_state)
    speaker_sample_ranges = _sample_uploaded_speech_ranges_for_speaker(ranges)
    if len(ranges) < 2:
        if ranges and rec_text:
            logger.warning("上传音频VAD只产出一个语音段，按单说话人保留时间戳分段")
            return _build_uploaded_segments_from_speaker_ranges_text(
                [{"speaker": "说话人1", "start_ms": ranges[0][0], "end_ms": ranges[0][1]}],
                rec_text
            )
        logger.warning("上传音频VAD未产出足够语音段，无法做说话人分离")
        return []

    speaker_range_items = []
    embeddings = []
    temp_paths = []
    try:
        total_ranges = len(speaker_sample_ranges)
        progress_stride = max(1, total_ranges // 20)
        for index, (start_ms, end_ms) in enumerate(speaker_sample_ranges):
            if progress_callback and index % progress_stride == 0:
                progress = 80 + int((index / max(1, total_ranges)) * 5)
                progress_callback("speaker", max(80, min(85, progress)))

            segment_audio_path = _write_audio_segment(audio_path, start_ms, end_ms)
            if not segment_audio_path:
                continue
            temp_paths.append(segment_audio_path)

            try:
                embedding = extract_embedding(segment_audio_path)
            except Exception as e:
                logger.warning(f"上传音频VAD片段声纹提取失败 {start_ms}-{end_ms}ms: {e}")
                continue

            embeddings.append(embedding)
            speaker_range_items.append({
                "start_ms": start_ms,
                "end_ms": end_ms,
            })

        if len(embeddings) < 2:
            logger.warning(
                f"上传音频声纹有效样本不足: ranges={len(ranges)}, embeddings={len(embeddings)}，"
                "按VAD时间段和单说话人兜底"
            )
            speaker_ranges = [
                {"speaker": "说话人1", "start_ms": start_ms, "end_ms": end_ms}
                for start_ms, end_ms in ranges
            ]
            return _build_uploaded_segments_from_speaker_ranges_text(speaker_ranges, rec_text)

        if progress_callback:
            progress_callback("speaker", 85)
        labels = _cluster_uploaded_speaker_windows(
            embeddings,
            expected_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers
        )
        cluster_order: Dict[int, str] = {}
        speaker_ranges = []
        for item, label in zip(speaker_range_items, labels):
            label = int(label)
            if label not in cluster_order:
                cluster_order[label] = f"说话人{len(cluster_order) + 1}"
            speaker_ranges.append({
                "speaker": cluster_order[label],
                "start_ms": item["start_ms"],
                "end_ms": item["end_ms"],
            })
        if len(speaker_ranges) < len(ranges):
            speaker_ranges = _assign_sampled_speakers_to_all_ranges(ranges, speaker_ranges)
            logger.info(
                "上传音频说话人聚类使用抽样声纹，最终分段已恢复完整VAD覆盖: "
                f"sampled_ranges={len(speaker_range_items)}, full_ranges={len(speaker_ranges)}"
            )

        timed_asr_segments = [
            segment for segment in _extract_asr_segments(rec_result or {})
            if segment.get("text") and segment.get("start_ms") is not None and segment.get("end_ms") is not None
        ]
        if timed_asr_segments:
            if progress_callback:
                progress_callback("speaker", 86)
            logger.info(
                "上传音频VAD声纹分离仅用于说话人标注，保留整文件SenseVoice句子与标点: "
                f"asr_segments={len(timed_asr_segments)}, speaker_ranges={len(speaker_ranges)}"
            )
            return _build_uploaded_segments_from_asr_speaker_ranges(timed_asr_segments, speaker_ranges)

        upload_asr_model = getattr(server_state, 'model_asr_upload', None) if server_state is not None else None
        recognition_ranges = speaker_ranges
        if upload_asr_model is not None:
            recognition_ranges = _merge_uploaded_speaker_ranges_for_piece_asr(speaker_ranges)
            if len(recognition_ranges) < len(speaker_ranges):
                logger.info(
                    "上传音频缺少ASR句级时间戳，已先合并同说话人VAD小段再逐段识别: "
                    f"speaker_ranges={len(speaker_ranges)}, piece_ranges={len(recognition_ranges)}"
                )
        fallback_segments = _build_uploaded_segments_from_speaker_ranges_text(recognition_ranges, rec_text)
        fallback_text_by_range = {
            (segment.get("speaker"), segment.get("startMs"), segment.get("endMs")): segment.get("text", "")
            for segment in fallback_segments
        }
        piece_asr_max_segments = _get_env_int('UPLOAD_SPEAKER_PIECE_ASR_MAX_SEGMENTS', 120, 1)
        if upload_asr_model is not None and rec_text and len(recognition_ranges) > piece_asr_max_segments:
            logger.warning(
                "上传音频缺少ASR句级时间戳且VAD片段较多，跳过逐片段二次ASR以避免抽样漏识别: "
                f"speaker_ranges={len(speaker_ranges)}, piece_ranges={len(recognition_ranges)}, "
                f"limit={piece_asr_max_segments}"
            )
            return fallback_segments
        segments = []
        for index, item in enumerate(recognition_ranges):
            if progress_callback and index % max(1, len(recognition_ranges) // 10) == 0:
                progress = 86 + int((index / max(1, len(recognition_ranges))) * 2)
                progress_callback("speaker", max(86, min(88, progress)))
            start_ms = item["start_ms"]
            end_ms = item["end_ms"]
            text = ""
            if upload_asr_model is not None:
                segment_audio_path = _write_audio_segment(audio_path, start_ms, end_ms)
                if segment_audio_path:
                    temp_paths.append(segment_audio_path)
                    try:
                        text = _recognize_uploaded_audio_piece(
                            upload_asr_model,
                            segment_audio_path,
                            server_state,
                            language,
                            hotword_text,
                        )
                    except Exception as e:
                        logger.warning(f"上传音频VAD片段SenseVoice识别失败 {start_ms}-{end_ms}ms: {e}")
            if not text:
                text = fallback_text_by_range.get((item["speaker"], start_ms, end_ms), "")
            if not text:
                logger.warning(f"上传音频VAD片段无文本，跳过 {start_ms}-{end_ms}ms")
                text = ""
            if not text:
                continue
            segments.append({
                "speaker": item["speaker"],
                "speaker_type": "dynamic",
                "speaker_confidence": 0.0,
                "speaker_result": None,
                "text": text,
                "mode": "uploaded-audio",
                "timestamp": [[start_ms, end_ms]],
                "startTime": _format_ms(start_ms),
                "endTime": _format_ms(end_ms),
                "startMs": start_ms,
                "endMs": end_ms,
            })
        if segments:
            return segments
        logger.warning("上传音频VAD声纹聚类已完成但未产出文本，按整段文本时间比例兜底")
        return _build_uploaded_segments_from_speaker_ranges_text(speaker_ranges, rec_text)
    except Exception as e:
        logger.warning(f"上传音频VAD+SenseVoice说话人分离失败: {e}", exc_info=True)
        return []
    finally:
        from ..audio.audio_format_handler import cleanup_temp_file
        for temp_path in temp_paths:
            cleanup_temp_file(temp_path)


def _build_uploaded_embedding_diarization_segments(
    audio_path: str,
    rec_result: Dict[str, Any],
    expected_speakers: Optional[int],
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
) -> List[Dict[str, Any]]:
    try:
        import numpy as np
        import soundfile as sf
        from ..speaker.speaker_verification import extract_embedding
    except Exception as e:
        logger.warning(f"上传音频声纹聚类依赖不可用，跳过多人兜底分离: {e}")
        return []

    audio_data, sample_rate = sf.read(audio_path, dtype='float32', always_2d=False)
    if getattr(audio_data, 'ndim', 1) > 1:
        audio_data = np.mean(audio_data, axis=1)
    duration_ms = int(len(audio_data) * 1000 / sample_rate) if sample_rate else 0
    if duration_ms < UPLOAD_SPEAKER_CLUSTER_MIN_AUDIO_MS:
        return []

    window_ms = _get_env_int('UPLOAD_SPEAKER_CLUSTER_WINDOW_MS', UPLOAD_SPEAKER_CLUSTER_WINDOW_MS, 3000)
    window_ms = max(3000, min(30000, window_ms))
    min_rms = float(os.getenv('UPLOAD_SPEAKER_CLUSTER_MIN_RMS', '0.0015'))
    windows = []
    embeddings = []
    temp_paths = []

    try:
        for start_ms in range(0, duration_ms, window_ms):
            end_ms = min(duration_ms, start_ms + window_ms)
            if end_ms - start_ms < 2500:
                continue

            start_sample = max(0, int(start_ms * sample_rate / 1000))
            end_sample = min(len(audio_data), int(end_ms * sample_rate / 1000))
            piece = audio_data[start_sample:end_sample]
            if piece.size == 0:
                continue
            rms = float(np.sqrt(np.mean(np.square(piece))))
            if rms < min_rms:
                continue

            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            sf.write(temp_path, piece, sample_rate)
            temp_paths.append(temp_path)

            try:
                embedding = extract_embedding(temp_path)
            except Exception as e:
                logger.warning(f"上传音频窗口声纹提取失败 {start_ms}-{end_ms}ms: {e}")
                continue

            windows.append({"start_ms": start_ms, "end_ms": end_ms})
            embeddings.append(embedding)

        if len(embeddings) < 2:
            return []

        labels = _cluster_uploaded_speaker_windows(
            embeddings,
            expected_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers
        )
        cluster_order: Dict[int, str] = {}
        ranges = []
        for window, label in zip(windows, labels):
            label = int(label)
            if label not in cluster_order:
                cluster_order[label] = f"说话人{len(cluster_order) + 1}"
            speaker = cluster_order[label]
            if ranges and ranges[-1]["speaker"] == speaker and window["start_ms"] <= ranges[-1]["end_ms"] + 1000:
                ranges[-1]["end_ms"] = window["end_ms"]
            else:
                ranges.append({
                    "speaker": speaker,
                    "start_ms": window["start_ms"],
                    "end_ms": window["end_ms"]
                })

        texts = _split_text_by_time_ranges(rec_result.get("text", ""), [
            (item["start_ms"], item["end_ms"]) for item in ranges
        ])
        segments = []
        for item, text in zip(ranges, texts):
            segments.append({
                "speaker": item["speaker"],
                "speaker_type": "dynamic",
                "speaker_confidence": 0.0,
                "speaker_result": None,
                "text": text,
                "mode": "uploaded-audio",
                "timestamp": [[item["start_ms"], item["end_ms"]]],
                "startTime": _format_ms(item["start_ms"]),
                "endTime": _format_ms(item["end_ms"]),
                "startMs": item["start_ms"],
                "endMs": item["end_ms"],
            })
        return [segment for segment in segments if segment.get("text")]
    except Exception as e:
        logger.warning(f"上传音频声纹聚类兜底分离失败: {e}", exc_info=True)
        return []
    finally:
        from ..audio.audio_format_handler import cleanup_temp_file
        for temp_path in temp_paths:
            cleanup_temp_file(temp_path)


def _needs_uploaded_embedding_diarization(
    segments: List[Dict[str, Any]],
    expected_speakers: Optional[int],
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
) -> bool:
    expected_speakers, min_speakers, max_speakers = _normalize_upload_speaker_bounds(
        expected_speakers,
        min_speakers,
        max_speakers
    )
    speakers = {segment.get("speaker") for segment in segments if segment.get("speaker")}
    speaker_count = len(speakers)
    if expected_speakers and expected_speakers >= 2:
        return speaker_count != expected_speakers
    if min_speakers and speaker_count < min_speakers:
        return True
    if max_speakers and speaker_count > max_speakers:
        return True
    return speaker_count <= 1


def _get_uploaded_speaker_key(segment: Dict[str, Any], index: int) -> str:
    return str(segment.get("speaker_key")) if segment.get("speaker_key") is not None else f"segment_{index}"


def _rank_uploaded_voiceprint_segments(
    segments: List[Dict[str, Any]],
    sample_limit: Optional[int] = None,
    min_duration_ms: Optional[int] = None,
    max_duration_ms: Optional[int] = None
) -> List[Dict[str, Any]]:
    sample_limit = sample_limit or _get_env_int(
        'UPLOAD_VOICEPRINT_MATCH_SAMPLES',
        UPLOAD_VOICEPRINT_MATCH_SAMPLE_LIMIT,
        1
    )
    min_duration_ms = min_duration_ms or _get_env_int(
        'UPLOAD_VOICEPRINT_MIN_SAMPLE_MS',
        UPLOAD_VOICEPRINT_MIN_SAMPLE_MS,
        200
    )
    max_duration_ms = max_duration_ms or _get_env_int(
        'UPLOAD_VOICEPRINT_MAX_SAMPLE_MS',
        UPLOAD_VOICEPRINT_MAX_SAMPLE_MS,
        min_duration_ms
    )

    candidates = []
    fallback = []
    for index, segment in enumerate(segments or []):
        start_ms = _coerce_optional_ms(segment.get("start_ms") if segment.get("start_ms") is not None else segment.get("startMs"))
        end_ms = _coerce_optional_ms(segment.get("end_ms") if segment.get("end_ms") is not None else segment.get("endMs"))
        if start_ms is None or end_ms is None or end_ms <= start_ms:
            continue

        duration_ms = end_ms - start_ms
        clipped_duration_ms = min(duration_ms, max_duration_ms)
        text = _clean_sentence_text(segment.get("text", ""))
        sample = {
            "index": index,
            "start_ms": max(0, start_ms),
            "end_ms": max(0, start_ms + clipped_duration_ms),
            "duration_ms": clipped_duration_ms,
            "original_duration_ms": duration_ms,
            "text": text,
            "quality": clipped_duration_ms + min(len(text), 120) * 20
        }
        fallback.append(sample)
        if duration_ms >= min_duration_ms:
            candidates.append(sample)

    pool = candidates or fallback
    selected = sorted(pool, key=lambda item: (item["quality"], item["duration_ms"]), reverse=True)[:sample_limit]
    return sorted(selected, key=lambda item: item["start_ms"])


def _median_uploaded_scores(scores: List[float]) -> float:
    if not scores:
        return 0.0
    ordered = sorted(float(score) for score in scores)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _mean_uploaded_embeddings(embeddings: List[Any]) -> Optional[Any]:
    if not embeddings:
        return None
    try:
        import numpy as np

        arrays = []
        expected_shape = None
        for embedding in embeddings:
            if embedding is None:
                continue
            array = np.asarray(embedding, dtype='float32').reshape(-1)
            if expected_shape is None:
                expected_shape = array.shape
            if array.shape == expected_shape:
                arrays.append(array)

        if not arrays:
            return None

        mean_embedding = np.mean(np.stack(arrays, axis=0), axis=0)
        norm = np.linalg.norm(mean_embedding)
        if norm > 0:
            mean_embedding = mean_embedding / norm
        return mean_embedding
    except Exception as e:
        logger.warning(f"上传声纹样本特征聚合失败: {e}")
        return embeddings[0] if embeddings else None


def _build_uploaded_speaker_result_from_embedding(audio_embedding: Any, top_k: int = 3) -> Dict[str, Any]:
    try:
        from ..speaker.speaker_manager import _find_similar_speakers_internal, _manager_state

        if not (_manager_state.get('speaker_embeddings') or {}):
            return {
                "success": False,
                "message": "没有已注册的说话人",
                "candidates": []
            }

        similar_speakers = _find_similar_speakers_internal(audio_embedding, top_k)
        threshold = float(_manager_state.get('similarity_threshold') or 0.8)
        best_match = similar_speakers[0] if similar_speakers and similar_speakers[0].get("similarity", 0) >= threshold else None
        return {
            "success": True,
            "best_match": best_match,
            "candidates": similar_speakers,
            "threshold": threshold,
            "query_embedding_shape": getattr(audio_embedding, "shape", None)
        }
    except Exception as e:
        logger.warning(f"上传声纹样本比对失败: {e}")
        return {
            "success": False,
            "message": str(e),
            "candidates": []
        }


def _aggregate_uploaded_voiceprint_results(
    sample_results: List[Dict[str, Any]],
    top_k: int = 3
) -> Dict[str, Any]:
    sample_count = len(sample_results or [])
    if sample_count <= 0:
        return {
            "success": False,
            "message": "没有可用的上传声纹样本",
            "candidates": [],
            "sample_count": 0,
            "method": "multi_sample_upload_voiceprint"
        }

    threshold_values = [
        float(result.get("threshold"))
        for result in sample_results
        if result.get("threshold") is not None
    ]
    default_threshold = threshold_values[0] if threshold_values else 0.8
    threshold = _get_env_float('UPLOAD_VOICEPRINT_MATCH_THRESHOLD', default_threshold, 0.0)
    required_margin = _get_env_float(
        'UPLOAD_VOICEPRINT_MATCH_MARGIN',
        UPLOAD_VOICEPRINT_MATCH_MARGIN,
        0.0
    )
    min_hits = min(
        sample_count,
        _get_env_int('UPLOAD_VOICEPRINT_MATCH_MIN_HITS', UPLOAD_VOICEPRINT_MATCH_MIN_HITS, 1)
    )

    grouped: Dict[str, Dict[str, Any]] = {}
    for result in sample_results:
        seen_names = set()
        for candidate in result.get("candidates") or []:
            speaker_name = candidate.get("speaker_name")
            if not speaker_name or speaker_name in seen_names:
                continue
            seen_names.add(speaker_name)
            try:
                similarity = float(candidate.get("similarity", 0.0))
            except (TypeError, ValueError):
                similarity = 0.0

            bucket = grouped.setdefault(speaker_name, {
                "speaker_name": speaker_name,
                "speaker_info": candidate.get("speaker_info", {}),
                "scores": [],
                "hit_count": 0,
            })
            bucket["scores"].append(similarity)
            if similarity >= threshold:
                bucket["hit_count"] += 1

    if not grouped:
        message = next((result.get("message") for result in sample_results if result.get("message")), "没有已注册的说话人")
        return {
            "success": False,
            "message": message,
            "candidates": [],
            "sample_count": sample_count,
            "method": "multi_sample_upload_voiceprint"
        }

    aggregate_candidates = []
    for bucket in grouped.values():
        ranked_scores = sorted(bucket["scores"], reverse=True)
        top_scores = ranked_scores[:max(1, min(3, len(ranked_scores)))]
        similarity = _median_uploaded_scores(top_scores)
        aggregate_candidates.append({
            "speaker_name": bucket["speaker_name"],
            "similarity": float(similarity),
            "speaker_info": bucket.get("speaker_info", {}),
            "hit_count": int(bucket.get("hit_count", 0)),
            "sample_count": sample_count,
            "observed_count": len(bucket["scores"]),
            "scores": [float(score) for score in ranked_scores[:sample_count]]
        })

    aggregate_candidates.sort(
        key=lambda item: (item["similarity"], item["hit_count"], item["observed_count"]),
        reverse=True
    )
    aggregate_candidates = aggregate_candidates[:max(1, top_k)]

    best_candidate = aggregate_candidates[0]
    second_similarity = aggregate_candidates[1]["similarity"] if len(aggregate_candidates) > 1 else None
    winner_margin = (
        best_candidate["similarity"] - second_similarity
        if second_similarity is not None else 1.0
    )
    accepted = (
        best_candidate["similarity"] >= threshold and
        best_candidate["hit_count"] >= min_hits and
        winner_margin >= required_margin
    )

    return {
        "success": True,
        "best_match": best_candidate if accepted else None,
        "candidates": aggregate_candidates if accepted else [],
        "aggregate_candidates": aggregate_candidates,
        "threshold": threshold,
        "required_margin": required_margin,
        "winner_margin": float(winner_margin),
        "min_hits": min_hits,
        "accepted": accepted,
        "sample_count": sample_count,
        "method": "multi_sample_upload_voiceprint"
    }


def _identify_uploaded_speaker(audio_path: str, top_k: int = 3) -> Dict[str, Any]:
    from ..speaker.speaker_labeling import process_speaker_identification
    from ..speaker.speaker_manager import identify_speaker, init_speaker_manager
    from ..speaker.speaker_verification import extract_embedding

    audio_embedding = None
    speaker_result = None
    server_state = app.config.get('SERVER_STATE')
    init_speaker_manager(getattr(server_state, 'args', None))

    try:
        audio_embedding = extract_embedding(audio_path)
    except Exception as e:
        logger.warning(f"上传音频声纹特征提取失败: {e}")

    try:
        speaker_result = identify_speaker(audio_path, top_k=top_k)
    except Exception as e:
        logger.warning(f"上传音频声纹识别失败: {e}")
        speaker_result = {
            "success": False,
            "message": str(e),
            "candidates": []
        }

    label_result = process_speaker_identification(speaker_result, audio_embedding)
    return {
        "original_result": speaker_result,
        "label_result": label_result
    }


def _identify_uploaded_speaker_from_segments(
    audio_path: str,
    segments: List[Dict[str, Any]],
    top_k: int = 3
) -> Dict[str, Any]:
    from ..speaker.speaker_labeling import process_speaker_identification
    from ..speaker.speaker_manager import init_speaker_manager
    from ..speaker.speaker_verification import extract_embedding
    from ..audio.audio_format_handler import cleanup_temp_file

    server_state = app.config.get('SERVER_STATE')
    init_speaker_manager(getattr(server_state, 'args', None))

    samples = _rank_uploaded_voiceprint_segments(segments)
    sample_results: List[Dict[str, Any]] = []
    sample_embeddings: List[Any] = []
    temp_paths = []

    try:
        for sample in samples:
            sample_audio_path = _write_audio_segment(audio_path, sample.get("start_ms"), sample.get("end_ms"))
            if not sample_audio_path:
                continue
            temp_paths.append(sample_audio_path)

            try:
                audio_embedding = extract_embedding(sample_audio_path)
                sample_embeddings.append(audio_embedding)
                sample_result = _build_uploaded_speaker_result_from_embedding(audio_embedding, top_k=top_k)
                sample_result["sample"] = {
                    "start_ms": sample.get("start_ms"),
                    "end_ms": sample.get("end_ms"),
                    "duration_ms": sample.get("duration_ms")
                }
                sample_results.append(sample_result)
            except Exception as e:
                logger.warning(f"上传声纹样本识别失败: {e}")

        if not sample_results:
            merged_audio_path = _write_audio_segments(audio_path, segments)
            if merged_audio_path:
                temp_paths.append(merged_audio_path)
            return _identify_uploaded_speaker(merged_audio_path or audio_path, top_k=top_k)

        aggregate_result = _aggregate_uploaded_voiceprint_results(sample_results, top_k=top_k)
        aggregate_result["sample_results"] = sample_results
        audio_embedding = _mean_uploaded_embeddings(sample_embeddings)
        label_result = process_speaker_identification(aggregate_result, audio_embedding)
        return {
            "original_result": aggregate_result,
            "label_result": label_result
        }
    finally:
        for temp_path in temp_paths:
            cleanup_temp_file(temp_path)


def _match_uploaded_registered_speaker_from_segments(
    audio_path: str,
    segments: List[Dict[str, Any]],
    top_k: int = 3
) -> Optional[Dict[str, Any]]:
    try:
        from ..speaker.speaker_manager import init_speaker_manager, _manager_state
        from ..speaker.speaker_verification import extract_embedding
        from ..audio.audio_format_handler import cleanup_temp_file
    except Exception as e:
        logger.warning(f"上传聚类说话人实名匹配依赖不可用: {e}")
        return None

    try:
        server_state = app.config.get('SERVER_STATE')
        init_speaker_manager(getattr(server_state, 'args', None))
    except Exception as e:
        logger.warning(f"上传聚类说话人实名匹配初始化失败: {e}")
        return None

    if not (_manager_state.get('speaker_embeddings') or {}):
        return None

    samples = _rank_uploaded_voiceprint_segments(segments)
    sample_results: List[Dict[str, Any]] = []
    temp_paths = []

    try:
        for sample in samples:
            sample_audio_path = _write_audio_segment(audio_path, sample.get("start_ms"), sample.get("end_ms"))
            if not sample_audio_path:
                continue
            temp_paths.append(sample_audio_path)

            try:
                audio_embedding = extract_embedding(sample_audio_path)
                sample_result = _build_uploaded_speaker_result_from_embedding(audio_embedding, top_k=top_k)
                sample_result["sample"] = {
                    "start_ms": sample.get("start_ms"),
                    "end_ms": sample.get("end_ms"),
                    "duration_ms": sample.get("duration_ms")
                }
                sample_results.append(sample_result)
            except Exception as e:
                logger.warning(f"上传聚类说话人实名样本匹配失败: {e}")

        if not sample_results:
            return None

        aggregate_result = _aggregate_uploaded_voiceprint_results(sample_results, top_k=top_k)
        aggregate_result["sample_results"] = sample_results
        best_match = aggregate_result.get("best_match") if aggregate_result.get("accepted") else None
        if not best_match:
            return {
                "original_result": aggregate_result,
                "label_result": {}
            }

        return {
            "original_result": aggregate_result,
            "label_result": {
                "speaker_label": best_match.get("speaker_name"),
                "speaker_type": "registered",
                "confidence": best_match.get("similarity", 0.0),
                "speaker_info": best_match.get("speaker_info", {}),
                "message": f"识别为已注册说话人: {best_match.get('speaker_name')}"
            }
        }
    finally:
        for temp_path in temp_paths:
            cleanup_temp_file(temp_path)


def _apply_uploaded_registered_voiceprints_to_segments(
    audio_path: str,
    segments: List[Dict[str, Any]],
    top_k: int = 3
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for segment in segments:
        speaker = (segment.get("speaker") or "").strip()
        if speaker:
            grouped.setdefault(speaker, []).append(segment)

    for speaker_segments in grouped.values():
        speaker_result = _match_uploaded_registered_speaker_from_segments(audio_path, speaker_segments, top_k=top_k)
        label_result = (speaker_result or {}).get("label_result") or {}
        if label_result.get("speaker_type") != "registered" or not label_result.get("speaker_label"):
            continue

        for segment in speaker_segments:
            segment["speaker"] = label_result["speaker_label"]
            segment["speaker_type"] = "registered"
            segment["speaker_confidence"] = label_result.get("confidence", 0.0)
            segment["speaker_result"] = speaker_result

    return segments


def _build_uploaded_recognition_segments(
    audio_path: str,
    rec_result: Dict[str, Any],
    enable_speaker_diarization: bool,
    top_k: int,
    enable_voiceprint_matching: bool = False
) -> List[Dict[str, Any]]:
    asr_segments = _extract_asr_segments(rec_result)
    recognition_segments = []
    speaker_cache: Dict[str, Dict[str, Any]] = {}
    fallback_labels: Dict[str, str] = {}
    speaker_segments: Dict[str, List[Dict[str, Any]]] = {}

    if enable_speaker_diarization:
        for index, segment in enumerate(asr_segments):
            speaker_key = _get_uploaded_speaker_key(segment, index)
            speaker_segments.setdefault(speaker_key, []).append(segment)

    for index, segment in enumerate(asr_segments):
        speaker_result = None
        if enable_speaker_diarization and enable_voiceprint_matching:
            speaker_key = _get_uploaded_speaker_key(segment, index)
            if speaker_key not in speaker_cache:
                speaker_cache[speaker_key] = _identify_uploaded_speaker_from_segments(
                    audio_path,
                    speaker_segments.get(speaker_key, [segment]),
                    top_k=top_k
                )
            speaker_result = speaker_cache[speaker_key]

        label_result = (speaker_result or {}).get("label_result", {})
        speaker_name = label_result.get("speaker_label", "")
        if (
            enable_speaker_diarization
            and (
                not speaker_name
                or label_result.get("speaker_type") in {"unknown", "error", None}
            )
        ):
            speaker_key = _get_uploaded_speaker_key(segment, index)
            if speaker_key not in fallback_labels:
                fallback_labels[speaker_key] = f"说话人{len(fallback_labels) + 1}"
            speaker_name = fallback_labels[speaker_key]
            label_result = {
                "speaker_label": speaker_name,
                "speaker_type": "dynamic",
                "confidence": 0.0,
                "message": "未匹配到已录入声纹，按上传音频分段分配临时说话人"
            }

        recognition_segments.append({
            "speaker": speaker_name,
            "speaker_type": label_result.get("speaker_type", "none"),
            "speaker_confidence": label_result.get("confidence", 0.0),
            "speaker_result": speaker_result,
            "text": segment.get("text", ""),
            "mode": "uploaded-audio",
            "timestamp": [[segment["start_ms"], segment["end_ms"]]] if segment.get("start_ms") is not None and segment.get("end_ms") is not None else None,
            "startTime": _format_ms(segment.get("start_ms")),
            "endTime": _format_ms(segment.get("end_ms")),
            "startMs": segment.get("start_ms"),
            "endMs": segment.get("end_ms")
        })

    return recognition_segments


def _build_uploaded_text_only_segments(rec_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "speaker": "",
            "speaker_type": "none",
            "speaker_confidence": 0.0,
            "speaker_result": None,
            "text": segment.get("text", ""),
            "mode": "uploaded-audio",
            "timestamp": [[segment["start_ms"], segment["end_ms"]]] if segment.get("start_ms") is not None and segment.get("end_ms") is not None else None,
            "startTime": _format_ms(segment.get("start_ms")),
            "endTime": _format_ms(segment.get("end_ms")),
            "startMs": segment.get("start_ms"),
            "endMs": segment.get("end_ms")
        }
        for segment in _extract_asr_segments(rec_result)
        if segment.get("text")
    ]


def _resolve_uploaded_diarization_model_path(server_state) -> Optional[str]:
    args = getattr(server_state, 'args', None) if server_state is not None else None
    if not hasattr(args, 'upload_diarization_model'):
        return None

    model_ref = getattr(args, 'upload_diarization_model', None) or UPLOAD_MODELSCOPE_DIARIZATION_MODEL_DIR
    root_dir = _project_root_dir()
    candidates: List[str] = []
    expanded = os.path.expanduser(str(model_ref))
    if os.path.isabs(expanded):
        candidates.append(expanded)
    elif expanded.startswith(".") or os.sep in expanded:
        candidates.append(os.path.abspath(os.path.join(root_dir, expanded)))
    else:
        candidates.append(os.path.join(root_dir, "models", expanded))
        candidates.append(os.path.join(root_dir, "models", str(model_ref).split("/")[-1]))

    seen = set()
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isdir(normalized) and (
            os.path.exists(os.path.join(normalized, "config.yaml"))
            or os.path.exists(os.path.join(normalized, "configuration.json"))
        ) and (
            os.path.exists(os.path.join(normalized, "model.onnx"))
            or os.path.exists(os.path.join(normalized, "model_quant.onnx"))
        ):
            return normalized
    return ""


def _get_uploaded_diarization_pipeline(server_state):
    global upload_diarization_pipeline, upload_diarization_pipeline_path

    model_path = _resolve_uploaded_diarization_model_path(server_state)
    if model_path is None:
        return None, None
    if not model_path:
        raise APIError(
            "上传人员分离ONNX模型未在本地找到，请先下载 "
            f"damo/{UPLOAD_MODELSCOPE_DIARIZATION_MODEL_DIR} 到 "
            f"models/{UPLOAD_MODELSCOPE_DIARIZATION_MODEL_DIR}",
            503
        )

    with upload_diarization_lock:
        if upload_diarization_pipeline is not None and upload_diarization_pipeline_path == model_path:
            return upload_diarization_pipeline, model_path

        try:
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks
        except Exception as e:
            raise APIError(
                "ModelScope ONNX人员分离依赖不可用，请检查 addict/datasets/modelscope 是否已安装: "
                f"{e}",
                503
            ) from e

        logger.info(f"加载上传人员分离ModelScope ONNX pipeline: {model_path}")
        upload_diarization_pipeline = pipeline(
            task=Tasks.auto_speech_recognition,
            model=model_path,
        )
        upload_diarization_pipeline_path = model_path
        return upload_diarization_pipeline, model_path


def _coerce_diarization_time_ms(value: Any, duration_seconds: Optional[float] = None) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and value:
        return _coerce_diarization_time_ms(value[0], duration_seconds)
    parsed_label = _parse_uploaded_time_label_to_ms(value)
    if parsed_label is not None:
        return parsed_label
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0:
        return None
    if duration_seconds and numeric <= float(duration_seconds) + 5:
        return int(round(numeric * 1000))
    if isinstance(value, float) and numeric < 10000:
        return int(round(numeric * 1000))
    return int(round(numeric))


def _extract_modelscope_diarization_items(result: Any) -> List[Dict[str, Any]]:
    if isinstance(result, list):
        if not result:
            return []
        if all(isinstance(item, dict) and ("text" in item or "sentence" in item) for item in result):
            return result
        result = result[0]
    if not isinstance(result, dict):
        return []

    for key in ("text_segments", "segments", "sentences", "sentence_info"):
        items = result.get(key)
        if isinstance(items, list) and items:
            return items
    return []


def _speaker_value_from_diarization_item(
    item: Dict[str, Any],
    speakers: Optional[List[Any]],
    index: int
) -> Any:
    for key in ("speaker", "spk", "speaker_id", "speakerId", "speaker_label"):
        if item.get(key) is not None:
            return item.get(key)
    if speakers and index < len(speakers):
        return speakers[index]
    return None


def _normalize_modelscope_diarization_segments(
    result: Any,
    duration_seconds: Optional[float] = None
) -> List[Dict[str, Any]]:
    result_dict = result[0] if isinstance(result, list) and result and isinstance(result[0], dict) else result
    speakers = result_dict.get("speakers") if isinstance(result_dict, dict) and isinstance(result_dict.get("speakers"), list) else None
    items = _extract_modelscope_diarization_items(result)
    if not items:
        return []

    speaker_labels: Dict[str, str] = {}
    segments: List[Dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("sentence") or item.get("value") or "").strip()
        if not text:
            continue
        timestamp = item.get("timestamp") or item.get("timestamps") or item.get("time")
        start_value = item.get("start", item.get("start_time", item.get("startTime", item.get("begin"))))
        end_value = item.get("end", item.get("end_time", item.get("endTime", item.get("finish"))))
        if isinstance(timestamp, (list, tuple)) and len(timestamp) >= 2:
            start_value = start_value if start_value is not None else timestamp[0]
            end_value = end_value if end_value is not None else timestamp[-1]
            if isinstance(end_value, (list, tuple)) and len(end_value) >= 2:
                end_value = end_value[1]

        start_ms = _coerce_diarization_time_ms(start_value, duration_seconds)
        end_ms = _coerce_diarization_time_ms(end_value, duration_seconds)
        if start_ms is not None and end_ms is not None and end_ms < start_ms:
            start_ms, end_ms = end_ms, start_ms

        speaker_value = _speaker_value_from_diarization_item(item, speakers, index)
        if speaker_value is None:
            continue
        speaker_key = str(speaker_value).strip()
        if not speaker_key:
            continue
        if speaker_key not in speaker_labels:
            speaker_labels[speaker_key] = f"说话人{len(speaker_labels) + 1}"
        speaker_name = speaker_labels[speaker_key]

        segments.append({
            "speaker": speaker_name,
            "speaker_type": "dynamic",
            "speaker_confidence": 0.0,
            "speaker_result": None,
            "text": text,
            "mode": "uploaded-audio",
            "timestamp": [[start_ms, end_ms]] if start_ms is not None and end_ms is not None else None,
            "startTime": _format_ms(start_ms),
            "endTime": _format_ms(end_ms),
            "startMs": start_ms,
            "endMs": end_ms,
            "speaker_key": speaker_key,
        })
    return segments


def _run_uploaded_modelscope_diarization(
    audio_path: str,
    server_state,
    expected_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    duration_seconds: Optional[float] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    diarization_pipeline, model_path = _get_uploaded_diarization_pipeline(server_state)
    if diarization_pipeline is None:
        return [], {}, ""

    params: Dict[str, Any] = {
        "audio_in": audio_path,
        "diarization": True,
    }
    normalized_expected, normalized_min, normalized_max = _normalize_upload_speaker_bounds(
        expected_speakers,
        min_speakers,
        max_speakers
    )
    if normalized_expected:
        params["num_speakers"] = normalized_expected
    else:
        if normalized_min:
            params["min_speakers"] = normalized_min
        if normalized_max:
            params["max_speakers"] = normalized_max

    with tempfile.TemporaryDirectory(prefix="aim-upload-diarization-") as output_dir:
        params["output_dir"] = output_dir
        try:
            result = diarization_pipeline(**params)
        except TypeError:
            fallback_params = {
                "audio_in": audio_path,
                "output_dir": output_dir,
                "diarization": True,
            }
            if normalized_expected:
                fallback_params["num_speakers"] = normalized_expected
            result = diarization_pipeline(**fallback_params)

    segments = _normalize_modelscope_diarization_segments(result, duration_seconds=duration_seconds)
    if not segments:
        raise APIError("ModelScope ONNX人员分离未返回可用的说话人片段", 502)

    text = "\n".join(
        f"{segment['speaker']}: {segment['text']}"
        for segment in segments
        if segment.get("text")
    )
    rec_result = {
        "text": _uploaded_plain_text_from_segments(segments),
        "raw_result": result,
        "timestamp": [
            segment["timestamp"][0]
            for segment in segments
            if segment.get("timestamp")
        ],
        "sentence_info": [
            {
                "text": segment.get("text", ""),
                "start": segment.get("startMs"),
                "end": segment.get("endMs"),
                "spk": segment.get("speaker_key"),
            }
            for segment in segments
        ],
        "chunk_count": 1,
        "chunked": False,
        "audio_size": os.path.getsize(audio_path) if os.path.exists(audio_path) else None,
        "display_text": text,
    }
    return segments, rec_result, model_path or ""


UPLOAD_FILLER_TRANSCRIPT_TEXT = {
    "嗯", "嗯嗯", "啊", "哦", "呃", "额", "这个", "那个", "然后", "就是"
}
def _bare_uploaded_text(value: str) -> str:
    return (value or "").strip().strip("，。！？,.!?、 ")


def _is_upload_filler_text(text: str) -> bool:
    bare = _bare_uploaded_text(text)
    return bare in UPLOAD_FILLER_TRANSCRIPT_TEXT


def _parse_uploaded_time_label_to_ms(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    parts = text.split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = [int(part) for part in parts]
    except ValueError:
        return None
    if hours < 0 or minutes < 0 or seconds < 0:
        return None
    return ((hours * 60 + minutes) * 60 + seconds) * 1000


def _uploaded_segment_time_bounds(segment: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    start_ms = _coerce_optional_ms(
        segment.get("startMs") if segment.get("startMs") is not None else segment.get("start_ms")
    )
    end_ms = _coerce_optional_ms(
        segment.get("endMs") if segment.get("endMs") is not None else segment.get("end_ms")
    )
    if start_ms is not None and end_ms is not None and end_ms > start_ms:
        return start_ms, end_ms

    timestamp = segment.get("timestamp") or segment.get("asr_timestamp")
    if isinstance(timestamp, list):
        ranges = []
        for item in timestamp:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            item_start = _coerce_optional_ms(item[0])
            item_end = _coerce_optional_ms(item[1])
            if item_start is not None and item_end is not None and item_end > item_start:
                ranges.append((item_start, item_end))
        if ranges:
            return ranges[0][0], ranges[-1][1]

    start_ms = _parse_uploaded_time_label_to_ms(segment.get("startTime") or segment.get("start_time"))
    end_ms = _parse_uploaded_time_label_to_ms(segment.get("endTime") or segment.get("end_time"))
    if start_ms is not None and end_ms is not None and end_ms > start_ms:
        return start_ms, end_ms

    return None, None


def _apply_uploaded_segment_time_bounds(segment: Dict[str, Any]) -> None:
    start_ms, end_ms = _uploaded_segment_time_bounds(segment)
    if start_ms is None or end_ms is None:
        segment["timestamp"] = None
        segment["startTime"] = None
        segment["endTime"] = None
        segment["startMs"] = None
        segment["endMs"] = None
        return

    segment["timestamp"] = [[start_ms, end_ms]]
    segment["startTime"] = _format_ms(start_ms)
    segment["endTime"] = _format_ms(end_ms)
    segment["startMs"] = start_ms
    segment["endMs"] = end_ms


def _should_keep_uploaded_segment(segment: Dict[str, Any]) -> bool:
    bare = _bare_uploaded_text(segment.get("text") or "")
    if not bare:
        return False
    return len(bare) >= 2 or bool((segment.get("speaker") or "").strip())


def _join_uploaded_text(left: str, right: str) -> str:
    left = (left or "").strip()
    right = (right or "").strip()
    if not left:
        return right
    if not right:
        return left
    return left + right


def _join_uploaded_translation(left: str, right: str) -> str:
    left = (left or "").strip()
    right = (right or "").strip()
    if not left:
        return right
    if not right:
        return left
    return f"{left} {right}"


def _merge_uploaded_segments_semantically(
    segments: List[Dict[str, Any]],
    server_state=None
) -> List[Dict[str, Any]]:
    if not segments:
        return []

    merged: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    def push_current() -> None:
        nonlocal current
        if not current:
            return
        current["text"] = (current.get("text") or "").strip()
        _apply_uploaded_segment_time_bounds(current)
        if _should_keep_uploaded_segment(current):
            merged.append(current)
        current = None

    ordered = sorted(
        segments,
        key=lambda item: (
            _uploaded_segment_time_bounds(item)[0]
            if _uploaded_segment_time_bounds(item)[0] is not None
            else 10**12
        )
    )
    for raw in ordered:
        text = _postprocess_uploaded_transcript_text(raw.get("text", ""), server_state)
        if not text:
            continue
        item = dict(raw)
        item["text"] = text
        _apply_uploaded_segment_time_bounds(item)
        filler = _is_upload_filler_text(text)
        if filler and current is None:
            continue
        if current is None:
            current = item
            continue

        same_speaker = (item.get("speaker") or "") == (current.get("speaker") or "")
        if filler and not same_speaker:
            continue
        if same_speaker:
            current["text"] = _join_uploaded_text(current.get("text") or "", text)
            current["translation"] = _join_uploaded_translation(
                current.get("translation") or "",
                item.get("translation") or ""
            )
            current_start, current_end = _uploaded_segment_time_bounds(current)
            item_start, item_end = _uploaded_segment_time_bounds(item)
            if current_start is None or (item_start is not None and item_start < current_start):
                current["startMs"] = item_start
            if current_end is None or (item_end is not None and item_end > current_end):
                current["endMs"] = item_end
            if not current.get("speaker_type") and item.get("speaker_type"):
                current["speaker_type"] = item.get("speaker_type")
            if not current.get("speaker_result") and item.get("speaker_result"):
                current["speaker_result"] = item.get("speaker_result")
            continue

        push_current()
        current = item

    push_current()
    return merged


def _run_upload_async_task(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_box = {}
    error_box = {}

    def _runner():
        try:
            result_box["value"] = asyncio.run(coro)
        except Exception as e:
            error_box["error"] = e

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_box:
        raise error_box["error"]
    return result_box.get("value")


async def _translate_uploaded_segments_async(
    plain_text: str,
    segments: List[Dict[str, Any]],
    progress_callback=None
) -> Dict[str, str]:
    from ..network import local_translation

    local_translation.initialize()
    if not local_translation.get_engine():
        if progress_callback:
            progress_callback("translation", 96)
        return {
            "translation": "",
            "plain_translation": "",
            "error": ""
        }

    translated_lines = []
    translated_parts = []
    total_segments = sum(1 for segment in segments if (segment.get("text") or "").strip())
    translated_count = 0
    for segment in segments:
        text = (segment.get("text") or "").strip()
        if not text:
            segment["translation"] = ""
            continue

        translation = await local_translation.translate(text) or ""
        translated_count += 1
        segment["translation"] = translation
        if translation:
            translated_parts.append(translation)
            translated_lines.append(
                f"{segment['speaker']}: {translation}" if segment.get("speaker") else translation
            )
        if progress_callback and total_segments > 0:
            progress = 88 + int((translated_count / total_segments) * 8)
            progress_callback("translation", max(88, min(96, progress)))

    if not translated_parts and plain_text.strip():
        if progress_callback:
            progress_callback("translation", 92)
        translation = await local_translation.translate(plain_text.strip()) or ""
        if progress_callback:
            progress_callback("translation", 96)
        return {
            "translation": translation,
            "plain_translation": translation,
            "error": ""
        }

    return {
        "translation": "\n".join(translated_lines),
        "plain_translation": " ".join(translated_parts),
        "error": ""
    }


def _translate_uploaded_segments(
    plain_text: str,
    segments: List[Dict[str, Any]],
    progress_callback=None
) -> Dict[str, str]:
    try:
        return _run_upload_async_task(
            _translate_uploaded_segments_async(
                plain_text,
                segments,
                progress_callback=progress_callback
            )
        )
    except UploadTaskCancelled:
        raise
    except Exception as e:
        logger.warning(f"上传音频翻译失败: {e}")
        return {
            "translation": "",
            "plain_translation": "",
            "error": str(e)
        }


def _recognize_uploaded_audio_file(
    saved_path: str,
    original_filename: str,
    server_state,
    language: str,
    enable_speaker_diarization: bool,
    top_k: int,
    enable_voiceprint_matching: bool = False,
    enable_translation: bool = False,
    expected_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    hotword_text: str = "",
    progress_callback=None,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    from ..audio.audio_format_handler import convert_media_to_wav, cleanup_temp_file, probe_media_info

    enable_speaker_diarization = True
    converted_temp_path = None
    recognition_audio_path = saved_path
    media_info = probe_media_info(saved_path)
    started_at = time.perf_counter()
    log_context = _build_upload_log_context(task_id, original_filename, saved_path)
    registration_audio_ref: Dict[str, Any] = {
        "source_file_name": os.path.basename(saved_path),
        "time_base": "source_audio",
        "sample_rate": media_info.get("sample_rate"),
        "channels": media_info.get("channels")
    }
    logger.info(
        f"上传音视频识别开始 {log_context}, duration={media_info.get('duration')}, size={media_info.get('size')}, "
        f"language={language}, diarization={enable_speaker_diarization}, translation={enable_translation}, "
        f"voiceprint={enable_voiceprint_matching}, top_k={top_k}, "
        f"speaker_bounds={expected_speakers}/{min_speakers}/{max_speakers}, "
        f"hotwords={len(hotword_text.split()) if hotword_text else 0}"
    )

    try:
        if progress_callback:
            progress_callback("prepare", 3)
        converted_temp_path = convert_media_to_wav(saved_path, target_sr=16000, target_channels=1)
        recognition_audio_path = converted_temp_path
        persisted_ref = _persist_uploaded_recognition_audio(saved_path, converted_temp_path)
        if persisted_ref:
            recognition_audio_path = persisted_ref["path"]
            registration_audio_ref = persisted_ref
    except UploadTaskCancelled:
        raise
    except Exception as e:
        logger.warning(f"上传音频转换为WAV失败，尝试使用原始文件识别: {e}")

    try:
        speaker_postprocess_error = ""
        speaker_segment_source = "upload_speaker_postprocess_pending"
        diarization_model_path = ""
        rec_result: Dict[str, Any] = {}
        try:
            def asr_progress(done_chunks, total_chunks):
                if progress_callback:
                    if total_chunks <= 0:
                        progress_callback("asr", 20)
                    else:
                        pct = 15 + int((done_chunks / total_chunks) * 60)
                        progress_callback("asr", max(15, min(75, pct)))

            rec_result = _run_uploaded_audio_asr(
                recognition_audio_path,
                server_state,
                language,
                hotword_text=hotword_text,
                expected_speakers=expected_speakers,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
                media_duration_seconds=media_info.get("duration"),
                progress_callback=asr_progress,
            )
            if progress_callback:
                progress_callback("speaker", 80)
            segments = _build_uploaded_text_only_segments(rec_result)
            if _has_uploaded_asr_speaker_labels(rec_result):
                integrated_segments = _build_uploaded_recognition_segments(
                    recognition_audio_path,
                    rec_result,
                    enable_speaker_diarization,
                    top_k=top_k,
                    enable_voiceprint_matching=enable_voiceprint_matching
                )
                if integrated_segments:
                    segments = integrated_segments
                    speaker_segment_source = "funasr_sentence_info_spk"
                    if progress_callback:
                        progress_callback("speaker", 88)
                else:
                    raise APIError("FunASR官网内置人员分离未生成可用的说话人文本片段", 502)
            else:
                raise APIError("FunASR官网内置人员分离未返回sentence_info.spk，请检查cam++是否加载成功", 502)
        except UploadTaskCancelled:
            raise
        except Exception as e:
            speaker_postprocess_error = str(e)
            if enable_speaker_diarization:
                raise
            if not rec_result:
                raise
            speaker_segment_source = "text_only_fallback"
            logger.warning(f"上传音频说话人/声纹后处理失败，保留整文件转写结果: {e}")
            segments = _build_uploaded_text_only_segments(rec_result)

        plain_text = _uploaded_plain_text_from_segments(segments) or _postprocess_uploaded_transcript_text(
            rec_result.get("text", ""),
            server_state
        )
        correction_result = _apply_uploaded_result_corrections({
            "segments": segments,
            "plain_text": plain_text,
            "asr_metadata": {}
        })
        segments = correction_result.get("segments") or segments
        plain_text = correction_result.get("plain_text") or plain_text
        text_correction_metadata = correction_result.get("asr_metadata") or {}

        text_content = "\n".join(
            f"{segment['speaker']}: {segment['text']}" if segment.get("speaker") else segment["text"]
            for segment in segments
            if segment.get("text")
        )
        translation_payload = {
            "translation": "",
            "plain_translation": "",
            "error": ""
        }
        if enable_translation:
            if progress_callback:
                progress_callback("translation", 88)
            translation_payload = _translate_uploaded_segments(
                plain_text,
                segments,
                progress_callback=progress_callback
            )
        translation_postprocess_error = translation_payload.get("error", "")

        primary_segment = next((segment for segment in segments if segment.get("speaker")), None)
        speaker_result = primary_segment.get("speaker_result") if primary_segment else None
        speaker_count = len({segment.get("speaker") for segment in segments if segment.get("speaker")})
        has_segment_timestamp = any(
            segment.get("timestamp") or (
                segment.get("startMs") is not None and segment.get("endMs") is not None
            )
            for segment in segments
        )
        asr_metadata = {
            "mode": "uploaded-sensevoice",
            "model": getattr(getattr(server_state, 'args', None), 'upload_asr_model', 'iic/SenseVoiceSmall'),
            "sentence_count": len(rec_result.get("sentence_info") or []),
            "has_timestamp": bool(rec_result.get("timestamp")) or has_segment_timestamp,
            "has_translation": bool(translation_payload.get("translation")),
            "speaker_diarization_enabled": enable_speaker_diarization,
            "voiceprint_matching_enabled": enable_voiceprint_matching,
            "speaker_segment_source": speaker_segment_source,
            "speaker_count": speaker_count,
            "diarization_model": diarization_model_path or None,
            "speaker_postprocess_failed": bool(speaker_postprocess_error),
            "speaker_postprocess_error": speaker_postprocess_error or None,
            "translation_enabled": enable_translation,
            "translation_postprocess_failed": bool(translation_postprocess_error),
            "translation_postprocess_error": translation_postprocess_error or None,
            "chunk_count": rec_result.get("chunk_count", 1),
            "chunked": rec_result.get("chunked", False),
            "audio_size": rec_result.get("audio_size"),
            "expected_speakers": expected_speakers,
            "min_speakers": min_speakers,
            "max_speakers": max_speakers,
            "hotword_count": len(hotword_text.split()) if hotword_text else 0
        }
        asr_metadata.update(text_correction_metadata)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            f"上传音视频识别完成 {log_context}, duration_ms={duration_ms}, segments={len(segments)}, "
            f"speaker_count={speaker_count}, translation={bool(translation_payload.get('translation'))}, "
            f"segment_source={speaker_segment_source}, chunk_count={asr_metadata.get('chunk_count')}, "
            f"text_corrections={text_correction_metadata.get('text_correction_count', 0)}"
        )

        return {
            "file_name": original_filename,
            "mode": "uploaded-sensevoice",
            "text": text_content or plain_text,
            "plain_text": plain_text,
            "translation": translation_payload.get("translation", ""),
            "plain_translation": translation_payload.get("plain_translation", ""),
            "translation_enabled": enable_translation,
            "confidence": rec_result.get("confidence"),
            "language": language,
            "speaker_name": primary_segment.get("speaker") if primary_segment else "",
            "speaker_type": primary_segment.get("speaker_type") if primary_segment else "none",
            "speaker_confidence": primary_segment.get("speaker_confidence") if primary_segment else 0.0,
            "speaker_result": speaker_result,
            "segments": segments,
            "timestamp": rec_result.get("timestamp"),
            "registration_audio": _public_registration_audio_ref(registration_audio_ref),
            "source_audio": {
                "file_name": original_filename,
                "saved_file_name": os.path.basename(saved_path),
                "duration": media_info.get("duration"),
                "format": media_info.get("format"),
                "codec": media_info.get("codec"),
                "size": media_info.get("size")
            },
            "asr_metadata": asr_metadata
        }
    finally:
        if converted_temp_path:
            cleanup_temp_file(converted_temp_path)


def _parse_upload_recognition_options() -> Dict[str, Any]:
    try:
        top_k = int(request.form.get('speaker_top_k', 3))
    except (TypeError, ValueError):
        top_k = 3
    top_k = max(1, min(10, top_k))

    expected_speakers, min_speakers, max_speakers = _parse_upload_speaker_bounds(
        request.form.get('expected_speakers'),
        request.form.get('min_speakers'),
        request.form.get('max_speakers')
    )

    return {
        "language": request.form.get('language', 'zh'),
        "enable_speaker_diarization": True,
        "enable_voiceprint_matching": _get_request_bool('enable_voiceprint_matching', False),
        "enable_translation": _get_request_bool('enable_translation', False),
        "speaker_top_k": top_k,
        "expected_speakers": expected_speakers,
        "min_speakers": min_speakers,
        "max_speakers": max_speakers,
        "hotword_text": _build_upload_hotword_text(
            request.form.get('hotwords'),
            _get_request_bool('include_default_hotwords', True)
        ),
    }


def _validate_upload_audio_file() -> Tuple[Any, str]:
    if 'file' not in request.files:
        raise APIError("请上传音频或视频文件", 400)

    audio_file = request.files['file']
    if not audio_file or not audio_file.filename:
        raise APIError("音视频文件不能为空", 400)

    original_filename = secure_filename(audio_file.filename)
    if not original_filename:
        original_filename = f"audio_{uuid.uuid4().hex}.wav"

    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_RECOGNITION_AUDIO_EXTENSIONS:
        raise APIError(
            f"不支持的音视频格式: {ext or '未知'}，支持: {', '.join(sorted(ALLOWED_RECOGNITION_AUDIO_EXTENSIONS))}",
            400
        )
    return audio_file, original_filename


def _run_upload_audio_task(task_id: str) -> None:
    row = _get_upload_task_row(task_id)
    if not row:
        return
    if row.get("status") == "cancelled":
        return
    progress_log_state = {
        "stage": None,
        "bucket": None,
    }

    def update_stage(stage: str, progress: int) -> None:
        if not _update_upload_task_if_active(task_id, status="running", stage=stage, progress=progress):
            raise UploadTaskCancelled("上传识别任务已取消")
        progress_bucket = max(0, int(progress)) // 10
        if (
            stage != progress_log_state["stage"]
            or progress_bucket != progress_log_state["bucket"]
            or progress in {0, 100}
        ):
            logger.info(
                f"上传音视频识别进度 task_id={task_id}, file={row.get('file_name')}, "
                f"stage={stage}, progress={progress}%"
            )
            progress_log_state["stage"] = stage
            progress_log_state["bucket"] = progress_bucket

    try:
        logger.info(
            f"上传音视频识别任务开始 task_id={task_id}, file={row.get('file_name')}, "
            f"language={row.get('language') or 'zh'}, diarization={bool(row.get('enable_speaker_diarization'))}, "
            f"voiceprint={bool(row.get('enable_voiceprint_matching'))}, "
            f"translation={bool(row.get('enable_translation'))}, top_k={int(row.get('speaker_top_k') or 3)}, "
            f"speaker_bounds={row.get('expected_speakers')}/{row.get('min_speakers')}/{row.get('max_speakers')}"
        )
        update_stage("正在准备音视频文件", 2)
        server_state = app.config.get('SERVER_STATE')
        hotword_text = row.get("hotword_text") or _build_upload_hotword_text()
        result = _recognize_uploaded_audio_file(
            saved_path=row["saved_path"],
            original_filename=row["file_name"],
            server_state=server_state,
            language=row.get("language") or "zh",
            enable_speaker_diarization=bool(row.get("enable_speaker_diarization")),
            enable_voiceprint_matching=bool(row.get("enable_voiceprint_matching")),
            top_k=int(row.get("speaker_top_k") or 3),
            enable_translation=bool(row.get("enable_translation")),
            expected_speakers=row.get("expected_speakers"),
            min_speakers=row.get("min_speakers"),
            max_speakers=row.get("max_speakers"),
            hotword_text=hotword_text,
            progress_callback=update_stage,
            task_id=task_id,
        )
        _raise_if_upload_task_cancelled(task_id)
        result["task_id"] = task_id
        registration_audio = result.get("registration_audio") or {}
        _update_upload_task_if_active(
            task_id,
            recognition_file_name=registration_audio.get("file_name"),
            recognition_path=os.path.join(_get_uploaded_recognition_audio_dir(), registration_audio["file_name"])
            if registration_audio.get("file_name") else None,
        )
        _complete_upload_task(task_id, result)
    except UploadTaskCancelled:
        logger.info(f"上传音视频识别任务已取消 task_id={task_id}")
    except Exception as e:
        if _is_upload_task_cancelled(task_id):
            logger.info(f"上传音视频识别任务已取消 task_id={task_id}")
            return
        logger.error(f"上传音视频识别任务失败 task_id={task_id}: {e}", exc_info=True)
        _update_upload_task_if_active(
            task_id,
            status="failed",
            progress=100,
            stage="上传识别失败",
            error=str(e),
            completed_at=_get_upload_task_timestamp(),
        )


def _submit_upload_task(task_id: str) -> None:
    future = upload_task_executor.submit(_run_upload_audio_task, task_id)
    with upload_task_futures_lock:
        upload_task_futures[task_id] = future

    def cleanup_upload_future(_):
        with upload_task_futures_lock:
            upload_task_futures.pop(task_id, None)

    future.add_done_callback(cleanup_upload_future)


def _create_upload_task_from_request() -> Dict[str, Any]:
    audio_file, original_filename = _validate_upload_audio_file()
    options = _parse_upload_recognition_options()
    saved_filename, saved_path, saved_size = _save_uploaded_recognition_file(audio_file, original_filename)
    try:
        from ..audio.audio_format_handler import probe_media_info
        media_info = probe_media_info(saved_path)
    except Exception:
        media_info = {"size": os.path.getsize(saved_path), "format": os.path.splitext(saved_path)[1].lower().lstrip(".")}

    task_id = _create_upload_task(
        file_name=original_filename,
        saved_file_name=saved_filename,
        saved_path=saved_path,
        language=options["language"],
        enable_speaker_diarization=options["enable_speaker_diarization"],
        enable_voiceprint_matching=options["enable_voiceprint_matching"],
        enable_translation=options["enable_translation"],
        speaker_top_k=options["speaker_top_k"],
        expected_speakers=options["expected_speakers"],
        min_speakers=options["min_speakers"],
        max_speakers=options["max_speakers"],
        hotword_text=options["hotword_text"],
        media_info=media_info,
    )
    _submit_upload_task(task_id)
    row = _get_upload_task_row(task_id)
    logger.info(
        f"已创建上传音视频识别任务 task_id={task_id}, file={original_filename}, saved_file={saved_filename}, "
        f"size={media_info.get('size') or saved_size}, language={options['language']}, "
        f"diarization={options['enable_speaker_diarization']}, voiceprint={options['enable_voiceprint_matching']}, "
        f"translation={options['enable_translation']}, "
        f"top_k={options['speaker_top_k']}, "
        f"speaker_bounds={options['expected_speakers']}/{options['min_speakers']}/{options['max_speakers']}, "
        f"hotwords={len((options['hotword_text'] or '').split())}"
    )
    return _upload_task_payload(row)


def _recover_upload_audio_tasks() -> None:
    rows = db.execute_query(
        "SELECT task_id FROM uploaded_audio_tasks WHERE status IN ('queued', 'running') ORDER BY created_at"
    )
    if not UPLOAD_RECOVER_PENDING_TASKS:
        timestamp = _get_upload_task_timestamp()
        for row in rows:
            task_id = row["task_id"]
            _update_upload_task(
                task_id,
                status="failed",
                progress=100,
                stage="服务重启，已取消未完成的上传识别任务",
                error="服务重启后已取消未完成的上传识别任务，请重新上传",
                completed_at=timestamp,
            )
        if rows:
            logger.info(f"服务重启后已取消 {len(rows)} 个未完成的上传识别任务")
        return

    for row in rows:
        task_id = row["task_id"]
        _update_upload_task(task_id, status="queued", progress=0, stage="服务恢复后重新排队", error=None)
        _submit_upload_task(task_id)


def _rebuild_uploaded_result_text(result: Dict[str, Any]) -> Dict[str, Any]:
    segments = result.get("segments") or []
    result["text"] = "\n".join(
        f"{segment.get('speaker')}: {segment.get('text')}" if segment.get("speaker") else segment.get("text", "")
        for segment in segments
        if segment.get("text")
    ).strip()
    return result


def _save_upload_result_for_task(task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    result = _rebuild_uploaded_result_text(result)
    _persist_uploaded_task_segments(task_id, result.get("segments") or [])
    _update_upload_task(task_id, result_json=json.dumps(result, ensure_ascii=False))
    return result


def _get_completed_upload_result(task_id: str) -> Dict[str, Any]:
    row = _get_upload_task_row(task_id)
    if not row:
        raise APIError("上传识别任务不存在", 404)
    result = _safe_json_loads(row.get("result_json"), None)
    if not result:
        raise APIError("上传识别结果尚未完成", 409)
    return result


def _uploaded_speaker_sample_quality(segment: Dict[str, Any]) -> str:
    duration_ms = max(0, int((segment.get("endMs") or 0) - (segment.get("startMs") or 0)))
    text = _clean_sentence_text(segment.get("text", ""))
    if 5000 <= duration_ms <= 40000 and len(text) >= 8:
        return "good"
    if duration_ms >= 2000 and len(text) >= 4:
        return "usable"
    return "short"


def _rank_uploaded_speaker_candidate_rows(
    rows: List[Tuple[int, Dict[str, Any]]],
    limit: int = 4
) -> List[Tuple[int, Dict[str, Any]]]:
    rank = {"good": 3, "usable": 2, "short": 1}
    return sorted(
        rows,
        key=lambda item: (
            rank.get(_uploaded_speaker_sample_quality(item[1]), 0),
            min(max(0, int((item[1].get("endMs") or 0) - (item[1].get("startMs") or 0))), 18000),
            len(_clean_sentence_text(item[1].get("text", ""))),
        ),
        reverse=True,
    )[:limit]


def _speaker_candidate_rows_from_result(task_id: str, result: Dict[str, Any]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
    for index, segment in enumerate(result.get("segments") or []):
        speaker = (segment.get("speaker") or "").strip() or "未命名"
        grouped.setdefault(speaker, []).append((index, segment))

    candidates = []
    for speaker, rows in grouped.items():
        total_duration_ms = sum(
            max(0, int((segment.get("endMs") or 0) - (segment.get("startMs") or 0)))
            for _, segment in rows
        )
        sample_rows = _rank_uploaded_speaker_candidate_rows(rows, limit=4)
        candidates.append({
            "speaker": speaker,
            "display_name": speaker,
            "segment_count": len(rows),
            "total_duration_ms": total_duration_ms,
            "total_duration_label": _format_ms(total_duration_ms),
            "sample_segments": [
                {
                    "index": index,
                    "speaker": speaker,
                    "text": segment.get("text", ""),
                    "start_ms": segment.get("startMs"),
                    "end_ms": segment.get("endMs"),
                    "start_label": segment.get("startTime"),
                    "duration_ms": max(0, int((segment.get("endMs") or 0) - (segment.get("startMs") or 0))),
                    "quality": _uploaded_speaker_sample_quality(segment),
                    "audio_url": f"/api/upload/audio/tasks/{task_id}/segments/{index}/audio",
                }
                for index, segment in sample_rows
            ],
        })
    return sorted(candidates, key=lambda item: item["total_duration_ms"], reverse=True)


# ============================================================================
# 会议管理API
# ============================================================================

@app.route('/api/meetings', methods=['POST'])
@handle_database_error
def create_meeting():
    """创建会议"""
    # 支持JSON格式的请求
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)

    title = data.get('title')
    file_name = data.get('fileName')

    if not title:
        raise APIError("会议标题不能为空", 400)
    
    if not file_name:
        raise APIError("文件名不能为空", 400)
    
    # 创建会议记录
    meeting_id = db.create_meeting(title, file_name)
    
    # 保存音频文件元数据（如果提供）
    if data.get('audioFile'):
        audio_info = data['audioFile']
        db.save_audio_file(
            meeting_id=meeting_id,
            file_name=audio_info.get('fileName'),
            file_path=audio_info.get('filePath'),  # 客户端路径
            file_size=audio_info.get('fileSize'),
            duration=audio_info.get('duration'),
            format=audio_info.get('format', 'wav')
        )
    
    # 保存转录内容元数据（如果提供）
    if data.get('transcriptionContent'):
        transcription_info = data['transcriptionContent']
        # 这里可以保存转录文档的元数据
        # 实际内容由前端保存为md文件
        pass
    
    # 保存会议纪要元数据（如果提供）
    if data.get('meetingMinutes'):
        minutes_info = data['meetingMinutes']
        # 这里可以保存会议纪要文档的元数据
        # 实际内容由前端保存为md文件
        pass
    
    return create_response({
        "meeting_id": meeting_id,
        "title": title,
        "fileName": file_name
    }, "会议创建成功", 201)


@app.route('/api/meetings', methods=['GET'])
@handle_database_error
def get_meetings_list():
    """获取会议列表"""
    try:
        # 获取所有会议
        meetings = db.get_all_meetings()
        
        meetings_data = []
        for meeting in meetings:
            meeting_dict = dict(meeting)
            meeting_id = meeting_dict['id']
            
            # 获取会议的音频文件元数据
            audio_files = db.get_meeting_audio_files(meeting_id)
            meeting_dict['audioFiles'] = [dict(af) for af in audio_files]
            
            # 标记是否有转录内容和会议纪要（基于文件路径判断）
            meeting_dict['hasTranscription'] = False  # 前端根据本地文件判断
            meeting_dict['hasMinutes'] = False  # 前端根据本地文件判断
            
            # 计算会议时长（如果有结束时间）
            if meeting_dict.get('end_time'):
                start_time = datetime.fromisoformat(meeting_dict['start_time'])
                end_time = datetime.fromisoformat(meeting_dict['end_time'])
                duration = end_time - start_time
                meeting_dict['duration'] = str(duration).split('.')[0]  # 去掉微秒
            else:
                meeting_dict['duration'] = '进行中'
            
            meetings_data.append(meeting_dict)
        
        paged_meetings, pagination = _paginate_items(meetings_data)
        if pagination:
            return create_response({
                'meetings': paged_meetings,
                **pagination
            }, "获取会议列表成功")
        return create_response(meetings_data, "获取会议列表成功")
    except Exception as e:
        logger.error(f"获取会议列表失败: {e}")
        raise APIError(f"获取会议列表失败: {str(e)}", 500)


@app.route('/api/meetings/<int:meeting_id>', methods=['GET'])
@handle_database_error
def get_meeting(meeting_id: int):
    """获取会议详情"""
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise APIError("会议不存在", 404)
    
    meeting_dict = dict(meeting)
    
    # 获取会议的音频文件元数据
    audio_files = db.get_meeting_audio_files(meeting_id)
    meeting_dict['audioFiles'] = [dict(af) for af in audio_files]
    
    # 标记是否有转录内容和会议纪要（前端根据本地文件判断）
    meeting_dict['hasTranscription'] = False
    meeting_dict['hasMinutes'] = False
    transcription_source, upload_task_id = _get_meeting_transcription_source(meeting_id)
    meeting_dict['transcription_source'] = transcription_source
    meeting_dict['recognitionMode'] = 'upload' if transcription_source == 'upload' else 'realtime'
    if upload_task_id:
        meeting_dict['uploadTaskId'] = upload_task_id
    
    return create_response(meeting_dict, "获取会议详情成功")


@app.route('/api/meetings/<int:meeting_id>/uploaded-transcription', methods=['GET'])
@handle_database_error
def get_meeting_uploaded_transcription(meeting_id: int):
    """获取保存后关联到会议的上传转写片段，和实时转写表保持隔离。"""
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise APIError("会议不存在", 404)

    rows = _get_meeting_uploaded_segment_rows(meeting_id)
    segments = [_uploaded_segment_row_to_response(row) for row in rows]
    task_ids = []
    file_names = []
    for row in rows:
        task_id = row["task_id"]
        if task_id and task_id not in task_ids:
            task_ids.append(task_id)
        task_file_name = row["task_file_name"] or row["task_saved_file_name"]
        if task_file_name and task_file_name not in file_names:
            file_names.append(task_file_name)

    text = _uploaded_segments_to_markdown(segments)
    plain_text = "\n".join(
        (segment.get("text") or "").strip()
        for segment in segments
        if (segment.get("text") or "").strip()
    )

    return create_response({
        "meeting_id": meeting_id,
        "source": "upload" if segments else "realtime",
        "task_id": task_ids[0] if task_ids else None,
        "task_ids": task_ids,
        "file_names": file_names,
        "segments": segments,
        "text": text,
        "plain_text": plain_text,
    }, "获取上传转写回显成功")


@app.route('/api/meetings/<int:meeting_id>', methods=['DELETE'])
@handle_database_error
def delete_meeting(meeting_id: int):
    """删除会议"""
    # 检查会议是否存在
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise APIError("会议不存在", 404)
    
    try:
        # 删除数据库中的会议记录（级联删除相关数据）
        db.delete_meeting(meeting_id)
        
        return create_response({"meeting_id": meeting_id}, "会议删除成功")
    except Exception as e:
        logger.error(f"删除会议失败: {e}")
        raise APIError(f"删除会议失败: {str(e)}", 500)





@app.route('/api/meetings/<int:meeting_id>/end', methods=['PUT'])
@handle_database_error
def end_meeting(meeting_id: int):
    """结束会议"""
    affected_rows = db.end_meeting(meeting_id)
    if affected_rows == 0:
        raise APIError("会议不存在或已结束", 404)
    
    return create_response({"meeting_id": meeting_id}, "会议已结束")


# ============================================================================
# 音频文件管理API
# ============================================================================

@app.route('/api/meetings/<int:meeting_id>/audio-files', methods=['POST'])
@handle_database_error
def upload_audio_file(meeting_id: int):
    """上传音频文件"""
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    required_fields = ['file_name', 'file_path']
    for field in required_fields:
        if not data.get(field):
            raise APIError(f"{field} 不能为空", 400)
    
    audio_id = db.save_audio_file(
        meeting_id=meeting_id,
        file_name=data['file_name'],
        file_path=data['file_path'],
        file_size=data.get('file_size'),
        duration=data.get('duration'),
        format=data.get('format'),
        sample_rate=data.get('sample_rate'),
        channels=data.get('channels')
    )
    
    return create_response({
        "audio_id": audio_id,
        "meeting_id": meeting_id,
        "file_name": data['file_name']
    }, "音频文件上传成功", 201)


@app.route('/api/meetings/<int:meeting_id>/audio-files', methods=['GET'])
@handle_database_error
def get_meeting_audio_files(meeting_id: int):
    """获取会议的所有音频文件"""
    audio_files = db.get_meeting_audio_files(meeting_id)
    audio_list = [dict(audio) for audio in audio_files]
    
    return create_response({
        "meeting_id": meeting_id,
        "audio_files": audio_list,
        "count": len(audio_list)
    }, "获取音频文件列表成功")


@app.route('/api/audio-files/<int:audio_id>', methods=['GET'])
@handle_database_error
def get_audio_file(audio_id: int):
    """获取音频文件信息"""
    audio_file = db.get_audio_file(audio_id)
    if not audio_file:
        raise APIError("音频文件不存在", 404)
    
    return create_response(dict(audio_file), "获取音频文件信息成功")


@app.route('/api/audio-files/<int:audio_id>', methods=['DELETE'])
@handle_database_error
def delete_audio_file(audio_id: int):
    """删除音频文件"""
    affected_rows = db.delete_audio_file(audio_id)
    if affected_rows == 0:
        raise APIError("音频文件不存在", 404)
    
    return create_response({"audio_id": audio_id}, "音频文件删除成功")


@app.route('/api/upload/audio/recognize', methods=['POST'])
@handle_database_error
def recognize_uploaded_audio():
    """上传音视频文件并执行识别。

    默认保持旧同步行为；传 async_task=true 时立即返回任务ID，前端轮询结果。
    """
    if _get_request_bool('async_task', False):
        task = _create_upload_task_from_request()
        return create_response(task, "上传音视频识别任务已创建", 202)

    audio_file, original_filename = _validate_upload_audio_file()
    options = _parse_upload_recognition_options()
    server_state = app.config.get('SERVER_STATE')
    saved_filename, saved_path, saved_size = _save_uploaded_recognition_file(audio_file, original_filename)
    logger.info(
        f"收到同步上传音视频识别请求 file={original_filename}, saved_file={saved_filename}, size={saved_size}, "
        f"language={options['language']}, diarization={options['enable_speaker_diarization']}, "
        f"voiceprint={options['enable_voiceprint_matching']}, "
        f"translation={options['enable_translation']}, top_k={options['speaker_top_k']}, "
        f"speaker_bounds={options['expected_speakers']}/{options['min_speakers']}/{options['max_speakers']}, "
        f"hotwords={len((options['hotword_text'] or '').split())}"
    )

    try:
        result = _recognize_uploaded_audio_file(
            saved_path=saved_path,
            original_filename=original_filename,
            server_state=server_state,
            language=options["language"],
            enable_speaker_diarization=options["enable_speaker_diarization"],
            enable_voiceprint_matching=options["enable_voiceprint_matching"],
            top_k=options["speaker_top_k"],
            enable_translation=options["enable_translation"],
            expected_speakers=options["expected_speakers"],
            min_speakers=options["min_speakers"],
            max_speakers=options["max_speakers"],
            hotword_text=options["hotword_text"]
        )
    except Exception:
        if os.path.exists(saved_path):
            os.unlink(saved_path)
        raise

    return create_response(result, "上传音视频识别完成")


@app.route('/api/upload/audio/tasks', methods=['POST'])
@handle_database_error
def create_uploaded_audio_task():
    """创建上传音视频后台识别任务。"""
    task = _create_upload_task_from_request()
    return create_response(task, "上传音视频识别任务已创建", 202)


@app.route('/api/upload/audio/tasks/<task_id>', methods=['GET'])
@handle_database_error
def get_uploaded_audio_task(task_id: str):
    row = _get_upload_task_row(task_id)
    if not row:
        raise APIError("上传识别任务不存在", 404)
    return create_response(_upload_task_payload(row), "上传识别任务状态")


@app.route('/api/upload/audio/tasks/<task_id>', methods=['DELETE'])
@handle_database_error
def cancel_uploaded_audio_task(task_id: str):
    task = _cancel_upload_task(task_id)
    return create_response(task, "上传识别任务已取消")


@app.route('/api/upload/audio/tasks/<task_id>/audio', methods=['GET'])
@handle_database_error
def get_uploaded_audio_source(task_id: str):
    row = _get_upload_task_row(task_id)
    if not row:
        raise APIError("上传识别任务不存在", 404)
    if not os.path.exists(row["saved_path"]):
        raise APIError("源音视频文件不存在", 404)
    return send_file(row["saved_path"], as_attachment=False, download_name=row["file_name"])


@app.route('/api/upload/audio/tasks/<task_id>/segments/<int:segment_index>/audio', methods=['GET'])
@handle_database_error
def get_uploaded_audio_segment(task_id: str, segment_index: int):
    result = _get_completed_upload_result(task_id)
    row = _get_upload_task_row(task_id)
    segments = result.get("segments") or []
    if segment_index < 0 or segment_index >= len(segments):
        raise APIError("上传识别片段不存在", 404)
    segment = segments[segment_index]
    audio_path = row.get("recognition_path") if row else None
    if not audio_path or not os.path.exists(audio_path):
        registration_audio = result.get("registration_audio") or {}
        file_name = registration_audio.get("file_name")
        if file_name:
            audio_path = _resolve_uploaded_audio_path(_get_uploaded_recognition_audio_dir(), file_name)
    if not audio_path or not os.path.exists(audio_path):
        raise APIError("识别基准音频不存在", 404)

    segment_audio_path = _write_audio_segment(audio_path, segment.get("startMs"), segment.get("endMs"))
    if not segment_audio_path:
        raise APIError("截取片段音频失败", 400)

    @after_this_request
    def _cleanup_segment_audio(response):
        try:
            if os.path.exists(segment_audio_path):
                os.unlink(segment_audio_path)
        except Exception:
            pass
        return response

    return send_file(segment_audio_path, mimetype="audio/wav", as_attachment=False)


@app.route('/api/upload/audio/tasks/<task_id>/speaker-candidates', methods=['GET'])
@handle_database_error
def get_uploaded_audio_speaker_candidates(task_id: str):
    result = _get_completed_upload_result(task_id)
    return create_response({
        "task_id": task_id,
        "candidates": _speaker_candidate_rows_from_result(task_id, result)
    }, "获取上传识别说话人候选成功")


@app.route('/api/upload/audio/tasks/<task_id>/corrections', methods=['POST'])
@handle_database_error
def apply_uploaded_audio_corrections(task_id: str):
    data = request.get_json(silent=True) or {}
    corrections = data.get("corrections")
    if corrections is None:
        corrections = data.get("replacements")
    use_default = _coerce_bool(data.get("use_default"), False)
    include_config_file = _coerce_bool(data.get("include_config_file"), False)

    correction_pairs = _load_upload_text_correction_pairs(
        corrections,
        use_default=use_default,
        include_config_file=include_config_file
    )
    if not correction_pairs:
        raise APIError("没有可用的上传识别纠错规则", 400)

    result = _get_completed_upload_result(task_id)
    before_count = _get_upload_result_text_correction_count(result)
    result = _apply_uploaded_result_corrections(
        result,
        use_default=False,
        include_config_file=False,
        correction_pairs=correction_pairs
    )
    result = _save_upload_result_for_task(task_id, result)
    correction_count = max(0, _get_upload_result_text_correction_count(result) - before_count)
    return create_response({
        "correction_count": correction_count,
        "correction_details": (result.get("asr_metadata") or {}).get("text_correction_details") or [],
        "result": result
    }, "上传识别文本纠错已应用")


@app.route('/api/upload/audio/tasks/<task_id>/speakers/<path:speaker>', methods=['PATCH'])
@handle_database_error
def rename_uploaded_audio_speaker(task_id: str, speaker: str):
    data = request.get_json() or {}
    new_name = (data.get("name") or "").strip()
    if not new_name:
        raise APIError("name 不能为空", 400)
    result = _get_completed_upload_result(task_id)
    changed = 0
    for segment in result.get("segments") or []:
        if (segment.get("speaker") or "") == speaker:
            segment["speaker"] = new_name
            changed += 1
    if changed == 0:
        raise APIError("说话人不存在", 404)
    result = _save_upload_result_for_task(task_id, result)
    return create_response({"updated_segments": changed, "result": result}, "上传识别说话人已更名")


@app.route('/api/upload/audio/tasks/<task_id>/segments/<int:segment_index>/speaker', methods=['PATCH'])
@handle_database_error
def rename_uploaded_audio_segment_speaker(task_id: str, segment_index: int):
    data = request.get_json() or {}
    new_name = (data.get("name") or "").strip()
    if not new_name:
        raise APIError("name 不能为空", 400)
    result = _get_completed_upload_result(task_id)
    segments = result.get("segments") or []
    if segment_index < 0 or segment_index >= len(segments):
        raise APIError("片段不存在", 404)

    old_name = segments[segment_index].get("speaker") or ""
    segments[segment_index]["speaker"] = new_name
    result = _save_upload_result_for_task(task_id, result)
    return create_response({
        "segment_index": segment_index,
        "old_speaker": old_name,
        "new_speaker": new_name,
        "result": result
    }, "上传识别片段说话人已修改")


@app.route('/api/upload/audio/tasks/<task_id>/speakers/merge', methods=['POST'])
@handle_database_error
def merge_uploaded_audio_speakers(task_id: str):
    data = request.get_json() or {}
    source = (data.get("from") or "").strip()
    target = (data.get("into") or "").strip()
    if not source or not target:
        raise APIError("from 和 into 不能为空", 400)
    if source == target:
        raise APIError("不能合并到同一个说话人", 400)
    result = _get_completed_upload_result(task_id)
    moved = 0
    for segment in result.get("segments") or []:
        if (segment.get("speaker") or "") == source:
            segment["speaker"] = target
            moved += 1
    if moved == 0:
        raise APIError("源说话人不存在", 404)
    result = _save_upload_result_for_task(task_id, result)
    return create_response({"moved_segments": moved, "result": result}, "上传识别说话人已合并")


# ============================================================================
# 语音识别结果API
# ============================================================================

@app.route('/api/meetings/<int:meeting_id>/speech-results', methods=['POST'])
@handle_database_error
def save_speech_result(meeting_id: int):
    """保存语音识别结果"""
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    required_fields = ['speaker_id', 'speaker_name', 'text_content']
    for field in required_fields:
        if not data.get(field):
            raise APIError(f"{field} 不能为空", 400)
    
    speech_id = db.save_speech_result(
        meeting_id=meeting_id,
        speaker_id=data['speaker_id'],
        speaker_name=data['speaker_name'],
        text_content=data['text_content'],
        confidence=data.get('confidence'),
        start_time=data.get('start_time'),
        end_time=data.get('end_time'),
        language=data.get('language', 'zh')
    )
    
    return create_response({
        "speech_id": speech_id,
        "meeting_id": meeting_id,
        "speaker_name": data['speaker_name']
    }, "语音识别结果保存成功", 201)


@app.route('/api/meetings/<int:meeting_id>/speech-results', methods=['GET'])
@handle_database_error
def get_meeting_speech_results(meeting_id: int):
    """获取会议的语音识别结果"""
    speech_results = db.get_meeting_speech_results(meeting_id)
    results_list = [dict(result) for result in speech_results]
    
    return create_response({
        "meeting_id": meeting_id,
        "speech_results": results_list,
        "count": len(results_list)
    }, "获取语音识别结果成功")


# ============================================================================
# 语音识别模式API
# ============================================================================

@app.route('/api/meetings/<int:meeting_id>/recognition-modes', methods=['POST'])
@handle_database_error
def save_recognition_mode(meeting_id: int):
    """保存语音识别模式结果"""
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    required_fields = ['audio_file_id', 'mode_type', 'text_content']
    for field in required_fields:
        if field not in data:
            raise APIError(f"{field} 不能为空", 400)
    
    # 验证模式类型
    valid_modes = ['speaker_diarization', 'no_speaker_diarization']
    if data['mode_type'] not in valid_modes:
        raise APIError(f"无效的模式类型，支持的类型: {', '.join(valid_modes)}", 400)
    
    mode_id = db.save_speech_recognition_mode(
        meeting_id=meeting_id,
        audio_file_id=data['audio_file_id'],
        mode_type=data['mode_type'],
        text_content=data['text_content'],
        confidence=data.get('confidence'),
        start_time=data.get('start_time'),
        end_time=data.get('end_time'),
        language=data.get('language', 'zh')
    )
    
    return create_response({
        "mode_id": mode_id,
        "meeting_id": meeting_id,
        "mode_type": data['mode_type']
    }, "语音识别模式结果保存成功", 201)


@app.route('/api/meetings/<int:meeting_id>/recognition-modes', methods=['GET'])
@handle_database_error
def get_recognition_modes(meeting_id: int):
    """获取会议的语音识别模式结果"""
    mode_type = request.args.get('mode_type')
    
    mode_results = db.get_speech_recognition_modes(meeting_id, mode_type)
    results_list = [dict(result) for result in mode_results]
    
    return create_response({
        "meeting_id": meeting_id,
        "mode_type": mode_type,
        "recognition_modes": results_list,
        "count": len(results_list)
    }, "获取语音识别模式结果成功")


@app.route('/api/audio-files/<int:audio_file_id>/recognition-modes', methods=['GET'])
@handle_database_error
def get_audio_recognition_modes(audio_file_id: int):
    """获取音频文件的语音识别模式结果"""
    mode_results = db.get_audio_file_recognition_modes(audio_file_id)
    results_list = [dict(result) for result in mode_results]
    
    return create_response({
        "audio_file_id": audio_file_id,
        "recognition_modes": results_list,
        "count": len(results_list)
    }, "获取音频文件识别结果成功")


# ============================================================================
# 翻译内容API
# ============================================================================

@app.route('/api/meetings/<int:meeting_id>/translations', methods=['POST'])
@handle_database_error
def save_meeting_translation(meeting_id: int):
    """保存会议翻译内容"""
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    required_fields = ['source_type', 'source_id', 'original_text', 
                      'translated_text', 'source_language', 'target_language']
    for field in required_fields:
        if not data.get(field):
            raise APIError(f"{field} 不能为空", 400)
    
    # 验证源类型
    valid_source_types = ['speech_result', 'mode_result']
    if data['source_type'] not in valid_source_types:
        raise APIError(f"无效的源类型，支持的类型: {', '.join(valid_source_types)}", 400)
    
    translation_id = db.save_meeting_translation(
        meeting_id=meeting_id,
        source_type=data['source_type'],
        source_id=data['source_id'],
        original_text=data['original_text'],
        translated_text=data['translated_text'],
        source_language=data['source_language'],
        target_language=data['target_language'],
        confidence=data.get('confidence')
    )
    
    return create_response({
        "translation_id": translation_id,
        "meeting_id": meeting_id,
        "source_type": data['source_type']
    }, "翻译内容保存成功", 201)


@app.route('/api/meetings/<int:meeting_id>/translations', methods=['GET'])
@handle_database_error
def get_meeting_translations(meeting_id: int):
    """获取会议的翻译内容"""
    source_type = request.args.get('source_type')
    
    translations = db.get_meeting_translations(meeting_id, source_type)
    translations_list = [dict(translation) for translation in translations]
    
    return create_response({
        "meeting_id": meeting_id,
        "source_type": source_type,
        "translations": translations_list,
        "count": len(translations_list)
    }, "获取翻译内容成功")


@app.route('/api/translations/by-source', methods=['GET'])
@handle_database_error
def get_translations_by_source():
    """根据源记录获取翻译内容"""
    source_type = request.args.get('source_type')
    source_id = request.args.get('source_id')
    
    if not source_type or not source_id:
        raise APIError("source_type 和 source_id 参数不能为空", 400)
    
    try:
        source_id = int(source_id)
    except ValueError:
        raise APIError("source_id 必须是整数", 400)
    
    translations = db.get_translation_by_source(source_type, source_id)
    translations_list = [dict(translation) for translation in translations]
    
    return create_response({
        "source_type": source_type,
        "source_id": source_id,
        "translations": translations_list,
        "count": len(translations_list)
    }, "获取源记录翻译内容成功")


# ============================================================================
# 传统翻译结果API
# ============================================================================

@app.route('/api/speech-results/<int:speech_id>/translations', methods=['POST'])
@handle_database_error
def save_translation_result(speech_id: int):
    """保存传统翻译结果"""
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    required_fields = ['original_text', 'translated_text', 
                      'source_language', 'target_language']
    for field in required_fields:
        if not data.get(field):
            raise APIError(f"{field} 不能为空", 400)
    
    translation_id = db.save_translation_result(
        speech_result_id=speech_id,
        original_text=data['original_text'],
        translated_text=data['translated_text'],
        source_language=data['source_language'],
        target_language=data['target_language'],
        confidence=data.get('confidence')
    )
    
    return create_response({
        "translation_id": translation_id,
        "speech_result_id": speech_id
    }, "翻译结果保存成功", 201)


# ============================================================================
# 说话人管理API
# ============================================================================

@app.route('/api/speakers', methods=['POST'])
@handle_database_error
def save_speaker():
    """保存说话人信息"""
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    speaker_id = data.get('speaker_id')
    if not speaker_id:
        raise APIError("speaker_id 不能为空", 400)
    
    db_speaker_id = db.save_speaker(
        speaker_id=speaker_id,
        name=data.get('name'),
        email=data.get('email'),
        voice_features=data.get('voice_features')
    )
    
    return create_response({
        "id": db_speaker_id,
        "speaker_id": speaker_id,
        "name": data.get('name')
    }, "说话人信息保存成功", 201)


@app.route('/api/speakers/<speaker_id>', methods=['GET'])
@handle_database_error
def get_speaker(speaker_id: str):
    """获取说话人信息"""
    speaker = db.get_speaker(speaker_id)
    if not speaker:
        raise APIError("说话人不存在", 404)
    
    speaker_data = dict(speaker)
    # 解析声纹特征JSON
    if speaker_data.get('voice_features'):
        try:
            speaker_data['voice_features'] = json.loads(speaker_data['voice_features'])
        except json.JSONDecodeError:
            speaker_data['voice_features'] = None
    
    return create_response(speaker_data, "获取说话人信息成功")


@app.route('/api/speakers/register', methods=['POST'])
@handle_database_error
def register_speaker_voiceprint():
    """注册说话人声纹"""
    from ..speaker.speaker_manager import register_speaker, init_speaker_manager
    import base64
    
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    speaker_name = data.get('speaker_name')
    if not speaker_name:
        raise APIError("speaker_name 不能为空", 400)

    server_state = app.config.get('SERVER_STATE')
    init_speaker_manager(getattr(server_state, 'args', None))
    
    # 处理音频数据
    audio_input = None
    if 'audio_data' in data:
        # Base64编码的音频数据
        try:
            audio_input = base64.b64decode(data['audio_data'])
        except Exception as e:
            raise APIError(f"音频数据解码失败: {str(e)}", 400)
    elif 'audio_file_path' in data:
        # 音频文件路径
        audio_input = _resolve_user_audio_input_path(data['audio_file_path'])
    else:
        raise APIError("必须提供 audio_data 或 audio_file_path", 400)
    
    # 调用说话人管理器注册
    result = register_speaker(
        speaker_name=speaker_name,
        audio_input=audio_input,
        description=data.get('description', ''),
        overwrite=data.get('overwrite', False)
    )
    
    if result['success']:
        return create_response(result, "说话人声纹注册成功", 201)
    else:
        raise APIError(result['message'], 400)


@app.route('/api/speakers/register-uploaded-segment', methods=['POST'])
@handle_database_error
def register_speaker_from_uploaded_segment():
    """从上传识别文件的时间片段注册说话人声纹。"""
    from ..audio.audio_format_handler import convert_media_to_wav, cleanup_temp_file
    from ..speaker.speaker_manager import register_speaker, init_speaker_manager

    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)

    speaker_name = (data.get('speaker_name') or '').strip()
    if not speaker_name:
        raise APIError("speaker_name 不能为空", 400)

    ranges = _collect_registration_audio_ranges(data)
    if not ranges:
        raise APIError("必须提供有效的 start_ms/end_ms 或 segments 时间范围", 400)

    registration_audio = data.get("registration_audio") or {}
    if not isinstance(registration_audio, dict):
        registration_audio = {}

    recognition_file_name = (
        data.get("recognition_audio_file_name") or
        registration_audio.get("file_name")
    )
    source_file_name = (
        data.get("source_audio_file_name") or
        registration_audio.get("source_file_name")
    )

    converted_temp_path = None
    segment_audio_path = None

    try:
        if recognition_file_name:
            audio_path = _resolve_uploaded_audio_path(
                _get_uploaded_recognition_audio_dir(),
                recognition_file_name
            )
            time_base = "recognition_wav_16k_mono"
        elif source_file_name:
            source_path = _resolve_uploaded_audio_path(
                _get_uploaded_audio_upload_dir(),
                source_file_name
            )
            converted_temp_path = convert_media_to_wav(source_path, target_sr=16000, target_channels=1)
            audio_path = converted_temp_path
            time_base = "converted_source_wav_16k_mono"
        else:
            raise APIError("缺少上传识别音频引用，请重新上传识别后再注册", 400)

        segment_audio_path = _write_audio_segments(
            audio_path,
            [{"start_ms": start_ms, "end_ms": end_ms} for start_ms, end_ms in ranges]
        )
        if not segment_audio_path:
            raise APIError("按时间戳截取注册音频失败，请确认识别结果包含有效时间戳", 400)

        server_state = app.config.get('SERVER_STATE')
        init_speaker_manager(getattr(server_state, 'args', None))

        result = register_speaker(
            speaker_name=speaker_name,
            audio_input=segment_audio_path,
            description=data.get('description', ''),
            overwrite=data.get('overwrite', False)
        )

        if result['success']:
            result["registration_source"] = {
                "time_base": time_base,
                "ranges": [{"start_ms": start_ms, "end_ms": end_ms} for start_ms, end_ms in ranges],
                "duration_ms": sum(end_ms - start_ms for start_ms, end_ms in ranges)
            }
            return create_response(result, "说话人声纹注册成功", 201)

        raise APIError(result['message'], 400)
    finally:
        if segment_audio_path:
            cleanup_temp_file(segment_audio_path)
        if converted_temp_path:
            cleanup_temp_file(converted_temp_path)


@app.route('/api/speakers/list', methods=['GET'])
@handle_database_error
def list_speakers():
    """获取所有已注册说话人列表"""
    from ..speaker.speaker_manager import list_speakers as get_speakers_list
    
    speakers = get_speakers_list()
    return create_response({
        "speakers": speakers,
        "count": len(speakers)
    }, "获取说话人列表成功")


@app.route('/api/speakers/identify', methods=['POST'])
@handle_database_error
def identify_speaker():
    """识别说话人"""
    from ..speaker.speaker_manager import identify_speaker as identify, init_speaker_manager
    import base64
    
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    # 处理音频数据
    audio_input = None
    if 'audio_data' in data:
        # Base64编码的音频数据
        try:
            audio_input = base64.b64decode(data['audio_data'])
        except Exception as e:
            raise APIError(f"音频数据解码失败: {str(e)}", 400)
    elif 'audio_file_path' in data:
        # 音频文件路径
        audio_input = _resolve_user_audio_input_path(data['audio_file_path'])
    else:
        raise APIError("必须提供 audio_data 或 audio_file_path", 400)

    server_state = app.config.get('SERVER_STATE')
    init_speaker_manager(getattr(server_state, 'args', None))
    
    # 识别说话人
    result = identify(
        audio_input=audio_input,
        top_k=data.get('top_k', 3)
    )
    
    if result['success']:
        return create_response(result, "说话人识别成功")
    else:
        raise APIError(result['message'], 400)


@app.route('/api/speakers/delete', methods=['POST'])
@handle_database_error
def delete_speaker():
    """删除说话人"""
    from ..speaker.speaker_manager import delete_speaker as delete_speaker_func
    
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    speaker_name = data.get('speaker_name')
    if not speaker_name:
        raise APIError("speaker_name 不能为空", 400)
    
    # 调用说话人管理器删除
    result = delete_speaker_func(speaker_name)
    
    if result['success']:
        return create_response(result, "说话人删除成功")
    else:
        raise APIError(result['message'], 400)


# ============================================================================
# 音频设备API
# ============================================================================

@app.route('/api/audio-devices', methods=['GET'])
@handle_database_error
def get_server_audio_devices():
    """获取服务器端的音频输入设备列表"""
    try:
        result = get_audio_devices()
        
        if result['success']:
            return create_response({
                "devices": result['devices'],
                "default_device": result['default_device']
            }, "获取音频设备列表成功")
        else:
            raise APIError(result['message'], 500)
            
    except Exception as e:
        logger.error(f"获取音频设备列表失败: {e}")
        raise APIError(f"获取音频设备列表失败: {str(e)}", 500)


# ============================================================================
# 会议纪要API
# ============================================================================

def _minutes_version_to_dict(row) -> Dict[str, Any]:
    data = dict(row)
    data['is_current'] = bool(data.get('is_current'))
    return data


def _create_minutes_revision_prompt() -> str:
    return """你是一个专业的会议纪要编辑助手。请基于已有会议纪要和用户修改要求，输出一份修改后的完整会议纪要。

要求：
1. 保留原纪要中的事实信息，不得添加、推测或虚构原文没有的信息。
2. 严格执行用户的修改要求，例如压缩、扩写、调整结构、突出行动项、改写措辞等。
3. 如果用户要求与原纪要事实冲突，以原纪要事实为准，并用更稳妥的表达处理。
4. 输出完整的新纪要，而不是差异说明。
5. 使用清晰的 Markdown 格式。
6. 严禁输出 <think>、</think>、<thinking>、</thinking> 等思考标签。
7. 严禁输出推理过程、内心独白或分析过程。
"""


def _llm_service_type_from_config(llm_config: Dict[str, Any]) -> str:
    return (
        llm_config.get('serviceType') or
        llm_config.get('service_type') or
        _get_stored_llm_config(include_secrets=False).get('activeServiceType') or
        'ollama'
    )


def _llm_model_from_config(llm_config: Dict[str, Any], service_type: str) -> str:
    inline_config = llm_config.get('config') or {}
    model = inline_config.get('model') or llm_config.get('model')
    if model:
        return str(model)

    stored_config = _get_stored_llm_config(include_secrets=False)
    service_config = stored_config.get('services', {}).get(service_type, {})
    return str(service_config.get('model') or '')


def _append_no_think_if_needed(content: str, llm_config: Dict[str, Any]) -> str:
    service_type = _llm_service_type_from_config(llm_config)
    model = _llm_model_from_config(llm_config, service_type).lower()
    if 'qwen3' not in model:
        return content
    content = content.rstrip()
    return content if content.endswith('/no_think') else f"{content} /no_think"


def _append_summary_no_think(content: str) -> str:
    content = (content or '').rstrip()
    return content if content.endswith('/no_think') else f"{content} /no_think"


def _revise_minutes_summary(base_summary: str, instruction: str, payload: Dict[str, Any]) -> str:
    options = payload.get('options') or {}
    options.setdefault('temperature', 0.4)
    options.setdefault('top_p', 0.8)
    options.setdefault('max_tokens', SUMMARY_MODEL_CONFIG['max_output_tokens'])
    llm_config = payload.get('llm') or {}

    user_content = (
        f"已有会议纪要：\n{base_summary}\n\n"
        f"用户修改要求：\n{instruction}\n\n"
        "请输出修改后的完整会议纪要。"
    )

    llm_payload = {
        'messages': [
            {'role': 'system', 'content': _append_no_think_if_needed(_create_minutes_revision_prompt(), llm_config)},
            {'role': 'user', 'content': _append_no_think_if_needed(user_content, llm_config)}
        ],
        'options': options
    }
    if llm_config.get('serviceType') or llm_config.get('service_type'):
        llm_payload['serviceType'] = llm_config.get('serviceType') or llm_config.get('service_type')
    if llm_config.get('config'):
        llm_payload['config'] = llm_config.get('config')

    result = _call_llm_gateway(llm_payload)
    content = (result.get('content') or '').strip()
    if not content:
        raise APIError("LLM返回的改写纪要为空", 502)
    return content

@app.route('/api/meetings/<int:meeting_id>/minutes', methods=['POST'])
@handle_database_error
def save_meeting_minutes(meeting_id: int):
    """保存会议纪要"""
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    minutes_id = db.save_meeting_minutes(
        meeting_id=meeting_id,
        summary=data.get('summary'),
        key_points=data.get('key_points'),
        action_items=data.get('action_items'),
        decisions=data.get('decisions'),
        participants=data.get('participants')
    )
    
    return create_response({
        "minutes_id": minutes_id,
        "meeting_id": meeting_id
    }, "会议纪要保存成功", 201)


@app.route('/api/meetings/<int:meeting_id>/minutes', methods=['GET'])
@handle_database_error
def get_meeting_minutes(meeting_id: int):
    """获取会议纪要"""
    minutes = db.get_meeting_minutes(meeting_id)
    if not minutes:
        raise APIError("会议纪要不存在", 404)

    minutes_data = dict(minutes)
    # 解析JSON字段
    json_fields = ['key_points', 'action_items', 'decisions', 'participants']
    for field in json_fields:
        if minutes_data.get(field):
            try:
                minutes_data[field] = json.loads(minutes_data[field])
            except json.JSONDecodeError:
                minutes_data[field] = None

    return create_response(minutes_data, "获取会议纪要成功")


@app.route('/api/meetings/<int:meeting_id>/minutes/versions', methods=['GET'])
@handle_database_error
def get_meeting_minutes_versions(meeting_id: int):
    """获取会议纪要版本列表"""
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise APIError("会议不存在", 404)

    minutes = db.get_meeting_minutes(meeting_id)
    if minutes and minutes['summary']:
        db.ensure_meeting_minutes_version(meeting_id, minutes['summary'])

    versions = [
        _minutes_version_to_dict(row)
        for row in db.get_meeting_minutes_versions(meeting_id)
    ]
    return create_response({
        'meeting_id': meeting_id,
        'versions': versions,
        'total': len(versions)
    }, "获取会议纪要版本成功")


@app.route('/api/meetings/<int:meeting_id>/minutes/revise', methods=['POST'])
@handle_database_error
def revise_meeting_minutes(meeting_id: int):
    """基于已有纪要和自然语言要求生成新版本"""
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise APIError("会议不存在", 404)

    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)

    instruction = (data.get('instruction') or '').strip()
    if not instruction:
        raise APIError("改写要求不能为空", 400)

    base_summary = (data.get('base_summary') or data.get('baseSummary') or '').strip()
    source_version_id = data.get('source_version_id') or data.get('sourceVersionId')
    source_version = None

    if source_version_id:
        source_version = db.get_meeting_minutes_version(int(source_version_id))
        if not source_version or source_version['meeting_id'] != meeting_id:
            raise APIError("源纪要版本不存在", 404)
        base_summary = source_version['summary']
    else:
        source_version = db.get_current_meeting_minutes_version(meeting_id)
        if source_version:
            base_summary = source_version['summary']
        elif base_summary:
            source_version_id = db.ensure_meeting_minutes_version(
                meeting_id,
                base_summary,
                instruction="原始纪要"
            )
            source_version = db.get_meeting_minutes_version(int(source_version_id)) if source_version_id else None
        else:
            minutes = db.get_meeting_minutes(meeting_id)
            if minutes and minutes['summary']:
                base_summary = minutes['summary']
                source_version_id = db.ensure_meeting_minutes_version(
                    meeting_id,
                    base_summary,
                    instruction="原始纪要"
                )
                source_version = db.get_meeting_minutes_version(int(source_version_id)) if source_version_id else None

    if not base_summary:
        raise APIError("没有可改写的会议纪要", 400)

    revised_summary = _revise_minutes_summary(base_summary, instruction, data)
    new_version_id = db.save_meeting_minutes_version(
        meeting_id=meeting_id,
        summary=revised_summary,
        instruction=instruction,
        source_version_id=source_version['id'] if source_version else None,
        is_current=True
    )
    db.save_meeting_minutes(
        meeting_id=meeting_id,
        summary=revised_summary,
        create_version=False
    )

    version = db.get_meeting_minutes_version(new_version_id)
    return create_response({
        'meeting_id': meeting_id,
        'version': _minutes_version_to_dict(version),
        'summary': revised_summary
    }, "会议纪要改写完成", 201)


@app.route('/api/meetings/<int:meeting_id>/minutes/versions/<int:version_id>/download', methods=['GET'])
@handle_database_error
def download_meeting_minutes_version(meeting_id: int, version_id: int):
    """下载指定会议纪要版本"""
    version = db.get_meeting_minutes_version(version_id)
    if not version or version['meeting_id'] != meeting_id:
        raise APIError("会议纪要版本不存在", 404)

    download_format = (request.args.get('format') or 'md').lower()
    allowed_formats = {'md', 'docx', 'word', 'pdf'}
    if download_format not in allowed_formats:
        raise APIError("不支持的下载格式", 400)

    meeting = db.get_meeting(meeting_id)
    meeting_title = meeting['title'] if meeting else 'meeting'
    safe_title = re.sub(r'[^\w\u4e00-\u9fff-]+', '_', meeting_title).strip('_') or 'meeting'
    base_name = f"{safe_title}_会议纪要_v{version['version']}"
    markdown_content = version['summary']

    if download_format in {'docx', 'word'}:
        return send_file(
            _build_docx(markdown_content),
            as_attachment=True,
            download_name=f"{base_name}.docx",
            mimetype=DOCX_MIMETYPE
        )

    if download_format == 'pdf':
        return send_file(
            _build_pdf(markdown_content),
            as_attachment=True,
            download_name=f"{base_name}.pdf",
            mimetype=PDF_MIMETYPE
        )

    buffer = BytesIO(markdown_content.encode('utf-8'))
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{base_name}.md",
        mimetype='text/markdown'
    )


@app.route('/api/meetings/save-complete', methods=['POST'])
@handle_database_error
def save_complete_meeting():
    """综合保存会议：包括音频文件、转录内容和会议纪要"""
    try:
        # 检查是否是文件上传请求
        if 'multipart/form-data' in request.content_type:
            # 处理文件上传格式
            data = request.form.to_dict()
            audio_file = request.files.get('audioFile')
        else:
            # 处理JSON格式
            data = request.get_json()
            audio_file = None
            
        if not data:
            raise APIError("请求数据不能为空", 400)
        
        # 验证必需字段
        required_fields = ['title']
        for field in required_fields:
            if not data.get(field):
                raise APIError(f"{field} 不能为空", 400)
        
        # 1. 创建会议记录
        meeting_id = db.create_meeting(
            title=data['title'],
            description=data.get('description', '')
        )
        
        logger.info(f"创建会议成功，会议ID: {meeting_id}")
        
        # 2. 保存音频文件（如果提供）
        audio_id = None
        audio_upload_error = None
        
        if audio_file:
            # 处理上传的音频文件
            try:
                if audio_file.filename:
                    # 确保音频存储目录存在
                    audio_dir = os.path.join(os.getcwd(), 'data', 'audio')
                    os.makedirs(audio_dir, exist_ok=True)
                    
                    # 生成安全的文件名
                    filename = secure_filename(audio_file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    audio_filename = f"{timestamp}_{filename}"
                    audio_path = os.path.join(audio_dir, audio_filename)
                    
                    # 保存文件
                    audio_file.save(audio_path)
                    
                    # 获取文件信息
                    file_size = os.path.getsize(audio_path)
                    
                    # 保存音频文件记录
                    audio_id = db.save_audio_file(
                        meeting_id=meeting_id,
                        file_name=audio_filename,
                        file_path=audio_path,
                        file_size=file_size,
                        format=data.get('audioFormat', 'wav'),
                        sample_rate=data.get('sampleRate', 16000),
                        channels=data.get('channels', 1)
                    )
                    
                    logger.info(f"保存音频文件成功，音频ID: {audio_id}")
            except Exception as e:
                audio_upload_error = str(e)
                logger.error(f"音频文件上传失败: {audio_upload_error}")
                logger.info("音频文件上传失败，但会议保存将继续进行")
                
        elif data.get('audioFilePath'):
            # 处理已存在的音频文件路径
            try:
                audio_file_path = _resolve_user_audio_input_path(data['audioFilePath'])
                audio_id = db.save_audio_file(
                    meeting_id=meeting_id,
                    file_name=data.get('audioFileName', 'audio.wav'),
                    file_path=audio_file_path,
                    file_size=data.get('audioFileSize'),
                    format=data.get('audioFormat', 'wav'),
                    sample_rate=data.get('sampleRate', 16000),
                    channels=data.get('channels', 1)
                )
                
                logger.info(f"保存音频文件记录成功，音频ID: {audio_id}")
            except Exception as e:
                audio_upload_error = str(e)
                logger.error(f"音频文件路径保存失败: {audio_upload_error}")
                logger.info("音频文件路径保存失败，但会议保存将继续进行")
        
        # 3. 保存语音转录结果（如果提供）
        speech_result_id = None
        if data.get('transcriptionContent'):
            speech_result_id = db.save_speech_result(
                meeting_id=meeting_id,
                speaker_id=data.get('speakerId', 'unknown'),
                speaker_name=data.get('speakerName', '未知说话人'),
                text_content=data['transcriptionContent'],
                confidence=data.get('confidence', 0.95),
                start_time=data.get('startTime', 0.0),
                end_time=data.get('endTime', 0.0),
                language=data.get('language', 'zh')
            )
            
            logger.info(f"保存语音转录结果成功，结果ID: {speech_result_id}")
        
        # 4. 保存会议纪要（如果提供）
        minutes_id = None
        if data.get('meetingMinutes') or data.get('summary'):
            # 处理会议纪要数据
            summary = data.get('meetingMinutes') or data.get('summary', '')
            key_points = data.get('keyPoints', [])
            action_items = data.get('actionItems', [])
            decisions = data.get('decisions', [])
            participants = data.get('participants', [])
            
            # 确保列表数据为正确的类型
            if isinstance(key_points, str):
                try:
                    key_points = json.loads(key_points)
                except json.JSONDecodeError:
                    key_points = []
            if isinstance(action_items, str):
                try:
                    action_items = json.loads(action_items)
                except json.JSONDecodeError:
                    action_items = []
            if isinstance(decisions, str):
                try:
                    decisions = json.loads(decisions)
                except json.JSONDecodeError:
                    decisions = []
            if isinstance(participants, str):
                try:
                    participants = json.loads(participants)
                except json.JSONDecodeError:
                    participants = []
            
            minutes_id = db.save_meeting_minutes(
                meeting_id=meeting_id,
                summary=summary,
                key_points=key_points,
                action_items=action_items,
                decisions=decisions,
                participants=participants
            )
            
            logger.info(f"保存会议纪要成功，纪要ID: {minutes_id}")
        
        # 5. 结束会议（设置结束时间）
        db.end_meeting(meeting_id)
        
        # 返回成功响应
        response_data = {
            'meeting_id': meeting_id,
            'audio_id': audio_id,
            'speech_result_id': speech_result_id,
            'minutes_id': minutes_id,
            'title': data['title'],
            'audio_upload_success': audio_id is not None,
            'audio_upload_error': audio_upload_error
        }
        
        # 根据音频上传结果调整响应消息
        if audio_upload_error:
            message = "会议保存成功，但音频文件上传失败"
            logger.warning(f"会议 {meeting_id} 保存成功，但音频上传失败: {audio_upload_error}")
        else:
            message = "会议保存成功"
        
        return create_response(response_data, message, 201)
        
    except Exception as e:
        logger.error(f"保存会议失败: {str(e)}", exc_info=True)
        raise APIError(f"保存会议失败: {str(e)}", 500)


@app.route('/api/meetings/save-documents', methods=['POST'])
@handle_database_error
def save_meeting_documents():
    """统一保存会议文档：同时保存到文件系统和数据库"""
    try:
        # 检查请求内容长度
        content_length = request.content_length
        max_size = app.config.get('MAX_CONTENT_LENGTH', 1024 * 1024 * 1024)  # 默认1GB
        
        # 记录请求大小信息
        if content_length:
            size_mb = content_length / (1024 * 1024)
            logger.info(f"接收到会议文档保存请求，数据大小: {size_mb:.1f}MB")
            
            # 检查是否超过限制（给一些缓冲空间）
            if content_length > max_size:
                max_mb = max_size / (1024 * 1024)
                raise APIError(f"请求数据过大: {size_mb:.1f}MB，最大允许: {max_mb:.0f}MB", 413)
        else:
            logger.info("接收到会议文档保存请求")
        
        data = request.get_json()
        if not data:
            raise APIError("请求数据不能为空", 400)
        
        # 验证必需字段
        required_fields = ['title']
        for field in required_fields:
            if not data.get(field):
                raise APIError(f"{field} 不能为空", 400)
        
        # 1. 创建或获取会议记录
        meeting_id = data.get('meeting_id')
        if not meeting_id:
            # 如果没有提供meeting_id，创建新的会议记录
            meeting_id = db.create_meeting(
                title=data['title'],
                description=data.get('description', '')
            )
            logger.info(f"创建新会议记录，ID: {meeting_id}")
        else:
            # 验证会议是否存在
            meeting = db.get_meeting(meeting_id)
            if not meeting:
                raise APIError(f"会议ID {meeting_id} 不存在", 404)
            logger.info(f"使用现有会议记录，ID: {meeting_id}")
        
        # 2. 确保文档存储目录存在
        documents_dir = os.path.join(os.getcwd(), 'data', 'documents')
        os.makedirs(documents_dir, exist_ok=True)
        
        # 3. 生成文件名（使用时间戳和会议ID避免重复）
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = "".join(c for c in data['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        base_filename = f"{timestamp}_{meeting_id}_{safe_title}"
        
        saved_files = []
        
        # 保存转录内容
        if data.get('transcriptionContent'):
            transcription_filename = f"{base_filename}_转录内容.md"
            transcription_path = os.path.join(documents_dir, transcription_filename)
            
            transcription_content = f"# {data['title']} - 转录内容\n\n"
            transcription_content += f"**会议时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n"
            if data.get('description'):
                transcription_content += f"**会议描述**: {data['description']}\n\n"
            if data.get('participants'):
                transcription_content += f"**参与人员**: {data['participants']}\n\n"
            transcription_content += "## 转录内容\n\n"
            transcription_content += data['transcriptionContent']
            
            with open(transcription_path, 'w', encoding='utf-8') as f:
                f.write(transcription_content)
            
            # 获取实际文件大小
            actual_size = os.path.getsize(transcription_path)
            
            # 保存到数据库
            doc_id = db.save_meeting_document(
                meeting_id=meeting_id,
                document_type='transcription',
                file_name=transcription_filename,
                file_path=transcription_path,
                file_size=actual_size
            )
            
            saved_files.append({
                'type': 'transcription',
                'filename': transcription_filename,
                'path': transcription_path,
                'size': actual_size,
                'document_id': doc_id
            })
            
            logger.info(f"转录内容已保存到: {transcription_path}, 数据库ID: {doc_id}")
        
        # 保存会议纪要
        if data.get('meetingMinutes') or data.get('summary'):
            minutes_filename = f"{base_filename}_会议纪要.md"
            minutes_path = os.path.join(documents_dir, minutes_filename)
            summary_text = (data.get('summary') or '').strip()
            meeting_minutes_text = (data.get('meetingMinutes') or '').strip()
            
            minutes_content = f"# {data['title']} - 会议纪要\n\n"
            minutes_content += f"**会议时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n"
            if data.get('description'):
                minutes_content += f"**会议描述**: {data['description']}\n\n"
            if data.get('participants'):
                minutes_content += f"**参与人员**: {data['participants']}\n\n"
            
            # 添加会议纪要内容
            if summary_text and summary_text != meeting_minutes_text:
                minutes_content += "## 会议总结\n\n"
                minutes_content += data['summary'] + "\n\n"
            
            if meeting_minutes_text:
                minutes_content += "## 详细纪要\n\n"
                minutes_content += data['meetingMinutes'] + "\n\n"
            elif summary_text:
                minutes_content += "## 详细纪要\n\n"
                minutes_content += data['summary'] + "\n\n"
            
            # 添加结构化信息
            if data.get('keyPoints'):
                minutes_content += "## 关键要点\n\n"
                for i, point in enumerate(data['keyPoints'], 1):
                    minutes_content += f"{i}. {point}\n"
                minutes_content += "\n"
            
            if data.get('actionItems'):
                minutes_content += "## 行动项\n\n"
                for i, item in enumerate(data['actionItems'], 1):
                    minutes_content += f"- [ ] {item}\n"
                minutes_content += "\n"
            
            if data.get('decisions'):
                minutes_content += "## 决策事项\n\n"
                for i, decision in enumerate(data['decisions'], 1):
                    minutes_content += f"{i}. {decision}\n"
                minutes_content += "\n"
            
            with open(minutes_path, 'w', encoding='utf-8') as f:
                f.write(minutes_content)
            
            # 获取实际文件大小
            actual_size = os.path.getsize(minutes_path)
            
            # 保存到数据库
            doc_id = db.save_meeting_document(
                meeting_id=meeting_id,
                document_type='minutes',
                file_name=minutes_filename,
                file_path=minutes_path,
                file_size=actual_size
            )
            
            saved_files.append({
                'type': 'minutes',
                'filename': minutes_filename,
                'path': minutes_path,
                'size': actual_size,
                'document_id': doc_id
            })

            db.save_meeting_minutes(
                meeting_id=meeting_id,
                summary=data.get('meetingMinutes') or data.get('summary') or minutes_content
            )
            
            logger.info(f"会议纪要已保存到: {minutes_path}, 数据库ID: {doc_id}")

        # 保存上传音视频识别的源文件引用（文件已在上传识别任务中持久化）
        upload_task_id = data.get('uploadTaskId') or data.get('upload_task_id')
        raw_recognition_mode = str(
            data.get('recognitionMode') or data.get('recognition_mode') or ''
        ).strip().lower()
        raw_transcription_source = str(
            data.get('transcriptionSource') or data.get('transcription_source') or ''
        ).strip().lower()
        transcription_source = 'upload' if (
            upload_task_id or raw_recognition_mode == 'upload' or raw_transcription_source == 'upload'
        ) else 'realtime'
        if upload_task_id:
            task_row = _get_upload_task_row(str(upload_task_id))
            if task_row:
                linked_segments = _link_upload_task_segments_to_meeting(str(upload_task_id), int(meeting_id))
                logger.info(
                    f"上传识别片段已关联到会议: task_id={upload_task_id}, "
                    f"meeting_id={meeting_id}, segments={linked_segments}"
                )

            if task_row and task_row.get('saved_path') and os.path.exists(task_row['saved_path']):
                source_path = task_row['saved_path']
                source_filename = task_row.get('file_name') or data.get('audioFileName') or os.path.basename(source_path)
                actual_size = os.path.getsize(source_path)
                doc_id = db.save_meeting_document(
                    meeting_id=meeting_id,
                    document_type='audio',
                    file_name=source_filename,
                    file_path=source_path,
                    file_size=actual_size
                )

                saved_files.append({
                    'type': 'audio',
                    'filename': source_filename,
                    'path': source_path,
                    'size': actual_size,
                    'document_id': doc_id,
                    'source': 'uploaded_audio_task',
                    'task_id': str(upload_task_id)
                })

                logger.info(
                    f"上传音视频源文件已关联到会议: task_id={upload_task_id}, "
                    f"path={source_path}, 数据库ID: {doc_id}"
                )
            else:
                logger.warning(f"上传识别任务源文件不可用，跳过媒体关联: task_id={upload_task_id}")
        
        # 保存音频文件（如果提供）
        if data.get('audioFile') and data.get('audioFileName'):
            # 确保音频存储目录存在
            audio_dir = os.path.join(os.getcwd(), 'data', 'audio')
            os.makedirs(audio_dir, exist_ok=True)
            
            # 生成音频文件名
            audio_filename = f"{base_filename}_{data['audioFileName']}"
            audio_path = os.path.join(audio_dir, audio_filename)
            
            # 保存音频文件
            import base64
            try:
                # 如果audioFile是base64编码的字符串
                if isinstance(data['audioFile'], str):
                    # 处理base64编码的音频数据
                    if data['audioFile'].startswith('data:'):
                        # 移除data URL前缀
                        audio_data = data['audioFile'].split(',')[1]
                    else:
                        audio_data = data['audioFile']
                    
                    # 解码并保存
                    with open(audio_path, 'wb') as f:
                        f.write(base64.b64decode(audio_data))
                else:
                    # 如果是二进制数据，直接保存
                    with open(audio_path, 'wb') as f:
                        f.write(data['audioFile'])
                
                # 获取实际文件大小
                actual_size = os.path.getsize(audio_path)
                
                # 保存到数据库
                doc_id = db.save_meeting_document(
                    meeting_id=meeting_id,
                    document_type='audio',
                    file_name=audio_filename,
                    file_path=audio_path,
                    file_size=actual_size
                )
                
                saved_files.append({
                    'type': 'audio',
                    'filename': audio_filename,
                    'path': audio_path,
                    'size': actual_size,
                    'document_id': doc_id
                })
                
                logger.info(f"音频文件已保存到: {audio_path}, 数据库ID: {doc_id}")
                
            except Exception as e:
                logger.error(f"保存音频文件失败: {str(e)}")
                # 音频保存失败不影响其他文档的保存，继续执行
        
        # 返回成功响应
        response_data = {
            'meeting_id': meeting_id,
            'title': data['title'],
            'timestamp': timestamp,
            'recognition_mode': 'upload' if transcription_source == 'upload' else 'realtime',
            'transcription_source': transcription_source,
            'upload_task_id': str(upload_task_id) if upload_task_id else None,
            'documents_directory': documents_dir,
            'saved_files': saved_files,
            'total_files': len(saved_files)
        }
        
        return create_response(response_data, "会议文档保存成功", 201)
        
    except Exception as e:
        logger.error(f"保存会议文档失败: {str(e)}", exc_info=True)
        raise APIError(f"保存会议文档失败: {str(e)}", 500)


DOCX_MIMETYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
PDF_MIMETYPE = 'application/pdf'


def _strip_markdown_inline(text: str) -> str:
    """去掉常见Markdown行内标记，保留可读文本。"""
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text.strip()


def _markdown_to_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """将项目生成的简单Markdown拆成适合导出渲染的块。"""
    blocks: List[Dict[str, Any]] = []
    in_code_block = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue

        if not stripped:
            blocks.append({'type': 'blank', 'text': ''})
            continue

        if not in_code_block:
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if heading_match:
                blocks.append({
                    'type': 'heading',
                    'level': len(heading_match.group(1)),
                    'text': _strip_markdown_inline(heading_match.group(2)),
                })
                continue

            task_match = re.match(r'^[-*+]\s+\[[ xX]\]\s+(.+)$', stripped)
            if task_match:
                blocks.append({
                    'type': 'paragraph',
                    'text': f"- [ ] {_strip_markdown_inline(task_match.group(1))}",
                })
                continue

            unordered_match = re.match(r'^[-*+]\s+(.+)$', stripped)
            if unordered_match:
                blocks.append({
                    'type': 'paragraph',
                    'text': f"- {_strip_markdown_inline(unordered_match.group(1))}",
                })
                continue

            ordered_match = re.match(r'^(\d+\.)\s+(.+)$', stripped)
            if ordered_match:
                blocks.append({
                    'type': 'paragraph',
                    'text': f"{ordered_match.group(1)} {_strip_markdown_inline(ordered_match.group(2))}",
                })
                continue

        blocks.append({
            'type': 'paragraph',
            'text': _strip_markdown_inline(line),
            'raw_text': line,
        })

    return blocks


def _replace_download_extension(file_name: str, extension: str) -> str:
    base_name = os.path.splitext(file_name or 'meeting_document')[0]
    return f"{base_name}{extension}"


def _docx_speaker_time_runs(markdown_line: str) -> Optional[List[Dict[str, Any]]]:
    match = re.match(r'^\s*\*\*([^*\n]+)\*\*(?:\s+(\[[^\]]+\]))?(.*)$', markdown_line)
    if not match:
        return None

    speaker, time_label, rest = match.groups()
    runs = [{'text': _strip_markdown_inline(speaker), 'bold': True}]
    if time_label:
        runs.append({'text': ' ', 'bold': False})
        runs.append({'text': time_label.strip(), 'bold': True})
    if rest:
        runs.append({'text': _strip_markdown_inline(rest), 'bold': False})
    return [run for run in runs if run['text']]


def _docx_run(text: str, bold: bool = False) -> str:
    run_props = '<w:rPr><w:b/></w:rPr>' if bold else ''
    return (
        '<w:r>'
        f'{run_props}'
        f'<w:t xml:space="preserve">{xml_escape(text)}</w:t>'
        '</w:r>'
    )


def _docx_paragraph(
    text: str,
    style_id: Optional[str] = None,
    runs: Optional[List[Dict[str, Any]]] = None
) -> str:
    paragraph_props = ''
    if style_id:
        paragraph_props = f'<w:pPr><w:pStyle w:val="{style_id}"/></w:pPr>'

    if not text and not runs:
        return '<w:p/>'

    run_xml = ''.join(_docx_run(str(run['text']), bool(run.get('bold'))) for run in runs) if runs else _docx_run(text)

    return (
        '<w:p>'
        f'{paragraph_props}'
        f'{run_xml}'
        '</w:p>'
    )


def _build_docx(markdown_text: str) -> BytesIO:
    paragraphs = []
    for block in _markdown_to_blocks(markdown_text):
        if block['type'] == 'blank':
            paragraphs.append(_docx_paragraph(''))
            continue

        if block['type'] == 'heading':
            level = min(max(int(block.get('level', 1)), 1), 3)
            paragraphs.append(_docx_paragraph(block['text'], f'Heading{level}'))
        else:
            paragraphs.append(_docx_paragraph(
                block['text'],
                runs=_docx_speaker_time_runs(block.get('raw_text') or '')
            ))

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(paragraphs)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr>
      <w:rFonts w:ascii="Arial" w:eastAsia="SimSun" w:hAnsi="Arial"/>
      <w:sz w:val="22"/>
      <w:szCs w:val="22"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="200" w:after="100"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="160" w:after="80"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
</w:styles>'''

    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

    root_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    document_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as docx:
        docx.writestr('[Content_Types].xml', content_types_xml)
        docx.writestr('_rels/.rels', root_rels_xml)
        docx.writestr('word/_rels/document.xml.rels', document_rels_xml)
        docx.writestr('word/document.xml', document_xml)
        docx.writestr('word/styles.xml', styles_xml)

    buffer.seek(0)
    return buffer


def _build_pdf(markdown_text: str) -> BytesIO:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise APIError("PDF导出需要安装 reportlab，请先执行 pip install reportlab", 500) from exc

    font_name = 'STSong-Light'
    pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4
    margin = 54
    max_width = page_width - margin * 2
    y = page_height - margin

    def wrap_text(text: str, font_size: int) -> List[str]:
        if not text:
            return ['']

        lines = []
        current = ''
        for char in text.replace('\t', ' '):
            candidate = current + char
            if not current or pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = char

        if current:
            lines.append(current)
        return lines

    for block in _markdown_to_blocks(markdown_text):
        if block['type'] == 'blank':
            y -= 8
            continue

        if block['type'] == 'heading':
            level = min(max(int(block.get('level', 1)), 1), 3)
            font_size = {1: 18, 2: 15, 3: 13}[level]
            line_height = font_size * 1.55
            extra_space = 6
        else:
            font_size = 11
            line_height = 17
            extra_space = 2

        pdf.setFont(font_name, font_size)
        for line in wrap_text(block['text'], font_size):
            if y < margin:
                pdf.showPage()
                pdf.setFont(font_name, font_size)
                y = page_height - margin

            pdf.drawString(margin, y, line)
            y -= line_height

        y -= extra_space

    pdf.save()
    buffer.seek(0)
    return buffer


@app.route('/api/meetings/documents/download', methods=['GET'])
@handle_database_error
def download_meeting_document():
    """下载会议文档"""
    try:
        # 获取查询参数
        document_id = _parse_int(request.args.get('document_id'))
        file_path = request.args.get('file_path')
        file_name = request.args.get('file_name')
        download_format = (request.args.get('format') or 'original').lower()
        inline = _coerce_bool(request.args.get('inline'), False)

        if document_id:
            document = db.get_meeting_document_by_id(document_id)
            if not document:
                raise APIError("文档不存在", 404)
            file_path = document['file_path']
            file_name = file_name or document['file_name']
        elif not file_path:
            raise APIError("document_id 不能为空", 400)

        allowed_formats = {'original', 'md', 'source', 'docx', 'word', 'pdf'}
        if download_format not in allowed_formats:
            raise APIError("不支持的下载格式", 400)

        abs_file_path = _require_existing_file_in_dirs(file_path, [_get_documents_dir(), _get_audio_dir()])
        
        # 确定下载文件名
        if not file_name:
            file_name = os.path.basename(abs_file_path)
        
        # 根据文件扩展名设置MIME类型
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext == '.md' and download_format in {'docx', 'word', 'pdf'}:
            with open(abs_file_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            if download_format in {'docx', 'word'}:
                converted_name = _replace_download_extension(file_name, '.docx')
                logger.info(f"下载Word文档: {abs_file_path} -> {converted_name}")
                return send_file(
                    _build_docx(markdown_content),
                    as_attachment=True,
                    download_name=converted_name,
                    mimetype=DOCX_MIMETYPE
                )

            converted_name = _replace_download_extension(file_name, '.pdf')
            logger.info(f"下载PDF文档: {abs_file_path} -> {converted_name}")
            return send_file(
                _build_pdf(markdown_content),
                as_attachment=True,
                download_name=converted_name,
                mimetype=PDF_MIMETYPE
            )

        if file_ext != '.md' and download_format in {'docx', 'word', 'pdf'}:
            raise APIError("该文件类型不支持格式转换", 400)

        if file_ext == '.md':
            mimetype = 'text/markdown'
        elif file_ext == '.txt':
            mimetype = 'text/plain'
        elif file_ext == '.pdf':
            mimetype = PDF_MIMETYPE
        elif file_ext == '.docx':
            mimetype = DOCX_MIMETYPE
        else:
            mimetype = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
        
        logger.info(f"下载文件: {abs_file_path}")
        
        # 发送文件
        return send_file(
            abs_file_path,
            as_attachment=not inline,
            download_name=file_name,
            mimetype=mimetype
        )
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}", exc_info=True)
        raise APIError("下载文件失败", 500)


@app.route('/api/meetings/documents/list', methods=['GET'])
@handle_database_error
def list_meeting_documents():
    """获取会议文档列表（从数据库）"""
    try:
        # 获取查询参数
        meeting_id = request.args.get('meeting_id')
        meeting_title = request.args.get('meeting_title')
        document_type = request.args.get('document_type')  # transcription, minutes, audio_info
        
        documents = []
        
        if meeting_id:
            # 获取指定会议的文档
            db_documents = db.get_meeting_documents(int(meeting_id), document_type)
            meeting = db.get_meeting(int(meeting_id))
            meeting_title_from_db = meeting['title'] if meeting else '未知会议'
            
            for doc in db_documents:
                document_info = {
                    'id': doc['id'],
                    'meeting_id': doc['meeting_id'],
                    'meeting_title': meeting_title_from_db,
                    'filename': doc['file_name'],
                    'type': doc['document_type'],
                    'file_path': doc['file_path'],
                    'file_size': doc['file_size'],
                    'created_time': doc['created_at'],
                    'updated_time': doc['updated_at'],
                    'download_url': _document_download_url(doc)
                }
                documents.append(document_info)
        else:
            # 获取所有文档
            db_documents = db.get_all_meeting_documents(document_type)
            
            for doc in db_documents:
                # 应用标题过滤
                if meeting_title and meeting_title not in doc['meeting_title']:
                    continue
                
                document_info = {
                    'id': doc['id'],
                    'meeting_id': doc['meeting_id'],
                    'meeting_title': doc['meeting_title'],
                    'filename': doc['file_name'],
                    'type': doc['document_type'],
                    'file_path': doc['file_path'],
                    'file_size': doc['file_size'],
                    'created_time': doc['created_at'],
                    'updated_time': doc['updated_at'],
                    'meeting_start_time': doc['meeting_start_time'],
                    'download_url': _document_download_url(doc)
                }
                documents.append(document_info)
        
        paged_documents, pagination = _paginate_items(documents)
        return create_response({
            'documents': paged_documents,
            'total': len(documents),
            **(pagination or {}),
            'filters': {
                'meeting_id': meeting_id,
                'meeting_title': meeting_title,
                'document_type': document_type
            }
        }, "获取文档列表成功")
        
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}", exc_info=True)
        raise APIError(f"获取文档列表失败: {str(e)}", 500)


EMOTION_SIGNAL_TERMS = {
    'positive': [
        '开心', '高兴', '满意', '认可', '赞同', '感谢', '放心', '有信心', '不错', '顺利',
        '成功', '喜欢', 'happy', 'satisfied', 'confident', 'thanks', 'thank you',
        'agree', 'good', 'great', 'smooth'
    ],
    'negative': [
        '担心', '焦虑', '紧张', '压力', '生气', '愤怒', '失望', '不满', '抱怨', '投诉',
        '冲突', '沮丧', '难受', '糟糕', 'worried', 'anxious', 'angry', 'upset',
        'frustrated', 'stress', 'pressure', 'complaint'
    ],
    'risk': [
        '风险', '困难', '阻塞', '延迟', '失败', '故障', '异常', '紧急', '严重', '不稳定',
        'blocked', 'delay', 'risk', 'urgent', 'fail', 'failure', 'issue'
    ],
    'uncertain': [
        '不确定', '待确认', '需要确认', '再确认', '不清楚', '犹豫', '看情况', '可能',
        '也许', 'maybe', 'probably', 'uncertain', 'not sure', 'to confirm'
    ]
}

EMOTION_SIGNAL_LABELS = {
    'positive': '积极/认可',
    'negative': '负向/压力',
    'risk': '风险/问题',
    'uncertain': '不确定/待确认'
}

EMOTION_IGNORED_SPEAKER_LABELS = {
    '会议时间', '会议描述', '参与人员', '会议名称', '转录内容',
    '会议总结', '详细纪要', '关键要点', '行动项', '决策事项', '时间', '地点'
}


def _strip_markdown_text(text: str) -> str:
    text = re.sub(r'[`*_>#\[\]()]', ' ', text or '')
    return re.sub(r'\s+', ' ', text).strip()


def _count_emotion_terms(text: str, terms: List[str]) -> int:
    normalized = _strip_markdown_text(text).lower()
    return sum(normalized.count(term.lower()) for term in terms)


def _parse_transcript_speaker_line(line: str) -> Optional[Tuple[str, str]]:
    match = re.match(r'^\s*(?:[-*]\s*)?(?:\*\*)?([^:\n：]{1,48})(?:\*\*)?[:：]\s*(.+)$', line)
    if not match:
        return None
    speaker = match.group(1).strip()
    content = match.group(2).strip()
    if not speaker or speaker in EMOTION_IGNORED_SPEAKER_LABELS or speaker.startswith('#') or not content:
        return None
    return speaker, content


def _parse_transcript_speaker_header(line: str) -> Optional[str]:
    bold_match = re.match(
        r'^\s*(?:[-*]\s*)?\*\*([^*\n]{1,48})\*\*(?:\s*\[[^\]]+\])?\s*$',
        line
    )
    time_match = re.match(
        r'^\s*(?:[-*]\s*)?([^:\n：\[\]]{1,48})\s*\[[^\]]+\]\s*$',
        line
    )
    match = bold_match or time_match
    if not match:
        return None

    speaker = match.group(1).strip()
    if not speaker or speaker in EMOTION_IGNORED_SPEAKER_LABELS or speaker.startswith('#'):
        return None
    return speaker


def _is_translation_line(line: str) -> bool:
    return bool(re.match(r'^\s*(翻译|译文|translation)\s*[:：]', line, re.IGNORECASE))


def _extract_emotion_segments(transcript: str) -> List[Dict[str, str]]:
    segments = []
    current_speaker: Optional[str] = None
    current_lines: List[str] = []

    def flush_current_segment():
        nonlocal current_speaker, current_lines
        text = ' '.join(part for part in current_lines if part).strip()
        if current_speaker and text:
            segments.append({'speaker': current_speaker, 'text': text})
        current_speaker = None
        current_lines = []

    for raw_line in (transcript or '').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or line.startswith('**会议') or _is_translation_line(line):
            continue
        header = _parse_transcript_speaker_header(line)
        if header:
            flush_current_segment()
            current_speaker = header
            current_lines = []
            continue

        parsed = _parse_transcript_speaker_line(line)
        if parsed:
            flush_current_segment()
            speaker, content = parsed
            current_speaker = speaker
            current_lines = [_strip_markdown_text(content)]
            continue

        cleaned = _strip_markdown_text(line)
        if cleaned:
            if current_speaker:
                current_lines.append(cleaned)
            else:
                segments.append({'speaker': '未分配', 'text': cleaned})

    flush_current_segment()
    return segments


def _score_emotion_text(text: str) -> Dict[str, int]:
    return {
        signal: _count_emotion_terms(text, terms)
        for signal, terms in EMOTION_SIGNAL_TERMS.items()
    }


def _emotion_score_total(scores: Dict[str, int]) -> int:
    return sum(max(0, value) for value in scores.values())


def _top_emotion_signals(scores: Dict[str, int]) -> List[str]:
    positive_scores = {signal: value for signal, value in scores.items() if value > 0}
    if not positive_scores:
        return []
    max_value = max(positive_scores.values())
    return [signal for signal, value in positive_scores.items() if value == max_value]


def _emotion_tone_label(scores: Dict[str, int]) -> str:
    if _emotion_score_total(scores) == 0:
        return '证据不足'
    top_signals = _top_emotion_signals(scores)
    if len(top_signals) != 1:
        return '多类线索并存'
    return f"检测到{EMOTION_SIGNAL_LABELS.get(top_signals[0], '明确')}线索"


def _main_emotion_signal(scores: Dict[str, int]) -> Tuple[str, str]:
    top_signals = _top_emotion_signals(scores)
    if not top_signals:
        return 'none', '无明确线索'
    if len(top_signals) > 1:
        return 'mixed', '多类线索并存'
    signal = top_signals[0]
    return signal, EMOTION_SIGNAL_LABELS.get(signal, '明确线索')


def _build_emotion_analysis(transcript: str) -> Dict[str, Any]:
    segments = _extract_emotion_segments(transcript)
    full_text = '\n'.join(segment['text'] for segment in segments)
    scores = _score_emotion_text(full_text)
    speaker_stats: Dict[str, Dict[str, Any]] = {}

    for segment in segments:
        speaker = segment['speaker']
        speaker_stat = speaker_stats.setdefault(speaker, {
            'speaker': speaker,
            'segments': 0,
            'characters': 0,
            'scores': {signal: 0 for signal in EMOTION_SIGNAL_TERMS}
        })
        speaker_stat['segments'] += 1
        speaker_stat['characters'] += len(segment['text'])
        segment_scores = _score_emotion_text(segment['text'])
        for signal, value in segment_scores.items():
            speaker_stat['scores'][signal] += value

    highlights = []
    signal_terms = [term for terms in EMOTION_SIGNAL_TERMS.values() for term in terms]
    for segment in segments:
        text_lower = segment['text'].lower()
        if any(term.lower() in text_lower for term in signal_terms):
            highlights.append({
                'speaker': segment['speaker'],
                'text': segment['text'][:160],
                'tone': _emotion_tone_label(_score_emotion_text(segment['text']))
            })
        if len(highlights) >= 6:
            break

    speaker_analyses = []
    sorted_speaker_stats = sorted(
        speaker_stats.values(),
        key=lambda item: (item['segments'], item['characters']),
        reverse=True
    )
    for stat in sorted_speaker_stats:
        speaker = stat['speaker']
        speaker_scores = stat['scores']
        speaker_segments = [
            segment['text']
            for segment in segments
            if segment['speaker'] == speaker
        ]
        speaker_highlights = []
        for text in speaker_segments:
            text_lower = text.lower()
            if any(term.lower() in text_lower for term in signal_terms):
                speaker_highlights.append(text[:160])
            if len(speaker_highlights) >= 3:
                break

        main_signal, main_signal_label = _main_emotion_signal(speaker_scores)
        speaker_analysis = {
            **stat,
            'tone': _emotion_tone_label(speaker_scores),
            'main_signal': main_signal,
            'main_signal_label': main_signal_label,
            'highlights': speaker_highlights
        }
        speaker_analyses.append(speaker_analysis)

    return {
        'segment_count': len(segments),
        'speaker_count': len(speaker_stats),
        'scores': scores,
        'tone': _emotion_tone_label(scores),
        'speaker_stats': speaker_analyses,
        'speaker_analyses': speaker_analyses,
        'highlights': highlights
    }


def _build_emotion_markdown(meeting_title: str, transcript: str) -> str:
    analysis = _build_emotion_analysis(transcript)
    scores = analysis['scores']
    generated_at = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
    lines = [
        f"# {meeting_title} - 情绪分析",
        "",
        f"**生成时间**: {generated_at}",
        "",
        "> 该报告只统计转录文本中明确出现的情绪、压力、风险和不确定性线索；没有明确证据时不做情绪推断，不代表心理或医学判断。",
        "",
        "## 总体判断",
        "",
        f"- **线索结论**: {analysis['tone']}",
        f"- **分析片段**: {analysis['segment_count']} 段",
        f"- **说话人数**: {analysis['speaker_count']} 位",
        "",
        "## 指标概览",
        "",
        "| 指标 | 命中次数 |",
        "| --- | ---: |"
    ]
    for signal, label in EMOTION_SIGNAL_LABELS.items():
        lines.append(f"| {label} | {scores.get(signal, 0)} |")

    lines.extend([
        "",
        "## 说话人分布",
        "",
        "| 说话人 | 段落 | 主要线索 |",
        "| --- | ---: | --- |"
    ])

    for stat in analysis['speaker_analyses']:
        lines.append(f"| {stat['speaker']} | {stat['segments']} | {stat['main_signal_label']} |")

    if not analysis['speaker_analyses']:
        lines.append("| 未分配 | 0 | 无明确线索 |")

    lines.extend([
        "",
        "## 逐人分析",
        ""
    ])
    if analysis['speaker_analyses']:
        for stat in analysis['speaker_analyses']:
            stat_scores = stat['scores']
            lines.extend([
                f"### {stat['speaker']}",
                "",
                f"- **线索结论**: {stat['tone']}",
                f"- **主要线索**: {stat['main_signal_label']}",
                f"- **发言片段**: {stat['segments']} 段，约 {stat['characters']} 字",
                f"- **指标命中**: " + "，".join(
                    f"{label} {stat_scores.get(signal, 0)}"
                    for signal, label in EMOTION_SIGNAL_LABELS.items()
                ),
                ""
            ])
            if stat['highlights']:
                lines.append("代表片段：")
                for text in stat['highlights']:
                    lines.append(f"- {text}")
                lines.append("")
            else:
                lines.append("代表片段：未检测到明确情绪、压力、风险或不确定性线索。")
                lines.append("")
    else:
        lines.append("- 未识别到明确说话人，无法生成逐人分析。")

    lines.extend([
        "",
        "## 重点片段",
        ""
    ])
    if analysis['highlights']:
        for item in analysis['highlights']:
            lines.append(f"- **{item['speaker']}**（{item['tone']}）: {item['text']}")
    else:
        lines.append("- 未检测到明确情绪、压力、风险或不确定性线索。")

    lines.extend([
        "",
        "## 使用建议",
        "",
        "- 对出现负向/压力或风险线索的片段，建议回看原文和录音上下文。",
        "- 对不确定/待确认线索，建议补充责任人、确认项和确认时间。",
        "- 如果未检测到明确线索，请不要把本报告解读为参会人的真实情绪状态。"
    ])
    return '\n'.join(lines) + '\n'


@app.route('/api/meetings/<int:meeting_id>/emotion-analysis', methods=['POST'])
@handle_database_error
def generate_meeting_emotion_analysis(meeting_id: int):
    """生成会议情绪分析产物"""
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise APIError("会议不存在", 404)

    data = request.get_json(silent=True) or {}
    transcript = (data.get('transcript') or '').strip()
    if not transcript:
        transcription_docs = db.get_meeting_documents(meeting_id, 'transcription')
        if transcription_docs:
            transcription_path = transcription_docs[0]['file_path']
            if os.path.exists(transcription_path):
                with open(transcription_path, 'r', encoding='utf-8') as f:
                    transcript = f.read().strip()

    if not transcript:
        raise APIError("没有可分析的转录稿", 400)

    documents_dir = os.path.join(os.getcwd(), 'data', 'documents')
    os.makedirs(documents_dir, exist_ok=True)
    existing_docs = db.get_meeting_documents(meeting_id, 'emotion')
    if existing_docs:
        doc = existing_docs[0]
        emotion_path = doc['file_path']
        emotion_filename = doc['file_name']
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = re.sub(r'[^\w\u4e00-\u9fff-]+', '_', meeting['title']).strip('_') or 'meeting'
        emotion_filename = f"{timestamp}_{meeting_id}_{safe_title}_情绪分析.md"
        emotion_path = os.path.join(documents_dir, emotion_filename)

    abs_documents_dir = os.path.abspath(documents_dir)
    abs_emotion_path = os.path.abspath(emotion_path)
    if not (abs_emotion_path == abs_documents_dir or abs_emotion_path.startswith(abs_documents_dir + os.sep)):
        raise APIError("无效的文件路径", 400)

    markdown = _build_emotion_markdown(meeting['title'], transcript)
    with open(abs_emotion_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    file_size = os.path.getsize(abs_emotion_path)
    if existing_docs:
        document_id = existing_docs[0]['id']
        db.update_meeting_document_file_size(document_id, file_size)
    else:
        document_id = db.save_meeting_document(
            meeting_id=meeting_id,
            document_type='emotion',
            file_name=emotion_filename,
            file_path=abs_emotion_path,
            file_size=file_size
        )

    updated_document = db.get_meeting_document_by_id(document_id)
    return create_response({
        'document': {
            'id': updated_document['id'],
            'meeting_id': updated_document['meeting_id'],
            'filename': updated_document['file_name'],
            'type': updated_document['document_type'],
            'file_path': updated_document['file_path'],
            'file_size': updated_document['file_size'],
            'created_time': updated_document['created_at'],
            'updated_time': updated_document['updated_at'],
            'download_url': _document_download_url(updated_document)
        },
        'content': markdown,
        'analysis': _build_emotion_analysis(transcript)
    }, "情绪分析已生成", 201)


@app.route('/api/meetings/<int:meeting_id>/documents/<int:document_id>/text', methods=['PUT'])
@handle_database_error
def update_meeting_document_text(meeting_id: int, document_id: int):
    """更新会议转录文档文本内容"""
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise APIError("会议不存在", 404)

    document = db.get_meeting_document_by_id(document_id)
    if not document or document['meeting_id'] != meeting_id:
        raise APIError("文档不存在", 404)
    if document['document_type'] != 'transcription':
        raise APIError("仅支持更新转录稿文档", 400)

    data = request.get_json(silent=True) or {}
    content = data.get('content')
    if not isinstance(content, str):
        raise APIError("content 必须为字符串", 400)
    if len(content.encode('utf-8')) > 5 * 1024 * 1024:
        raise APIError("转录稿内容过大", 413)

    documents_dir = os.path.join(os.getcwd(), 'data', 'documents')
    abs_documents_dir = os.path.abspath(documents_dir)
    abs_file_path = os.path.abspath(document['file_path'])
    if not (abs_file_path == abs_documents_dir or abs_file_path.startswith(abs_documents_dir + os.sep)):
        raise APIError("无效的文件路径", 400)
    if not os.path.exists(abs_file_path):
        raise APIError("文件不存在", 404)

    with open(abs_file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    file_size = os.path.getsize(abs_file_path)
    db.update_meeting_document_file_size(document_id, file_size)

    updated_document = db.get_meeting_document_by_id(document_id)
    return create_response({
        'document': {
            'id': updated_document['id'],
            'meeting_id': updated_document['meeting_id'],
            'filename': updated_document['file_name'],
            'type': updated_document['document_type'],
            'file_path': updated_document['file_path'],
            'file_size': updated_document['file_size'],
            'created_time': updated_document['created_at'],
            'updated_time': updated_document['updated_at'],
            'download_url': _document_download_url(updated_document)
        },
        'content': content
    }, "转录稿已更新")


@app.route('/api/meetings/documents/<int:document_id>', methods=['DELETE'])
@handle_database_error
def delete_meeting_document(document_id: int):
    """删除会议文档（同时删除文件和数据库记录）"""
    try:
        # 获取文档信息
        document = db.get_meeting_document_by_id(document_id)
        
        if not document:
            raise APIError("文档不存在", 404)
        file_path = _require_path_in_dirs(document['file_path'], [_get_documents_dir()])
        
        # 删除物理文件
        if os.path.isfile(file_path):
            os.remove(file_path)
            logger.info(f"已删除文件: {file_path}")
        else:
            logger.warning(f"文件不存在: {file_path}")
        
        # 删除数据库记录
        db.delete_meeting_document(document_id)
        
        return create_response({
            'document_id': document_id,
            'file_path': file_path
        }, "文档删除成功")
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {str(e)}", exc_info=True)
        raise APIError("删除文档失败", 500)


@app.route('/data/audio/<path:filename>', methods=['GET'])
@handle_database_error
def serve_audio_file(filename):
    """提供音频文件的静态访问服务"""
    try:
        # 构建音频文件的完整路径
        audio_dir = _get_audio_dir()
        file_path = os.path.join(audio_dir, filename)
        abs_file_path = _require_existing_file_in_dirs(file_path, [audio_dir])
        
        # 返回音频文件
        return send_file(
            abs_file_path,
            mimetype='audio/wav',
            as_attachment=False,
            download_name=os.path.basename(abs_file_path)
        )
    except APIError:
        raise
    except Exception as e:
        logger.error(f"提供音频文件失败: {str(e)}", exc_info=True)
        raise APIError("提供音频文件失败", 500)


# ============================================================================
# 系统配置API
# ============================================================================

@app.route('/api/config', methods=['POST'])
@handle_database_error
def set_config():
    """设置系统配置"""
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    
    key = data.get('key')
    value = data.get('value')
    
    if not key or value is None:
        raise APIError("key 和 value 不能为空", 400)
    
    config_id = db.set_config(
        key=key,
        value=str(value),
        description=data.get('description')
    )
    
    return create_response({
        "config_id": config_id,
        "key": key,
        "value": value
    }, "配置设置成功", 201)


@app.route('/api/config/<key>', methods=['GET'])
@handle_database_error
def get_config(key: str):
    """获取系统配置"""
    value = db.get_config(key)
    if value is None:
        raise APIError("配置项不存在", 404)
    
    return create_response({
        "key": key,
        "value": value
    }, "获取配置成功")


def _is_legacy_default_llm_config(stored: Dict[str, Any]) -> bool:
    """识别旧版自动保存的默认配置，让新默认模型能生效。"""
    if not isinstance(stored, dict):
        return False

    active_service_type = stored.get(
        'activeServiceType',
        LEGACY_DEFAULT_LLM_CONFIG['activeServiceType']
    )
    if active_service_type != LEGACY_DEFAULT_LLM_CONFIG['activeServiceType']:
        return False

    stored_services = stored.get('services') or {}
    if not isinstance(stored_services, dict):
        return False

    for service_type, legacy_service_config in LEGACY_DEFAULT_LLM_CONFIG['services'].items():
        stored_service_config = stored_services.get(service_type) or {}
        if not isinstance(stored_service_config, dict):
            return False

        for field in ('endpoint', 'model'):
            stored_value = stored_service_config.get(field, legacy_service_config[field])
            if stored_value != legacy_service_config[field]:
                return False

        if stored_service_config.get('apiKey') or stored_service_config.get('api_key'):
            return False

    return True


def _get_stored_llm_config(include_secrets: bool = False) -> Dict[str, Any]:
    """获取后端保存的LLM配置。"""
    raw_config = db.get_config('llm_config')
    config = json.loads(json.dumps(DEFAULT_LLM_CONFIG))

    if raw_config:
        try:
            stored = json.loads(raw_config)
            if isinstance(stored, dict):
                if _is_legacy_default_llm_config(stored):
                    return config if include_secrets else _sanitize_llm_config(config)
                if stored.get('activeServiceType') in DEFAULT_LLM_CONFIG['services']:
                    config['activeServiceType'] = stored['activeServiceType']
                stored_services = stored.get('services') or {}
                for service_type, service_config in stored_services.items():
                    if service_type in config['services'] and isinstance(service_config, dict):
                        config['services'][service_type].update(service_config)
        except json.JSONDecodeError:
            logger.warning("LLM配置JSON解析失败，将使用默认配置")

    return config if include_secrets else _sanitize_llm_config(config)


def _sanitize_llm_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """隐藏API Key明文。"""
    sanitized = json.loads(json.dumps(config))
    for service_config in sanitized['services'].values():
        api_key = service_config.pop('apiKey', None)
        service_config.pop('api_key', None)
        service_config['hasApiKey'] = bool(api_key)

    return sanitized


def _save_llm_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """保存LLM配置，未传入的API Key保持原值。"""
    if not data:
        raise APIError("请求数据不能为空", 400)

    current = _get_stored_llm_config(include_secrets=True)
    active_service_type = data.get('activeServiceType') or data.get('serviceType')
    if active_service_type:
        if active_service_type not in DEFAULT_LLM_CONFIG['services']:
            raise APIError(f"不支持的LLM服务类型: {active_service_type}", 400)
        current['activeServiceType'] = active_service_type

    incoming_services = data.get('services') or {}
    for service_type, incoming_config in incoming_services.items():
        if service_type not in DEFAULT_LLM_CONFIG['services']:
            raise APIError(f"不支持的LLM服务类型: {service_type}", 400)
        if not isinstance(incoming_config, dict):
            raise APIError(f"{service_type} 配置格式错误", 400)

        service_config = current['services'][service_type]
        for field in ['endpoint', 'model']:
            if incoming_config.get(field):
                service_config[field] = incoming_config[field]

        if incoming_config.get('clearApiKey'):
            service_config.pop('apiKey', None)
        elif incoming_config.get('apiKey'):
            service_config['apiKey'] = incoming_config['apiKey']

    db.set_config(
        key='llm_config',
        value=json.dumps(current, ensure_ascii=False),
        description='会议纪要LLM服务配置'
    )

    return _get_stored_llm_config(include_secrets=False)


@app.route('/api/llm/config', methods=['GET'])
@handle_database_error
def get_llm_config():
    """获取LLM配置（不返回API Key明文）。"""
    return create_response(_get_stored_llm_config(include_secrets=False), "获取LLM配置成功")


@app.route('/api/llm/config', methods=['PUT'])
@handle_database_error
def update_llm_config():
    """更新LLM配置。"""
    data = request.get_json()
    return create_response(_save_llm_config(data), "LLM配置保存成功")


# ============================================================================
# 数据库信息API
# ============================================================================

@app.route('/api/database/info', methods=['GET'])
@handle_database_error
def get_database_info():
    """获取数据库信息"""
    info = db.get_database_info()
    return create_response(info, "获取数据库信息成功")


@app.route('/api/database/vacuum', methods=['POST'])
@handle_database_error
def vacuum_database():
    """优化数据库"""
    db.vacuum()
    return create_response(None, "数据库优化完成")


# ============================================================================
# 热词管理API
# ============================================================================


def _hotword_now() -> str:
    return datetime.now().isoformat()


def _normalize_hotword_weight(value: Any, default: int = HOTWORDS_DEFAULT_WEIGHT) -> int:
    try:
        weight = int(round(float(value)))
    except (TypeError, ValueError):
        weight = default
    return max(1, min(100, weight))


def _normalize_hotword_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on', 'protected', '保护', '是'}


def _normalize_hotword_word(value: Any) -> str:
    word = re.sub(r'\s+', ' ', str(value or '').strip())
    if not word or len(word) > 50:
        return ''
    if re.search(r'[<>|\[\]{}]', word):
        return ''
    return word


def _safe_hotword_id(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _build_hotword_asset(
    raw: Dict[str, Any],
    *,
    default_category: str = HOTWORDS_DEFAULT_CATEGORY,
    default_source: str = HOTWORDS_DEFAULT_SOURCE,
    existing: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    now = _hotword_now()
    word = _normalize_hotword_word(raw.get('word') or raw.get('text') or raw.get('name'))
    if not word:
        return None

    return {
        'id': _safe_hotword_id(raw.get('id')),
        'word': word,
        'weight': _normalize_hotword_weight(raw.get('weight'), existing.get('weight') if existing else HOTWORDS_DEFAULT_WEIGHT),
        'category': str(raw.get('category') or (existing.get('category') if existing else '') or default_category).strip() or default_category,
        'source': str(raw.get('source') or (existing.get('source') if existing else '') or default_source).strip() or default_source,
        'protected': _normalize_hotword_bool(raw.get('protected', raw.get('isProtected')), existing.get('protected', False) if existing else False),
        'description': str(raw.get('description') or (existing.get('description') if existing else '') or '').strip(),
        'created_at': str(raw.get('created_at') or (existing.get('created_at') if existing else '') or now),
        'updated_at': now
    }


def _parse_legacy_hotword_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    parts = line.split()
    weight = HOTWORDS_DEFAULT_WEIGHT
    word = line
    if len(parts) >= 2:
        try:
            parsed_weight = float(parts[-1])
        except ValueError:
            parsed_weight = None
        if parsed_weight is not None:
            weight = _normalize_hotword_weight(parsed_weight)
            word = ' '.join(parts[:-1])

    word = _normalize_hotword_word(word)
    if not word:
        return None

    return {
        'word': word,
        'weight': _normalize_hotword_weight(weight),
        'category': HOTWORDS_DEFAULT_CATEGORY,
        'source': HOTWORDS_LEGACY_SOURCE,
        'protected': False
    }


def _dedupe_hotword_assets(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    by_word: Dict[str, Dict[str, Any]] = {}
    used_ids = set()
    next_id = 1

    for item in items:
        word = item.get('word')
        if not word:
            continue

        existing = by_word.get(word)
        if existing:
            if item.get('protected') and not existing.get('protected'):
                existing.update(item)
            else:
                existing['weight'] = max(_normalize_hotword_weight(existing.get('weight')), _normalize_hotword_weight(item.get('weight')))
                existing['updated_at'] = item.get('updated_at') or _hotword_now()
            continue

        hotword_id = _safe_hotword_id(item.get('id'))
        if hotword_id is None or hotword_id in used_ids:
            while next_id in used_ids:
                next_id += 1
            hotword_id = next_id
        used_ids.add(hotword_id)
        item['id'] = hotword_id
        by_word[word] = item
        deduped.append(item)

    return deduped


def _load_legacy_hotword_assets() -> List[Dict[str, Any]]:
    if not os.path.exists(HOTWORDS_TXT_PATH):
        return []

    items: List[Dict[str, Any]] = []
    try:
        with open(HOTWORDS_TXT_PATH, 'r', encoding='utf-8') as file:
            for line in file:
                parsed = _parse_legacy_hotword_line(line)
                if parsed:
                    items.append(_build_hotword_asset(parsed, default_source=HOTWORDS_LEGACY_SOURCE) or parsed)
    except Exception as e:
        logger.warning(f"读取旧版热词文件失败: {e}")

    return _dedupe_hotword_assets(items)


def _load_hotword_assets() -> List[Dict[str, Any]]:
    if not os.path.exists(HOTWORDS_ASSET_PATH):
        return _load_legacy_hotword_assets()

    try:
        with open(HOTWORDS_ASSET_PATH, 'r', encoding='utf-8') as file:
            payload = json.load(file)
    except Exception as e:
        logger.warning(f"读取热词资产文件失败，将回退旧版文件: {e}")
        return _load_legacy_hotword_assets()

    raw_items = payload.get('items') if isinstance(payload, dict) else payload
    if isinstance(raw_items, dict):
        normalized_raw_items = []
        for word, value in raw_items.items():
            if isinstance(value, dict):
                normalized_raw_items.append({'word': word, **value})
            else:
                normalized_raw_items.append({'word': word, 'weight': value})
        raw_items = normalized_raw_items

    items: List[Dict[str, Any]] = []
    if isinstance(raw_items, list):
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            item = _build_hotword_asset(raw_item)
            if item:
                items.append(item)

    return _dedupe_hotword_assets(items)


def _export_hotword_txt(items: List[Dict[str, Any]]) -> None:
    os.makedirs(HOTWORDS_DATA_DIR, exist_ok=True)
    tmp_path = f"{HOTWORDS_TXT_PATH}.{uuid.uuid4().hex}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as file:
        file.write("# 热词配置文件\n")
        file.write("# 格式: 热词 权重\n")
        file.write("# 权重范围: 1-100\n")
        file.write("# 此文件由热词资产自动导出，请在热词设置页面维护\n\n")
        for item in items:
            word = _normalize_hotword_word(item.get('word'))
            if word:
                file.write(f"{word} {_normalize_hotword_weight(item.get('weight'))}\n")
    os.replace(tmp_path, HOTWORDS_TXT_PATH)


def _save_hotword_assets(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    with hotword_asset_lock:
        os.makedirs(HOTWORDS_DATA_DIR, exist_ok=True)
        normalized = _dedupe_hotword_assets([
            item for item in (
                _build_hotword_asset(raw_item) for raw_item in items if isinstance(raw_item, dict)
            )
            if item
        ])

        payload = {
            'version': 1,
            'updated_at': _hotword_now(),
            'items': normalized,
            'metadata': {
                'asset_path': HOTWORDS_ASSET_PATH,
                'export_path': HOTWORDS_TXT_PATH,
                'total_count': len(normalized),
                'protected_count': len([item for item in normalized if item.get('protected')])
            }
        }

        tmp_path = f"{HOTWORDS_ASSET_PATH}.{uuid.uuid4().hex}.tmp"
        with open(tmp_path, 'w', encoding='utf-8') as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, HOTWORDS_ASSET_PATH)
        _export_hotword_txt(normalized)
        return normalized


def _filter_hotword_assets(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    query = request.args.get('q', '').strip().lower()
    category = request.args.get('category', '').strip()
    source = request.args.get('source', '').strip()
    protected_filter = request.args.get('protected', '').strip().lower()
    min_weight = request.args.get('min_weight')
    max_weight = request.args.get('max_weight')

    try:
        min_weight_value = int(min_weight) if min_weight not in (None, '') else None
    except ValueError:
        min_weight_value = None
    try:
        max_weight_value = int(max_weight) if max_weight not in (None, '') else None
    except ValueError:
        max_weight_value = None

    filtered = []
    for item in items:
        word = str(item.get('word', ''))
        if query and query not in word.lower() and query not in str(item.get('description', '')).lower():
            continue
        if category and item.get('category') != category:
            continue
        if source and item.get('source') != source:
            continue
        if protected_filter in {'true', '1', 'yes', 'protected'} and not item.get('protected'):
            continue
        if protected_filter in {'false', '0', 'no', 'unprotected'} and item.get('protected'):
            continue
        weight = _normalize_hotword_weight(item.get('weight'))
        if min_weight_value is not None and weight < min_weight_value:
            continue
        if max_weight_value is not None and weight > max_weight_value:
            continue
        filtered.append(item)

    return filtered


def _parse_hotword_json_payload(content: str, default_category: str, default_source: str) -> Optional[List[Dict[str, Any]]]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None

    raw_items: Any = payload
    if isinstance(payload, dict):
        raw_items = payload.get('items') or payload.get('hotwords') or payload.get('data') or payload

    if isinstance(raw_items, dict):
        normalized_raw_items = []
        for word, value in raw_items.items():
            if isinstance(value, dict):
                normalized_raw_items.append({'word': word, **value})
            else:
                normalized_raw_items.append({'word': word, 'weight': value})
        raw_items = normalized_raw_items

    if not isinstance(raw_items, list):
        return []

    items = []
    for raw_item in raw_items:
        if isinstance(raw_item, str):
            raw_item = {'word': raw_item}
        if isinstance(raw_item, dict):
            item = _build_hotword_asset(raw_item, default_category=default_category, default_source=default_source)
            if item:
                items.append(item)
    return items


def _parse_hotword_csv_rows(content: str, default_category: str, default_source: str) -> List[Dict[str, Any]]:
    rows = [line for line in content.splitlines() if line.strip() and not line.strip().startswith('#')]
    if not rows:
        return []

    try:
        reader = csv.reader(StringIO('\n'.join(rows)))
        parsed_rows = list(reader)
    except csv.Error:
        return []

    if not parsed_rows or all(len(row) <= 1 for row in parsed_rows):
        return []

    header = [cell.strip().lower() for cell in parsed_rows[0]]
    has_header = bool({'word', '热词', 'weight', '权重'} & set(header))
    data_rows = parsed_rows[1:] if has_header else parsed_rows

    def cell(row: List[str], *names: str, fallback_index: Optional[int] = None) -> str:
        if has_header:
            for name in names:
                if name in header:
                    index = header.index(name)
                    return row[index].strip() if index < len(row) else ''
        if fallback_index is not None and fallback_index < len(row):
            return row[fallback_index].strip()
        return ''

    items = []
    for row in data_rows:
        raw = {
            'word': cell(row, 'word', '热词', '词条', fallback_index=0),
            'weight': cell(row, 'weight', '权重', fallback_index=1) or HOTWORDS_DEFAULT_WEIGHT,
            'category': cell(row, 'category', '分类', fallback_index=2) or default_category,
            'protected': cell(row, 'protected', '保护', '是否保护', fallback_index=3),
            'source': cell(row, 'source', '来源', fallback_index=4) or default_source,
            'description': cell(row, 'description', '描述', fallback_index=5)
        }
        item = _build_hotword_asset(raw, default_category=default_category, default_source=default_source)
        if item:
            items.append(item)
    return items


def _parse_hotword_text_lines(content: str, default_category: str, default_source: str) -> List[Dict[str, Any]]:
    items = []
    for line in content.replace('，', ',').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if ',' in line and not re.search(r'\s+\d+(\.\d+)?$', line):
            for word in [part.strip() for part in line.split(',') if part.strip()]:
                item = _build_hotword_asset({
                    'word': word,
                    'weight': HOTWORDS_DEFAULT_WEIGHT,
                    'category': default_category,
                    'source': default_source
                }, default_category=default_category, default_source=default_source)
                if item:
                    items.append(item)
            continue

        parsed = _parse_legacy_hotword_line(line)
        if parsed:
            parsed['category'] = default_category
            parsed['source'] = default_source
            item = _build_hotword_asset(parsed, default_category=default_category, default_source=default_source)
            if item:
                items.append(item)

    return items


def _parse_import_hotwords(content: str, default_category: str, default_source: str) -> List[Dict[str, Any]]:
    content = content.strip()
    if not content:
        return []

    json_items = _parse_hotword_json_payload(content, default_category, default_source)
    if json_items is not None:
        return _dedupe_hotword_assets(json_items)

    csv_items = _parse_hotword_csv_rows(content, default_category, default_source)
    if csv_items:
        return _dedupe_hotword_assets(csv_items)

    return _dedupe_hotword_assets(_parse_hotword_text_lines(content, default_category, default_source))


def _merge_imported_hotwords(
    existing_items: List[Dict[str, Any]],
    imported_items: List[Dict[str, Any]],
    *,
    mode: str = 'merge',
    preserve_protected: bool = True
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    mode = mode if mode in {'append', 'merge', 'replace'} else 'merge'
    base_items = [item for item in existing_items if preserve_protected and item.get('protected')] if mode == 'replace' else list(existing_items)
    by_word = {item['word']: item for item in base_items if item.get('word')}
    next_id = max([_safe_hotword_id(item.get('id')) or 0 for item in existing_items] + [0]) + 1
    stats = {
        'added': 0,
        'updated': 0,
        'skipped_duplicate': 0,
        'skipped_protected': 0
    }

    for imported in imported_items:
        word = imported.get('word')
        if not word:
            continue

        existing = by_word.get(word)
        if existing:
            if preserve_protected and existing.get('protected'):
                stats['skipped_protected'] += 1
                continue
            if mode == 'append':
                stats['skipped_duplicate'] += 1
                continue

            imported['id'] = existing.get('id')
            imported['created_at'] = existing.get('created_at') or imported.get('created_at')
            existing.update(imported)
            existing['updated_at'] = _hotword_now()
            stats['updated'] += 1
            continue

        imported['id'] = next_id
        next_id += 1
        base_items.append(imported)
        by_word[word] = imported
        stats['added'] += 1

    return _dedupe_hotword_assets(base_items), stats


@app.route('/api/hotwords', methods=['GET'])
@handle_database_error
def get_hotwords():
    """获取热词列表"""
    try:
        hotwords = _load_hotword_assets()
        if hotwords and not os.path.exists(HOTWORDS_ASSET_PATH):
            hotwords = _save_hotword_assets(hotwords)
        return create_response(_filter_hotword_assets(hotwords), "获取热词列表成功")
    except APIError:
        raise
    except Exception as e:
        logger.error(f"获取热词列表失败: {e}")
        raise APIError(f"获取热词列表失败: {str(e)}", 500)


@app.route('/api/hotwords', methods=['POST'])
@handle_database_error
def save_hotwords():
    """保存热词列表"""
    try:
        data = request.get_json()
        if not data or 'hotwords' not in data:
            raise APIError("请求数据格式错误，需要hotwords字段", 400)
        
        hotwords = data['hotwords']
        if not isinstance(hotwords, list):
            raise APIError("hotwords必须是数组格式", 400)

        existing = _load_hotword_assets()
        incoming = []
        for raw_item in hotwords:
            if isinstance(raw_item, dict):
                existing_match = next(
                    (item for item in existing if item.get('id') == _safe_hotword_id(raw_item.get('id')) or item.get('word') == raw_item.get('word')),
                    None
                )
                item = _build_hotword_asset(raw_item, existing=existing_match)
                if item:
                    incoming.append(item)

        incoming_ids = {_safe_hotword_id(item.get('id')) for item in incoming}
        incoming_words = {item.get('word') for item in incoming}
        preserved_protected = 0
        for item in existing:
            if item.get('protected') and item.get('id') not in incoming_ids and item.get('word') not in incoming_words:
                incoming.append(item)
                preserved_protected += 1

        saved_hotwords = _save_hotword_assets(incoming)
        return create_response({
            "count": len(saved_hotwords),
            "protected_count": len([item for item in saved_hotwords if item.get('protected')]),
            "preserved_protected": preserved_protected,
            "file_path": HOTWORDS_TXT_PATH,
            "asset_path": HOTWORDS_ASSET_PATH
        }, "热词保存成功")
    except APIError:
        raise
    except Exception as e:
        logger.error(f"保存热词失败: {e}")
        raise APIError(f"保存热词失败: {str(e)}", 500)


@app.route('/api/hotwords/import', methods=['POST'])
@handle_database_error
def import_hotwords():
    """导入热词资产"""
    try:
        data = request.get_json()
        if not data or not data.get('content'):
            raise APIError("请求数据格式错误，需要content字段", 400)

        mode = str(data.get('mode') or 'merge').strip()
        default_category = str(data.get('category') or '导入').strip() or '导入'
        default_source = str(data.get('source') or '导入').strip() or '导入'
        preserve_protected = _normalize_hotword_bool(data.get('preserveProtected'), True)

        imported_items = _parse_import_hotwords(str(data.get('content')), default_category, default_source)
        if not imported_items:
            raise APIError("没有解析到有效热词", 400)

        existing = _load_hotword_assets()
        merged, stats = _merge_imported_hotwords(
            existing,
            imported_items,
            mode=mode,
            preserve_protected=preserve_protected
        )
        saved_hotwords = _save_hotword_assets(merged)
        return create_response({
            "hotwords": saved_hotwords,
            "stats": {
                **stats,
                "parsed": len(imported_items),
                "total": len(saved_hotwords)
            },
            "file_path": HOTWORDS_TXT_PATH,
            "asset_path": HOTWORDS_ASSET_PATH
        }, "热词导入成功")
    except APIError:
        raise
    except Exception as e:
        logger.error(f"导入热词失败: {e}")
        raise APIError(f"导入热词失败: {str(e)}", 500)


@app.route('/api/hotwords/<int:hotword_id>', methods=['PUT'])
@handle_database_error
def update_hotword(hotword_id: int):
    """更新单个热词"""
    try:
        data = request.get_json()
        if not data:
            raise APIError("请求数据不能为空", 400)

        hotwords = _load_hotword_assets()
        target = next((item for item in hotwords if item.get('id') == hotword_id), None)
        if not target:
            raise APIError("热词不存在", 404)

        merged_raw = {**target, **data, 'id': hotword_id}
        updated = _build_hotword_asset(merged_raw, existing=target)
        if not updated:
            raise APIError("热词内容无效", 400)

        duplicate = next(
            (item for item in hotwords if item.get('id') != hotword_id and item.get('word') == updated.get('word')),
            None
        )
        if duplicate:
            raise APIError("热词已存在，不能重名", 400)

        for index, item in enumerate(hotwords):
            if item.get('id') == hotword_id:
                hotwords[index] = updated
                break

        _save_hotword_assets(hotwords)
        return create_response({
            "hotword_id": hotword_id,
            "word": updated.get('word'),
            "weight": updated.get('weight')
        }, "热词更新成功")
    except APIError:
        raise
    except Exception as e:
        logger.error(f"更新热词失败: {e}")
        raise APIError(f"更新热词失败: {str(e)}", 500)


@app.route('/api/hotwords/<int:hotword_id>', methods=['DELETE'])
@handle_database_error
def delete_hotword(hotword_id: int):
    """删除单个热词"""
    try:
        hotwords = _load_hotword_assets()
        target = next((item for item in hotwords if item.get('id') == hotword_id), None)
        if not target:
            raise APIError("热词不存在", 404)
        if target.get('protected'):
            raise APIError("受保护热词不能删除，请先取消保护", 409)

        saved_hotwords = [item for item in hotwords if item.get('id') != hotword_id]
        _save_hotword_assets(saved_hotwords)
        return create_response({
            "hotword_id": hotword_id
        }, "热词删除成功")
    except APIError:
        raise
    except Exception as e:
        logger.error(f"删除热词失败: {e}")
        raise APIError(f"删除热词失败: {str(e)}", 500)


# ============================================================================
# 文档分割API
# ============================================================================

@app.route('/api/segment/text', methods=['POST'])
@handle_database_error
def segment_text():
    """
    单文本分段接口
    
    Request Body:
        {
            "text": "待分段的文本内容"
        }
    
    Returns:
        Response: 分段结果
    """
    data = request.get_json()
    if not data or 'text' not in data:
        raise APIError("请求体中缺少text字段")
    
    text = data['text']
    if not text or not text.strip():
        raise APIError("文本内容不能为空")
    
    try:
        # 确保分段服务已初始化
        try:
            status = get_segmentation_status()
            if not status.get('is_initialized', False):
                init_document_segmentation()
        except Exception as e:
            logger.warning(f"初始化分段服务: {e}")
            init_document_segmentation()
        
        # 执行文档分段
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            segmented_text = loop.run_until_complete(segment(text))
        finally:
            loop.close()
        
        if segmented_text is not None:
            return create_response({
                "original_text": text,
                "segmented_text": segmented_text,
                "original_length": len(text),
                "segmented_length": len(segmented_text),
                "timestamp": datetime.now().isoformat()
            }, "文档分段成功")
        else:
            raise APIError("文档分段处理失败", 500)
            
    except DocumentSegmentationError as e:
        logger.error(f"文档分段错误: {e}")
        raise APIError(f"文档分段失败: {str(e)}", 500)
    except Exception as e:
        logger.error(f"文档分段接口异常: {e}")
        raise APIError(f"服务器内部错误: {str(e)}", 500)


@app.route('/api/segment/batch', methods=['POST'])
@handle_database_error
def segment_text_batch():
    """
    批量文本分段接口
    
    Request Body:
        {
            "texts": ["文本1", "文本2", "文本3"]
        }
    
    Returns:
        Response: 批量分段结果
    """
    data = request.get_json()
    if not data or 'texts' not in data:
        raise APIError("请求体中缺少texts字段")
    
    texts = data['texts']
    if not isinstance(texts, list):
        raise APIError("texts字段必须是数组")
    
    if not texts:
        raise APIError("文本数组不能为空")
    
    if len(texts) > 100:  # 限制批量处理数量
        raise APIError("批量处理文本数量不能超过100个")
    
    try:
        # 确保分段服务已初始化
        try:
            status = get_segmentation_status()
            if not status.get('is_initialized', False):
                init_document_segmentation()
        except Exception as e:
            logger.warning(f"初始化分段服务: {e}")
            init_document_segmentation()
        
        # 执行批量文档分段
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            segmented_texts = loop.run_until_complete(segment_batch(texts))
        finally:
            loop.close()
        
        if segmented_texts is not None:
            results = []
            for i, (original, segmented) in enumerate(zip(texts, segmented_texts)):
                results.append({
                    "index": i,
                    "original_text": original,
                    "segmented_text": segmented if segmented is not None else original,
                    "original_length": len(original) if original else 0,
                    "segmented_length": len(segmented) if segmented else len(original) if original else 0,
                    "success": segmented is not None
                })
            
            return create_response({
                "total_count": len(texts),
                "success_count": sum(1 for r in results if r['success']),
                "results": results,
                "timestamp": datetime.now().isoformat()
            }, "批量文档分段完成")
        else:
            raise APIError("批量文档分段处理失败", 500)
            
    except DocumentSegmentationError as e:
        logger.error(f"批量文档分段错误: {e}")
        raise APIError(f"批量文档分段失败: {str(e)}", 500)
    except Exception as e:
        logger.error(f"批量文档分段接口异常: {e}")
        raise APIError(f"服务器内部错误: {str(e)}", 500)


@app.route('/api/segment/status', methods=['GET'])
@handle_database_error
def get_segment_status():
    """
    获取文档分段服务状态
    
    Returns:
        Response: 分段服务状态信息
    """
    try:
        status = get_segmentation_status()
        return create_response({
            "service_status": status,
            "timestamp": datetime.now().isoformat()
        }, "获取分段服务状态成功")
        
    except Exception as e:
        logger.error(f"获取分段服务状态失败: {e}")
        return create_response({
            "service_status": {
                "is_initialized": False,
                "error": str(e)
            },
            "timestamp": datetime.now().isoformat()
        }, "获取分段服务状态失败", 500)


# ============================================================================
# 串口单元号绑定API
# ============================================================================

SERIAL_CONFIG_PATH = 'config/serial_config.yaml'


def load_serial_config_data() -> Dict[str, Any]:
    """加载串口配置文件。"""
    try:
        with open(SERIAL_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def save_serial_config_data(config: Dict[str, Any]) -> None:
    """保存串口配置文件。"""
    with open(SERIAL_CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def normalize_unit_mapping(unit_mapping: Optional[Dict[Any, Any]]) -> Dict[int, str]:
    """将单元号映射统一为整数键。"""
    normalized: Dict[int, str] = {}
    for raw_unit, speaker_name in (unit_mapping or {}).items():
        try:
            unit_number = int(raw_unit)
        except (TypeError, ValueError):
            continue

        if speaker_name is None:
            continue

        normalized[unit_number] = str(speaker_name).strip()

    return normalized


def get_serial_unit_meta(unit_number: int) -> Dict[str, Any]:
    """根据单元号计算通道与型号信息。"""
    if 1 <= unit_number <= 15:
        channel = unit_number
        model = "型号1"
    elif 33 <= unit_number <= 54:
        channel = unit_number - 32
        model = "型号2"
    else:
        channel = unit_number
        model = "未知"

    return {
        "unit_number": unit_number,
        "unit_hex": f"{unit_number:02X}",
        "channel": channel,
        "channel_name": f"通道{channel:02d}",
        "model": model
    }


def build_serial_units_list(unit_mapping: Optional[Dict[Any, Any]], protocol_type: Optional[str]) -> List[Dict[str, Any]]:
    """构造串口单元列表，未绑定的单元也会返回。"""
    normalized_mapping = normalize_unit_mapping(unit_mapping)
    normalized_protocol = str(protocol_type or 'auto').upper()

    available_units = set(normalized_mapping.keys())

    if normalized_protocol in {'A', 'AUTO'}:
        available_units.update(range(1, 16))
    if normalized_protocol in {'B', 'AUTO'}:
        available_units.update(range(33, 55))

    units_list: List[Dict[str, Any]] = []
    for unit_number in sorted(available_units):
        unit_info = get_serial_unit_meta(unit_number)
        unit_info["speaker_name"] = normalized_mapping.get(unit_number, "")
        units_list.append(unit_info)

    return units_list

@app.route('/api/serial/units', methods=['GET'])
@handle_database_error
def get_serial_units():
    """获取所有串口单元号绑定信息"""
    try:
        from ..serial import get_serial_manager
        
        serial_manager = get_serial_manager()
        config = load_serial_config_data()
        speaker_config = config.get('speaker_identification', {})
        serial_config = config.get('serial', {})

        if serial_manager:
            unit_mapping = serial_manager.unit_speaker_mapping or {}
            mode = serial_manager.get_speaker_mode()
            message = "获取单元号绑定成功"
        else:
            unit_mapping = speaker_config.get('unit_speaker_mapping', {})
            mode = speaker_config.get('mode', 'voiceprint')
            message = "串口管理器未初始化，已返回配置文件中的绑定信息"

        protocol_type = serial_config.get('protocol_type', 'auto')
        units_list = build_serial_units_list(unit_mapping, protocol_type)
        
        return create_response({
            "units": units_list,
            "mode": mode,
            "protocol_type": protocol_type,
            "total": len(units_list),
            "bound_total": len([unit for unit in units_list if unit.get("speaker_name")])
        }, message)
        
    except Exception as e:
        logger.error(f"获取单元号绑定失败: {e}")
        raise APIError(f"获取单元号绑定失败: {str(e)}", 500)


@app.route('/api/serial/units/<int:unit_number>', methods=['PUT'])
@handle_database_error
def update_serial_unit(unit_number: int):
    """更新单元号绑定的说话人"""
    try:
        from ..serial import get_serial_manager
        
        data = request.get_json()
        if not data:
            raise APIError("请求数据不能为空", 400)
        
        speaker_name = data.get('speaker_name', '').strip()
        if not speaker_name:
            raise APIError("说话人名称不能为空", 400)
        
        # 验证单元号范围
        if unit_number < 1 or unit_number > 255:
            raise APIError("单元号必须在1-255之间", 400)
        
        # 读取配置文件
        config = load_serial_config_data()
        
        # 确保配置结构存在
        if 'speaker_identification' not in config:
            config['speaker_identification'] = {}
        if 'unit_speaker_mapping' not in config['speaker_identification']:
            config['speaker_identification']['unit_speaker_mapping'] = {}
        
        # 更新映射
        config['speaker_identification']['unit_speaker_mapping'][unit_number] = speaker_name
        
        # 保存配置文件
        save_serial_config_data(config)
        
        # 更新串口管理器
        serial_manager = get_serial_manager()
        if serial_manager:
            serial_manager.unit_speaker_mapping[unit_number] = speaker_name
            logger.info(f"更新单元号绑定: {unit_number} -> {speaker_name}")
        
        unit_info = get_serial_unit_meta(unit_number)
        unit_info["speaker_name"] = speaker_name
        return create_response(unit_info, "更新单元号绑定成功")
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"更新单元号绑定失败: {e}")
        raise APIError(f"更新单元号绑定失败: {str(e)}", 500)


@app.route('/api/serial/units/<int:unit_number>', methods=['DELETE'])
@handle_database_error
def delete_serial_unit(unit_number: int):
    """删除单元号绑定"""
    try:
        from ..serial import get_serial_manager
        
        config = load_serial_config_data()
        if not config:
            raise APIError("配置文件不存在", 404)
        
        # 检查映射是否存在
        if 'speaker_identification' not in config or \
           'unit_speaker_mapping' not in config['speaker_identification']:
            raise APIError("单元号映射不存在", 404)
        
        mapping = config['speaker_identification']['unit_speaker_mapping']
        if unit_number in mapping:
            del mapping[unit_number]
        elif str(unit_number) in mapping:
            del mapping[str(unit_number)]
        else:
            raise APIError(f"单元号{unit_number}未绑定", 404)
        
        # 保存配置文件
        save_serial_config_data(config)
        
        # 更新串口管理器
        serial_manager = get_serial_manager()
        if serial_manager and unit_number in serial_manager.unit_speaker_mapping:
            del serial_manager.unit_speaker_mapping[unit_number]
            logger.info(f"删除单元号绑定: {unit_number}")
        
        return create_response(None, "删除单元号绑定成功")
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"删除单元号绑定失败: {e}")
        raise APIError(f"删除单元号绑定失败: {str(e)}", 500)


@app.route('/api/serial/units/batch', methods=['POST'])
@handle_database_error
def batch_update_serial_units():
    """批量更新单元号绑定"""
    try:
        from ..serial import get_serial_manager
        
        data = request.get_json()
        if not data or 'units' not in data:
            raise APIError("请求数据格式错误", 400)
        
        units = data['units']
        if not isinstance(units, list):
            raise APIError("units必须是数组", 400)
        
        # 读取配置文件
        config = load_serial_config_data()
        
        # 确保配置结构存在
        if 'speaker_identification' not in config:
            config['speaker_identification'] = {}
        if 'unit_speaker_mapping' not in config['speaker_identification']:
            config['speaker_identification']['unit_speaker_mapping'] = {}
        
        # 批量更新
        updated_count = 0
        for unit in units:
            unit_number = unit.get('unit_number')
            speaker_name = unit.get('speaker_name', '').strip()
            
            if not unit_number or not speaker_name:
                continue
            
            if unit_number < 1 or unit_number > 255:
                continue
            
            config['speaker_identification']['unit_speaker_mapping'][unit_number] = speaker_name
            updated_count += 1
        
        # 保存配置文件
        save_serial_config_data(config)
        
        # 更新串口管理器
        serial_manager = get_serial_manager()
        if serial_manager:
            serial_manager.unit_speaker_mapping.update(
                config['speaker_identification']['unit_speaker_mapping']
            )
            logger.info(f"批量更新单元号绑定: {updated_count}个")
        
        return create_response({
            "updated_count": updated_count
        }, f"批量更新成功，共更新{updated_count}个绑定")
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"批量更新单元号绑定失败: {e}")
        raise APIError(f"批量更新单元号绑定失败: {str(e)}", 500)


@app.route('/api/serial/mode', methods=['GET'])
@handle_database_error
def get_serial_mode():
    """获取串口识别模式"""
    try:
        from ..serial import get_serial_manager
        
        serial_manager = get_serial_manager()
        config = load_serial_config_data()
        if serial_manager:
            mode = serial_manager.get_speaker_mode()
            message = "获取识别模式成功"
        else:
            mode = config.get('speaker_identification', {}).get('mode', 'voiceprint')
            message = "串口管理器未初始化，已返回配置文件中的识别模式"
        
        mode_desc = {
            'voiceprint': '声纹识别模式',
            'serial': '串口识别模式',
            'hybrid': '混合模式'
        }
        
        return create_response({
            "mode": mode,
            "description": mode_desc.get(mode, '未知模式')
        }, message)
        
    except Exception as e:
        logger.error(f"获取识别模式失败: {e}")
        raise APIError(f"获取识别模式失败: {str(e)}", 500)


@app.route('/api/serial/mode', methods=['PUT'])
@handle_database_error
def update_serial_mode():
    """更新串口识别模式"""
    try:
        from ..serial import get_serial_manager
        
        data = request.get_json()
        if not data or 'mode' not in data:
            raise APIError("请求数据格式错误", 400)
        
        mode = data['mode']
        if mode not in ['voiceprint', 'serial', 'hybrid']:
            raise APIError("模式必须是voiceprint、serial或hybrid", 400)
        
        # 读取配置文件
        config = load_serial_config_data()
        
        # 确保配置结构存在
        if 'speaker_identification' not in config:
            config['speaker_identification'] = {}
        
        # 更新模式
        config['speaker_identification']['mode'] = mode
        
        # 保存配置文件
        save_serial_config_data(config)
        
        # 更新串口管理器
        serial_manager = get_serial_manager()
        if serial_manager:
            serial_manager.speaker_mode = mode
            logger.info(f"更新识别模式: {mode}")
        
        mode_desc = {
            'voiceprint': '声纹识别模式',
            'serial': '串口识别模式',
            'hybrid': '混合模式'
        }
        
        return create_response({
            "mode": mode,
            "description": mode_desc.get(mode, '未知模式')
        }, "更新识别模式成功")
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"更新识别模式失败: {e}")
        raise APIError(f"更新识别模式失败: {str(e)}", 500)


@app.route('/api/serial/config', methods=['GET'])
@handle_database_error
def get_serial_config():
    """获取串口配置"""
    try:
        config = load_serial_config_data()
        if not config:
            raise APIError("配置文件不存在", 404)
        
        serial_config = config.get('serial', {})
        
        return create_response({
            "enabled": serial_config.get('enabled', False),
            "port": serial_config.get('port', 'COM1'),
            "baudrate": serial_config.get('baudrate', 9600),
            "protocol_type": serial_config.get('protocol_type', 'auto'),
            "logging": serial_config.get('logging', True),
            "log_level": serial_config.get('log_level', 'INFO')
        }, "获取串口配置成功")
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"获取串口配置失败: {e}")
        raise APIError(f"获取串口配置失败: {str(e)}", 500)


@app.route('/api/serial/config', methods=['PUT'])
@handle_database_error
def update_serial_config():
    """更新串口配置"""
    try:
        data = request.get_json()
        if not data:
            raise APIError("请求数据不能为空", 400)
        
        # 读取配置文件
        config = load_serial_config_data()
        
        # 确保配置结构存在
        if 'serial' not in config:
            config['serial'] = {}
        
        # 更新配置
        if 'enabled' in data:
            config['serial']['enabled'] = bool(data['enabled'])
        if 'port' in data:
            config['serial']['port'] = str(data['port'])
        if 'baudrate' in data:
            baudrate = int(data['baudrate'])
            if baudrate not in [9600, 19200, 38400, 57600, 115200]:
                raise APIError("波特率必须是9600, 19200, 38400, 57600或115200", 400)
            config['serial']['baudrate'] = baudrate
        if 'protocol_type' in data:
            protocol = data['protocol_type']
            if protocol not in ['auto', 'A', 'B']:
                raise APIError("协议类型必须是auto、A或B", 400)
            config['serial']['protocol_type'] = protocol
        if 'logging' in data:
            config['serial']['logging'] = bool(data['logging'])
        if 'log_level' in data:
            log_level = data['log_level']
            if log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
                raise APIError("日志级别必须是DEBUG、INFO、WARNING或ERROR", 400)
            config['serial']['log_level'] = log_level
        
        # 保存配置文件
        save_serial_config_data(config)
        
        logger.info(f"更新串口配置: {data}")
        
        return create_response({
            "enabled": config['serial'].get('enabled', False),
            "port": config['serial'].get('port', 'COM1'),
            "baudrate": config['serial'].get('baudrate', 9600),
            "protocol_type": config['serial'].get('protocol_type', 'auto'),
            "logging": config['serial'].get('logging', True),
            "log_level": config['serial'].get('log_level', 'INFO'),
            "message": "配置已更新，重启服务器后生效"
        }, "更新串口配置成功")
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"更新串口配置失败: {e}")
        raise APIError(f"更新串口配置失败: {str(e)}", 500)


# ============================================================================
# LLM网关与任务队列API
# ============================================================================

def _extract_llm_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """校验并标准化LLM请求。"""
    if not data:
        raise APIError("LLM请求数据不能为空", 400)

    stored_config = _get_stored_llm_config(include_secrets=True)
    service_type = (
        data.get('serviceType') or
        data.get('service_type') or
        stored_config.get('activeServiceType') or
        'ollama'
    )
    if service_type not in {'ollama', 'xinference', 'vllm', 'sglang'}:
        raise APIError(f"不支持的LLM服务类型: {service_type}", 400)

    messages = data.get('messages')
    if not isinstance(messages, list) or not messages:
        raise APIError("messages不能为空", 400)

    config = data.get('config') or data.get(f'{service_type}Config') or {}
    service_config = stored_config.get('services', {}).get(service_type, {})
    endpoint = config.get('endpoint') or data.get('endpoint') or service_config.get('endpoint')
    model = config.get('model') or data.get('model') or service_config.get('model')
    api_key = (
        config.get('apiKey') or
        config.get('api_key') or
        data.get('apiKey') or
        service_config.get('apiKey') or
        service_config.get('api_key')
    )

    if not endpoint:
        raise APIError("LLM endpoint不能为空", 400)
    if not model:
        raise APIError("LLM model不能为空", 400)

    parsed_endpoint = urlparse(endpoint)
    if parsed_endpoint.scheme not in {'http', 'https'} or not parsed_endpoint.netloc:
        raise APIError("LLM endpoint必须是有效的HTTP/HTTPS地址", 400)

    return {
        'service_type': service_type,
        'endpoint': endpoint,
        'model': model,
        'api_key': api_key,
        'messages': messages,
        'options': data.get('options') or {}
    }


def _build_llm_request_body(normalized: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, str]]:
    """构造上游LLM请求体和请求头。"""
    options = normalized['options']
    service_type = normalized['service_type']

    headers = {'Content-Type': 'application/json'}

    if service_type == 'ollama':
        request_body = {
            'model': normalized['model'],
            'messages': normalized['messages'],
            'stream': False,
            'options': {
                'temperature': options.get('temperature', 0.5),
                'top_p': options.get('top_p', 0.8),
                'top_k': options.get('top_k', 40),
                'repeat_penalty': options.get('repeat_penalty', 1.1),
                'num_predict': min(int(options.get('max_tokens', 8192)), 8192),
                'num_ctx': int(options.get('num_ctx', 32768)),
                'stop': options.get('stop', ['<|im_end|>', '</s>']),
                'num_thread': options.get('num_thread', -1),
                'num_gpu': options.get('num_gpu', -1)
            },
            'keep_alive': options.get('keep_alive', '10m')
        }
    else:
        if normalized.get('api_key'):
            headers['Authorization'] = f"Bearer {normalized['api_key']}"

        request_body = {
            'model': normalized['model'],
            'messages': normalized['messages'],
            'temperature': options.get('temperature', 0.7),
            'top_p': options.get('top_p', 0.9),
            'max_tokens': options.get('max_tokens', 8192),
            'stream': False
        }

    return request_body, headers


def _strip_llm_reasoning_preface(content: str) -> str:
    """移除未带思考标签但出现在纪要正文前的模型推理说明。"""
    if not content:
        return ''

    heading_match = re.search(
        r'(?m)^\s*(?:#{1,6}\s*)?(?:(?:会议主题|发言人)\s*[:：].*|(?:会议纪要|会议摘要(?:（300字）|\(300字\))?|会议基本信息|主要内容|主要议题讨论|本段落主要议题|重要决策|待办事项|后续安排)\s*[:：]?\s*)$',
        content
    )
    if not heading_match or heading_match.start() == 0:
        return content.strip()

    prefix = content[:heading_match.start()].strip()
    if not prefix:
        return content[heading_match.start():].strip()

    reasoning_markers = (
        "我现在需要",
        "首先",
        "接下来",
        "用户提供",
        "根据用户",
        "需要根据",
        "逐项分析",
        "开始分析",
        "确保",
        "推理",
        "思考",
        "好的",
        "以下是"
    )
    if len(prefix) <= 1000 or any(marker in prefix for marker in reasoning_markers):
        return content[heading_match.start():].strip()

    return content.strip()


def _strip_llm_thinking_content(content: str) -> str:
    """移除推理模型误放进正文的思考标签内容。"""
    if not content:
        return ''

    cleaned = re.sub(
        r'<(think|thinking)\b[^>]*>.*?</\1>',
        '',
        content,
        flags=re.IGNORECASE | re.DOTALL
    ).strip()

    if re.match(r'^<(think|thinking)\b', cleaned, flags=re.IGNORECASE):
        heading_match = re.search(r'(?m)^\s*#{1,6}\s+', cleaned)
        if heading_match:
            cleaned = cleaned[heading_match.start():].strip()

    return _strip_llm_reasoning_preface(cleaned)


def _parse_llm_response(service_type: str, response_data: Dict[str, Any]) -> Dict[str, Any]:
    """解析不同LLM服务的响应。"""
    if service_type == 'ollama':
        message = response_data.get('message') or {}
        content = _strip_llm_thinking_content((message.get('content') or '').strip())
        if not content:
            raise APIError("Ollama API返回数据格式错误", 502)

        return {
            'content': content,
            'usage': {
                'prompt_tokens': response_data.get('prompt_eval_count'),
                'completion_tokens': response_data.get('eval_count'),
                'total_tokens': (
                    (response_data.get('prompt_eval_count') or 0) +
                    (response_data.get('eval_count') or 0)
                )
            },
            'metrics': {
                'total_duration': response_data.get('total_duration'),
                'load_duration': response_data.get('load_duration'),
                'prompt_eval_duration': response_data.get('prompt_eval_duration'),
                'eval_duration': response_data.get('eval_duration')
            }
        }

    choices = response_data.get('choices') or []
    if not choices or not choices[0].get('message'):
        raise APIError("OpenAI兼容API返回数据格式错误", 502)

    content = _strip_llm_thinking_content((choices[0]['message'].get('content') or '').strip())
    if not content:
        raise APIError("OpenAI兼容API返回内容为空", 502)

    return {
        'content': content,
        'usage': response_data.get('usage'),
        'finish_reason': choices[0].get('finish_reason')
    }


def _call_llm_gateway(payload: Dict[str, Any]) -> Dict[str, Any]:
    """通过后端网关调用上游LLM。"""
    normalized = _extract_llm_request(payload)
    request_body, headers = _build_llm_request_body(normalized)
    start_time = time.time()

    logger.info(
        "转发LLM请求: service=%s endpoint=%s model=%s messages=%s",
        normalized['service_type'],
        normalized['endpoint'],
        normalized['model'],
        len(normalized['messages'])
    )

    try:
        response = requests.post(
            normalized['endpoint'],
            json=request_body,
            headers=headers,
            timeout=LLM_TASK_TIMEOUT,
            verify=_get_llm_verify_setting()
        )
    except requests.RequestException as e:
        raise APIError(f"LLM上游服务请求失败: {str(e)}", 502)

    duration = time.time() - start_time

    if not response.ok:
        error_text = response.text
        try:
            error_json = response.json()
            error_text = error_json.get('error') or error_json.get('message') or error_text
        except Exception:
            pass

        raise APIError(f"LLM上游服务异常: {response.status_code} - {error_text}", 502)

    try:
        response_data = response.json()
    except ValueError:
        raise APIError("LLM上游服务返回非JSON数据", 502)

    parsed = _parse_llm_response(normalized['service_type'], response_data)
    parsed.update({
        'service_type': normalized['service_type'],
        'model': normalized['model'],
        'duration_seconds': round(duration, 3)
    })

    return parsed


def _prune_llm_tasks() -> None:
    """清理已完成的旧任务，避免内存无限增长。"""
    now = time.time()
    expire_seconds = 2 * 60 * 60

    with llm_tasks_lock:
        expired_task_ids = [
            task_id for task_id, task in llm_tasks.items()
            if task.get('status') in {'succeeded', 'failed'} and
            now - task.get('updated_at_ts', now) > expire_seconds
        ]
        for task_id in expired_task_ids:
            llm_tasks.pop(task_id, None)


def _run_llm_task(task_id: str, payload: Dict[str, Any]) -> None:
    """执行LLM任务并更新内存状态。"""
    with llm_tasks_lock:
        if task_id in llm_tasks:
            llm_tasks[task_id].update({
                'status': 'running',
                'updated_at': datetime.now().isoformat(),
                'updated_at_ts': time.time()
            })

    try:
        result = _call_llm_gateway(payload)
        with llm_tasks_lock:
            llm_tasks[task_id].update({
                'status': 'succeeded',
                'result': result,
                'updated_at': datetime.now().isoformat(),
                'updated_at_ts': time.time()
            })
    except Exception as e:
        logger.error(f"LLM任务失败 task_id={task_id}: {e}")
        with llm_tasks_lock:
            llm_tasks[task_id].update({
                'status': 'failed',
                'error': str(e),
                'updated_at': datetime.now().isoformat(),
                'updated_at_ts': time.time()
            })


@app.route('/api/llm/chat', methods=['POST'])
@handle_database_error
def llm_chat():
    """同步LLM网关接口。"""
    data = request.get_json()
    result = _call_llm_gateway(data)
    return create_response(result, "LLM请求完成")


@app.route('/api/llm/tasks', methods=['POST'])
@handle_database_error
def create_llm_task():
    """创建异步LLM任务。"""
    data = request.get_json()
    _extract_llm_request(data)
    _prune_llm_tasks()

    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    with llm_tasks_lock:
        llm_tasks[task_id] = {
            'task_id': task_id,
            'status': 'queued',
            'created_at': now,
            'updated_at': now,
            'updated_at_ts': time.time()
        }

    llm_task_executor.submit(_run_llm_task, task_id, data)
    return create_response({'task_id': task_id, 'status': 'queued'}, "LLM任务已创建", 202)


@app.route('/api/llm/tasks/<task_id>', methods=['GET'])
@handle_database_error
def get_llm_task(task_id: str):
    """查询异步LLM任务状态。"""
    with llm_tasks_lock:
        task = llm_tasks.get(task_id)
        if not task:
            raise APIError("LLM任务不存在或已过期", 404)

        safe_task = {key: value for key, value in task.items() if key != 'updated_at_ts'}

    return create_response(safe_task, "LLM任务状态")


# ============================================================================
# 会议纪要生成任务API
# ============================================================================

def _estimate_summary_tokens(text: str) -> int:
    """估算会议纪要生成使用的token数量。"""
    import re

    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text or ''))
    english_words = len(re.findall(r'[a-zA-Z]+', text or ''))
    other_chars = max(len(text or '') - chinese_chars - english_words, 0)

    return int(
        chinese_chars * SUMMARY_MODEL_CONFIG['chinese_char_to_token_ratio'] +
        english_words * SUMMARY_MODEL_CONFIG['english_word_to_token_ratio'] +
        other_chars * 0.5
    ) + 1


def _summary_text_char_count(text: str) -> int:
    """统计用于会议纪要分段的非空白字符数。"""
    return len(re.sub(r'\s+', '', text or ''))


def _segment_summary_text(text: str, system_prompt_tokens: int, max_chars: Optional[int] = None) -> List[str]:
    """按固定字数智能分段，避免依赖上游模型真实上下文长度。"""
    import re

    max_segment_chars = max(int(max_chars or SUMMARY_MODEL_CONFIG['segment_max_chars']), 1000)

    paragraphs = [p.strip() for p in re.split(r'(?:\r?\n){2,}', text or '') if p.strip()]
    if not paragraphs:
        return []

    segments = []
    current_segment = ''
    current_chars = 0

    for paragraph in paragraphs:
        paragraph_chars = _summary_text_char_count(paragraph)

        if paragraph_chars > max_segment_chars:
            if current_segment:
                segments.append(current_segment)
                current_segment = ''
                current_chars = 0

            sentences = [s.strip() for s in re.split(r'[。！？.!?]', paragraph) if s.strip()]
            temp_segment = ''
            temp_chars = 0

            for sentence in sentences:
                sentence_text = f"{sentence}。"
                sentence_chars = _summary_text_char_count(sentence_text)

                if sentence_chars > max_segment_chars:
                    if temp_segment:
                        segments.append(temp_segment)
                        temp_segment = ''
                        temp_chars = 0

                    for i in range(0, len(sentence), max_segment_chars):
                        chunk = sentence[i:i + max_segment_chars].strip()
                        if chunk:
                            segments.append(f"{chunk}。")
                elif temp_chars + sentence_chars > max_segment_chars:
                    if temp_segment:
                        segments.append(temp_segment)
                    temp_segment = sentence_text
                    temp_chars = sentence_chars
                else:
                    temp_segment += sentence_text
                    temp_chars += sentence_chars

            if temp_segment:
                segments.append(temp_segment)
            continue

        if current_chars + paragraph_chars > max_segment_chars:
            if current_segment:
                segments.append(current_segment)
            current_segment = paragraph
            current_chars = paragraph_chars
        else:
            current_segment = f"{current_segment}\n\n{paragraph}" if current_segment else paragraph
            current_chars += paragraph_chars

    if current_segment:
        segments.append(current_segment)

    return segments


def _summary_text_contains_cjk(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text or ''))


def _summary_text_looks_like_english_translation(text: str) -> bool:
    letters = len(re.findall(r'[A-Za-z]', text or ''))
    english_words = len(re.findall(r'[A-Za-z]{2,}', text or ''))
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff]', text or ''))
    return letters >= 40 and english_words >= 8 and letters > cjk_chars * 3


def _strip_translations_for_summary_text(transcript: str) -> str:
    """过滤中英翻译模式下混入会议纪要输入的译文内容。"""
    if not transcript:
        return ''

    kept_lines = []
    has_cjk_context = False
    for raw_line in transcript.splitlines():
        line = raw_line.strip()
        if re.match(r'^(翻译|译文|Translation|Translated)\s*[:：]', line, flags=re.IGNORECASE):
            continue

        if _summary_text_contains_cjk(line):
            has_cjk_context = True
            kept_lines.append(raw_line)
            continue

        if has_cjk_context and _summary_text_looks_like_english_translation(line):
            continue

        kept_lines.append(raw_line)

    blocks = [
        block.strip()
        for block in re.split(r'(?:\r?\n){2,}', "\n".join(kept_lines))
        if block.strip()
    ]

    while (
        len(blocks) > 1 and
        _summary_text_contains_cjk("\n\n".join(blocks[:-1])) and
        _summary_text_looks_like_english_translation(blocks[-1])
    ):
        blocks.pop()

    return "\n\n".join(blocks).strip()


def _normalize_summary_template_id(template_id: Optional[str]) -> str:
    template = (template_id or SUMMARY_TEMPLATE_STANDARD).strip()
    return template if template in SUMMARY_TEMPLATE_IDS else SUMMARY_TEMPLATE_STANDARD


def _append_summary_custom_requirements(prompt: str, custom_requirements: str = None) -> str:
    if custom_requirements:
        prompt += f"\n\n额外要求：\n{custom_requirements}"
    return prompt


def _create_project_review_system_prompt(custom_requirements: str = None, merge: bool = False) -> str:
    intro = (
        "你是专业会议纪要整理助手。下面输入的是多个分段生成的会议纪要片段，请去重、归并、重组，"
        "合并为一份完整的“方案评审型会议纪要”。不要保留“第1段/第2段”等分段痕迹。"
        if merge else
        "你是专业会议纪要整理助手。请基于提供的会议转录内容，生成一份“方案评审型会议纪要”。"
    )
    source_label = "片段" if merge else "转录文本"
    prompt = f"""{intro}

输出必须使用以下结构：

会议主题：[用一句话概括会议核心主题，优先使用{source_label}中明确提到的系统、项目、方案名称]
发言人：[仅列出{source_label}中实际出现的发言人名称，用顿号分隔；不要虚构]
会议摘要：[用一段话概括本次会议讨论的核心事项、形成的结论、后续推进方向，控制在150-300字]

---

一、[一级议题名称]
[用一段话概括该议题的讨论背景、目标和结论]

1. [二级主题]
[整理该主题下的具体讨论内容、统计口径、规则、方案、争议点或结论。必须保留关键名词、系统名称、业务口径、数字、流程节点等信息。]

2. [二级主题]
[继续整理同一一级议题下的相关内容。]

二、[一级议题名称]
[继续按同样格式整理。]

---

四、待办事项
[仅提取会议中明确要求后续推进、测试、调整、沟通、提供资料、更新文档等事项。每条单独一行。格式为：任务内容。 @负责人]
[如果负责人不明确，使用 @待确认]
[如果没有明确待办事项，输出：本次转录中未明确待办事项。]

严格要求：
- 只基于{source_label}整理，不得虚构会议主题、发言人、任务、负责人、时间、结论。
- 不要输出“会议基本信息”“主要议题讨论”等标准模板标题。
- 一级标题使用中文数字编号：一、二、三、四。
- 二级条目使用阿拉伯数字编号：1. 2. 3.
- 每个一级议题下先写一段概括，再写二级条目。
- 待办事项必须尽量写成可执行动作，并在末尾标注 @负责人。
- 如果原文中出现多个系统、多个方案，需要按主题归类，不要按发言顺序机械堆叠。
- 保留业务术语和关键细节，例如统计口径、审批节点、测试环境、权限视图、上线策略、数据范围等。
- 不输出思考过程、分析过程、解释说明或任何 <think> 标签。
"""

    return f"{_append_summary_custom_requirements(prompt, custom_requirements)}\n\n/no_think"


def _create_summary_system_prompt(custom_requirements: str = None, template_id: str = None) -> str:
    if _normalize_summary_template_id(template_id) == SUMMARY_TEMPLATE_PROJECT_REVIEW:
        return _create_project_review_system_prompt(custom_requirements)

    return _create_single_segment_final_system_prompt(custom_requirements, template_id).replace(
        "请基于提供的单段会议录音转写文本",
        "请基于提供的会议录音转写文本"
    )


def _create_segment_system_prompt(current: int, total: int, custom_requirements: str = None) -> str:
    prompt = f"""你是一个专业的会议纪要生成专家。这是一段较长会议内容的第{current}部分（共{total}部分）。

请为这部分内容生成结构化的纪要片段，重点关注：
1. 保持与其他部分的连贯性
2. 提取本段落的关键信息
3. 避免重复内容
4. 保持信息的完整性和准确性
5. 直接输出纪要内容，不需要思考过程

生成格式：
## 本段落主要议题
▸ 议题：[仅记录转录中明确讨论的具体话题，数量根据实际内容决定]
  - 讨论要点：[仅记录转录中的实际讨论内容，不得虚构]
  - 关键数据：[仅包含转录中明确提及的数字、百分比、金额等，不得虚构]
  - 各方观点：[仅记录转录中不同发言人的实际观点，不得虚构]
  - 达成共识：[仅记录转录中明确表达的一致意见，不得虚构]
  - 重要细节：[记录本段落中提到的重要细节信息，不得虚构]

## 重要信息
- 决策事项：[仅记录转录中明确的决策，如无则省略]
- 行动项：[仅记录转录中明确的任务，如无则省略]
- 时间节点：[仅记录转录中明确的时间，如无则省略]
- 参与人员：[仅记录转录中明确提及的人员，不得虚构]

特别要求：
- 严格基于提供的转录文本内容，绝对不添加、推测或虚构任何信息
- 保持所有具体信息的准确性，仅使用转录中的实际内容
- 对于转录中没有的信息，直接省略相关部分，不要标注"需补充"
- 只记录转录中实际存在的讨论点，不要为了完整性而添加内容
- 请直接输出纪要片段，不要包含思考过程或推理步骤
- 严禁输出<think>、</think>、<thinking>、</thinking>等任何思考标签
- 严禁输出任何形式的推理过程、内心独白或分析过程
- 严禁使用"我认为"、"我觉得"、"让我想想"等主观表达
- 严禁虚构议题、观点、数据、人员等任何信息
- 禁用所有形式的思维链(Chain of Thought)输出
"""

    if custom_requirements:
        prompt += f"\n\n额外要求：\n{custom_requirements}"

    return f"{prompt}\n\n/no_think"


def _create_merge_system_prompt(custom_requirements: str = None, template_id: str = None) -> str:
    if _normalize_summary_template_id(template_id) == SUMMARY_TEMPLATE_PROJECT_REVIEW:
        return _create_project_review_system_prompt(custom_requirements, merge=True)

    prompt = """你是一个专业的会议纪要整理助手。请将多个会议纪要片段合并成一份完整、连贯的会议纪要。

合并要求：
1. 保持所有重要信息和关键细节，避免遗漏任何具体内容
2. 统一格式，确保所有段落使用相同的结构
3. 将对应的内容归类整合到统一的标准格式中
4. 保持原有的具体数据、时间、人名、数字等关键细节不变，不得虚构，如果没有就不显示
5. 将各片段中的关键细节整合到相应的议题讨论下
6. 会议摘要应覆盖核心内容；转录内容较少时不强求字数
7. 去除重复内容，但保留所有独特信息和细节

标准输出格式：
## 会议基本信息
- 会议时间：[从各片段中提取，不得虚构，如果没有就不显示]
- 会议地点：[从各片段中提取，不得虚构，如果没有就不显示]
- 参与者：[合并所有提到的参与者，不得虚构，如果没有就不显示]
- 会议主题和目标：[整合各片段的主题]

## 会议摘要
[整合所有片段的核心内容、目标与结论，不得虚构；内容较少时保持简洁]

## 主要议题讨论
[按时间顺序整理，合并所有片段的讨论要点，议题数量根据实际内容决定，将关键细节整合到相应议题下]
▸ 议题名称：[整合所有讨论主题]
  - 讨论要点：[详细记录所有讨论内容和关键细节]
  - 关键数据：[合并所有具体数字、百分比、金额等关键细节]
  - 各方观点：[汇总各方观点和意见，包含具体细节]
  - 达成共识：[整理已达成共识的结论，包含具体细节]
  - 重要细节：[整合各片段中提到的重要细节信息]

## 重要决策
[合并所有片段中的决策事项]
▸ [整合决策内容]
▸ [合并决策依据和影响]
▸ [统一时间节点]

## 待办事项
[汇总所有片段的任务]
▸ [合并任务内容]
▸ [整理负责人信息，不得虚构，如果没有就不显示]
▸ [统一截止时间]
▸ [合并优先级和依赖关系]

## 后续安排
[整合所有后续计划]
- [合并下次会议安排]
- [汇总跟进事项]
- [整理风险点和注意事项]

特别要求：
7. 重点关注关键细节的保留：确保所有具体数字、时间点、人员姓名、技术参数等细节信息都被整合到相应的议题下
8. 细节归类整合：将散布在各片段中的相关细节信息归类到同一议题下，形成完整的讨论记录
9. 直接输出合并后的会议纪要，不需要思考过程或解释
10. 严禁输出<think>、</think>、<thinking>、</thinking>等任何思考标签
11. 严禁输出任何形式的推理过程、内心独白或分析过程
12. 严禁使用"我认为"、"我觉得"、"让我想想"等主观表达
13. 禁用所有形式的思维链(Chain of Thought)输出
14. 只输出纯净的会议纪要内容，不包含任何元信息

请合并以下会议纪要片段：
"""

    if custom_requirements:
        prompt += f"\n\n额外要求：\n{custom_requirements}"

    return f"{prompt}\n\n/no_think"


def _create_single_segment_final_system_prompt(custom_requirements: str = None, template_id: str = None) -> str:
    if _normalize_summary_template_id(template_id) == SUMMARY_TEMPLATE_PROJECT_REVIEW:
        return _create_project_review_system_prompt(custom_requirements)

    prompt = """你是一个专业的会议纪要生成专家。请基于提供的单段会议录音转写文本，直接生成最终版会议纪要。

生成要求：
- 会议摘要用300-450字概括会议核心目标与最终结论。
- 主要内容按议题分点整理，最少20条；每条必须只基于转录文本中明确提到的信息。
- 仅提取明确提到的信息，不推测未说明的细节。
- 如果转录中明确议题不足20条，不得虚构补齐。

标准输出格式：
## 会议基本信息
- 会议时间：[从各片段中提取，不得虚构，如果没有就不显示]
- 会议地点：[从各片段中提取，不得虚构，如果没有就不显示]
- 参与者：[合并所有提到的参与者，不得虚构，如果没有就不显示]
- 会议主题和目标：[整合各片段的主题]
## 会议摘要
[用300-450字概括会议核心目标与最终结论；仅提取明确提到的信息，不推测未说明的细节]

## 主要议题讨论
[按议题分点整理，最少20条；不够20条就按实际条数来写，仅记录转录文本中实际讨论的议题，按讨论顺序整理]
▸ 议题1：[讨论主题，直接引用会议中的命名]
    - 讨论要点：[详细记录所有讨论内容和关键细节]
    - 关键数据：[合并所有具体数字、百分比、金额等关键细节]
    - 各方观点：[汇总各方观点和意见，包含具体细节]
    - 达成共识：[整理已达成共识的结论，包含具体细节]
    - 重要细节：[整合文中提到的重要细节信息]

## 重要决策
[合并所有片段中的决策事项]
▸ [整合决策内容]
▸ [合并决策依据和影响]
▸ [统一时间节点，不得虚构，如果没有就不显示]

## 待办事项
[仅记录会议中明确指定的任务；最少5条；不够5条就按实际条数来写，没有则标注“转录中未涉及具体待办事项”]
▸ 任务内容：[直接引用任务描述原话]
▸ 负责人：[以会议中指定的称呼为准；未明确则标注“待确认”]
▸ 截止时间：[格式：YYYY/MM/DD，不得虚构，如果没有就不显示]

## 后续安排
[仅记录会议中明确指定的任务；最少5条；不够5条就按实际条数来写，没有则标注“转录中未涉及后续安排”]
- [下次会议安排，不得虚构，如果没有就不显示]
- [跟进事项，不得虚构，如果没有就不显示]
- [整理风险点和注意事项，不得虚构，如果没有就不显示]

特别要求：
- 严禁输出交互内容
- 若任务要求存在模糊处，标注需补充说明而非自行解释。
- 严格基于转录文本，绝对不添加、推测或虚构任何信息。
- 请直接输出会议纪要，不要包含思考过程或推理步骤。
- 严禁输出<think>、</think>、<thinking>、</thinking>等任何思考标签。
- 严禁输出任何形式的推理过程、内心独白或分析过程。
- 严禁使用"我认为"、"我觉得"、"让我想想"等主观表达。
- 禁用所有形式的思维链(Chain of Thought)输出。
"""

    if custom_requirements:
        prompt += f"\n\n额外要求：\n{custom_requirements}"

    return f"{prompt}\n\n/no_think"


def _normalize_summary_generation_options(
    generation_options: Dict[str, Any],
    available_output_tokens: Optional[int] = None
) -> Dict[str, Any]:
    options = dict(generation_options or {})
    max_output_tokens = int(SUMMARY_MODEL_CONFIG['max_output_tokens'])

    try:
        requested_output_tokens = int(options.get('max_tokens') or max_output_tokens)
    except (TypeError, ValueError):
        requested_output_tokens = max_output_tokens

    if requested_output_tokens <= 0:
        requested_output_tokens = max_output_tokens

    if available_output_tokens is not None:
        requested_output_tokens = min(requested_output_tokens, max(int(available_output_tokens), 0))

    options['max_tokens'] = min(requested_output_tokens, max_output_tokens)
    return options


def _limit_summary_generation_options(generation_options: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
    options = dict(generation_options or {})
    try:
        requested_tokens = int(options.get('max_tokens') or max_tokens)
    except (TypeError, ValueError):
        requested_tokens = max_tokens
    options['max_tokens'] = min(max(requested_tokens, 1), int(max_tokens))
    return options


def _build_summary_llm_payload(
    messages: List[Dict[str, str]],
    llm_config: Dict[str, Any],
    generation_options: Dict[str, Any],
    temperature: float = None,
    top_p: float = None
) -> Dict[str, Any]:
    options = dict(generation_options or {})
    if temperature is not None:
        options['temperature'] = temperature
    if top_p is not None:
        options['top_p'] = top_p
    options = _normalize_summary_generation_options(options)

    return {
        'serviceType': llm_config.get('serviceType') or llm_config.get('service_type'),
        'config': llm_config.get('config') or {},
        'messages': messages,
        'options': options
    }


def _call_summary_llm(
    messages: List[Dict[str, str]],
    llm_config: Dict[str, Any],
    generation_options: Dict[str, Any],
    temperature: float = None,
    top_p: float = None
) -> str:
    payload = _build_summary_llm_payload(messages, llm_config, generation_options, temperature, top_p)
    result = _call_llm_gateway(payload)
    content = result.get('content')
    if not content:
        raise APIError("LLM返回的纪要内容为空", 502)
    return content


def _generate_direct_summary_backend(
    transcript: str,
    llm_config: Dict[str, Any],
    generation_options: Dict[str, Any],
    custom_requirements: str = None,
    template_id: str = None
) -> str:
    system_prompt = _create_summary_system_prompt(custom_requirements, template_id)
    user_content = f"会议转录内容：\n{transcript}"
    input_tokens = _estimate_summary_tokens(system_prompt) + _estimate_summary_tokens(user_content)
    available_output_tokens = SUMMARY_MODEL_CONFIG['max_context_tokens'] - input_tokens - 2000

    if available_output_tokens < SUMMARY_MODEL_CONFIG['min_output_tokens']:
        raise APIError("CONTENT_TOO_LONG", 413)

    direct_generation_options = _normalize_summary_generation_options(
        generation_options,
        available_output_tokens
    )

    return _call_summary_llm([
        {'role': 'system', 'content': _append_summary_no_think(system_prompt)},
        {'role': 'user', 'content': _append_summary_no_think(user_content)}
    ], llm_config, direct_generation_options, temperature=0.5, top_p=0.8)


def _generate_single_segment_final_summary_backend(
    transcript: str,
    llm_config: Dict[str, Any],
    generation_options: Dict[str, Any],
    custom_requirements: str = None,
    template_id: str = None
) -> str:
    system_prompt = _create_single_segment_final_system_prompt(custom_requirements, template_id)
    user_content = f"会议转录内容：\n{transcript}"
    input_tokens = _estimate_summary_tokens(system_prompt) + _estimate_summary_tokens(user_content)
    available_output_tokens = SUMMARY_MODEL_CONFIG['max_context_tokens'] - input_tokens - 2000

    if available_output_tokens < SUMMARY_MODEL_CONFIG['min_output_tokens']:
        raise APIError("CONTENT_TOO_LONG", 413)

    final_generation_options = _normalize_summary_generation_options(
        generation_options,
        available_output_tokens
    )

    return _call_summary_llm([
        {'role': 'system', 'content': _append_summary_no_think(system_prompt)},
        {'role': 'user', 'content': _append_summary_no_think(user_content)}
    ], llm_config, final_generation_options, temperature=0.5, top_p=0.8)


def _generate_segment_summary_backend(
    segment_text: str,
    llm_config: Dict[str, Any],
    generation_options: Dict[str, Any],
    current: int,
    total: int,
    custom_requirements: str = None
) -> str:
    system_prompt = _create_segment_system_prompt(current, total, custom_requirements)
    user_content = f"这是会议内容的第{current}部分（共{total}部分）：\n\n{segment_text}"

    return _call_summary_llm([
        {'role': 'system', 'content': _append_summary_no_think(system_prompt)},
        {'role': 'user', 'content': _append_summary_no_think(user_content)}
    ], llm_config, generation_options, temperature=0.5, top_p=0.8)


def _merge_summary_segments_backend(
    summaries: List[str],
    llm_config: Dict[str, Any],
    generation_options: Dict[str, Any],
    custom_requirements: str = None,
    template_id: str = None
) -> str:
    if not summaries:
        raise APIError("没有可合并的纪要片段", 400)
    if len(summaries) == 1:
        return summaries[0]

    system_prompt = _create_merge_system_prompt(custom_requirements, template_id)
    content = "\n\n---分段---\n\n".join(summaries)

    if (
        _estimate_summary_tokens(system_prompt) + _estimate_summary_tokens(content) >
        SUMMARY_MODEL_CONFIG['max_context_tokens'] - SUMMARY_MODEL_CONFIG['max_output_tokens']
    ):
        batch_size = max((len(summaries) + 1) // 2, 1)
        merged_batches = []
        for i in range(0, len(summaries), batch_size):
            merged_batches.append(_merge_summary_segments_backend(
                summaries[i:i + batch_size],
                llm_config,
                generation_options,
                custom_requirements,
                template_id
            ))
        return _merge_summary_segments_backend(merged_batches, llm_config, generation_options, custom_requirements, template_id)

    return _call_summary_llm([
        {'role': 'system', 'content': _append_summary_no_think(system_prompt)},
        {'role': 'user', 'content': _append_summary_no_think(content)}
    ], llm_config, generation_options, temperature=0.5, top_p=0.8)


def _generate_segmented_summary_backend(
    task_id: str,
    transcript: str,
    llm_config: Dict[str, Any],
    generation_options: Dict[str, Any],
    custom_requirements: str = None,
    template_id: str = None,
    stage_prefix: str = '文本较长，开始分段'
) -> Tuple[str, str, int]:
    _update_summary_task(task_id, {
        'progress': 20,
        'stage': stage_prefix
    })

    system_tokens = _estimate_summary_tokens(_create_summary_system_prompt(custom_requirements, template_id))
    segments = _segment_summary_text(transcript, system_tokens)
    if not segments:
        raise APIError("分段结果为空", 400)

    segment_options = _limit_summary_generation_options(
        generation_options,
        SUMMARY_MODEL_CONFIG['segment_max_output_tokens']
    )
    merge_options = _limit_summary_generation_options(
        generation_options,
        SUMMARY_MODEL_CONFIG['merge_max_output_tokens']
    )

    if len(segments) == 1:
        _update_summary_task(task_id, {
            'progress': 35,
            'stage': '单段文本，直接生成正式会议纪要'
        })
        summary = _generate_single_segment_final_summary_backend(
            segments[0],
            llm_config,
            merge_options,
            custom_requirements,
            template_id
        )
        return summary, 'direct_after_segmentation', 1

    segment_summaries = []
    for index, segment_text in enumerate(segments, 1):
        progress = 20 + int(index / len(segments) * 55)
        _update_summary_task(task_id, {
            'progress': progress,
            'stage': f'正在处理第 {index}/{len(segments)} 个文本段落'
        })
        segment_summaries.append(_generate_segment_summary_backend(
            segment_text,
            llm_config,
            segment_options,
            index,
            len(segments),
            custom_requirements
        ))

    _update_summary_task(task_id, {
        'progress': 82,
        'stage': '正在合并会议纪要片段'
    })
    summary = _merge_summary_segments_backend(
        segment_summaries,
        llm_config,
        merge_options,
        custom_requirements,
        template_id
    )
    return summary, 'segmented', len(segments)


def _update_summary_task(task_id: str, updates: Dict[str, Any]) -> None:
    with summary_tasks_lock:
        if task_id in summary_tasks:
            updates.setdefault('updated_at', datetime.now().isoformat())
            updates.setdefault('updated_at_ts', time.time())
            summary_tasks[task_id].update(updates)


def _generate_summary_backend(task_id: str, payload: Dict[str, Any]) -> None:
    transcript = _strip_translations_for_summary_text(payload.get('transcript') or '').strip()
    if not transcript:
        raise APIError("没有可用的语音转写内容", 400)

    llm_config = payload.get('llm') or {}

    generation_options = payload.get('options') or {}
    custom_requirements = payload.get('customRequirements') or generation_options.get('customRequirements')
    template_id = _normalize_summary_template_id(
        payload.get('templateId') or
        payload.get('template_id') or
        generation_options.get('templateId') or
        generation_options.get('template_id')
    )
    meeting_id = payload.get('meeting_id') or payload.get('meetingId')

    _update_summary_task(task_id, {
        'status': 'running',
        'progress': 5,
        'stage': '开始生成会议纪要'
    })

    try:
        transcript_chars = _summary_text_char_count(transcript)
        direct_max_chars = int(SUMMARY_MODEL_CONFIG['direct_max_chars'])

        if transcript_chars > direct_max_chars:
            summary, mode, segments_count = _generate_segmented_summary_backend(
                task_id,
                transcript,
                llm_config,
                generation_options,
                custom_requirements,
                template_id=template_id,
                stage_prefix=f'转写内容约 {transcript_chars} 字，超过 {direct_max_chars} 字安全阈值，开始分段'
            )
        else:
            _update_summary_task(task_id, {
                'progress': 15,
                'stage': '直接处理完整转写文本'
            })
            try:
                summary = _generate_direct_summary_backend(
                    transcript,
                    llm_config,
                    generation_options,
                    custom_requirements,
                    template_id
                )
                mode = 'direct'
                segments_count = 1
            except APIError as e:
                if str(e) != 'CONTENT_TOO_LONG':
                    raise

                summary, mode, segments_count = _generate_segmented_summary_backend(
                    task_id,
                    transcript,
                    llm_config,
                    generation_options,
                    custom_requirements,
                    template_id=template_id,
                    stage_prefix='文本超过模型上下文，开始分段'
                )

        minutes_id = None
        if meeting_id:
            meeting = db.get_meeting(int(meeting_id))
            if not meeting:
                raise APIError(f"会议ID {meeting_id} 不存在", 404)
            minutes_id = db.save_meeting_minutes(meeting_id=int(meeting_id), summary=summary)

        _update_summary_task(task_id, {
            'status': 'succeeded',
            'progress': 100,
            'stage': '会议纪要生成完成',
            'result': {
                'summary': summary,
                'mode': mode,
                'segments_count': segments_count,
                'template_id': template_id,
                'meeting_id': int(meeting_id) if meeting_id else None,
                'minutes_id': minutes_id
            }
        })
    except Exception as e:
        logger.error(f"会议纪要任务失败 task_id={task_id}: {e}")
        _update_summary_task(task_id, {
            'status': 'failed',
            'stage': '会议纪要生成失败',
            'error': str(e)
        })


def _prune_summary_tasks() -> None:
    now = time.time()
    expire_seconds = 2 * 60 * 60

    with summary_tasks_lock:
        expired_task_ids = [
            task_id for task_id, task in summary_tasks.items()
            if task.get('status') in {'succeeded', 'failed'} and
            now - task.get('updated_at_ts', now) > expire_seconds
        ]
        for task_id in expired_task_ids:
            summary_tasks.pop(task_id, None)


@app.route('/api/summary/tasks', methods=['POST'])
@handle_database_error
def create_summary_task():
    """创建后端会议纪要生成任务。"""
    data = request.get_json()
    if not data:
        raise APIError("请求数据不能为空", 400)
    if not (data.get('transcript') or '').strip():
        raise APIError("没有可用的语音转写内容", 400)

    _prune_summary_tasks()
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    with summary_tasks_lock:
        summary_tasks[task_id] = {
            'task_id': task_id,
            'status': 'queued',
            'progress': 0,
            'stage': '已加入会议纪要生成队列',
            'created_at': now,
            'updated_at': now,
            'updated_at_ts': time.time()
        }

    llm_task_executor.submit(_generate_summary_backend, task_id, data)
    return create_response({'task_id': task_id, 'status': 'queued'}, "会议纪要生成任务已创建", 202)


@app.route('/api/summary/tasks/<task_id>', methods=['GET'])
@handle_database_error
def get_summary_task(task_id: str):
    """查询会议纪要生成任务状态。"""
    with summary_tasks_lock:
        task = summary_tasks.get(task_id)
        if not task:
            raise APIError("会议纪要生成任务不存在或已过期", 404)
        safe_task = {key: value for key, value in task.items() if key != 'updated_at_ts'}

    return create_response(safe_task, "会议纪要生成任务状态")


# ============================================================================
# 健康检查API
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    try:
        # 检查数据库连接
        db_info = db.get_database_info()
        
        # 检查分段服务状态
        try:
            segment_status = get_segmentation_status()
        except Exception:
            segment_status = {"is_initialized": False, "error": "服务未初始化"}

        with llm_tasks_lock:
            llm_task_counts = {}
            for task in llm_tasks.values():
                status = task.get('status', 'unknown')
                llm_task_counts[status] = llm_task_counts.get(status, 0) + 1

        with summary_tasks_lock:
            summary_task_counts = {}
            for task in summary_tasks.values():
                status = task.get('status', 'unknown')
                summary_task_counts[status] = summary_task_counts.get(status, 0) + 1
        
        return create_response({
            "status": "healthy",
            "service": "database-api",
            "version": "1.0.0",
            "database": "connected",
            "database_size": db_info.get('database_size', 0),
            "segmentation_service": segment_status,
            "llm_queue": {
                "max_workers": LLM_TASK_MAX_WORKERS,
                "task_counts": llm_task_counts
            },
            "summary_queue": {
                "max_workers": LLM_TASK_MAX_WORKERS,
                "task_counts": summary_task_counts
            }
        }, "服务正常")
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return create_response({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, "服务不健康", 503)


# ============================================================================
# 错误处理
# ============================================================================

@app.errorhandler(400)
def bad_request(error):
    return create_response(None, "请求参数错误", 400)


@app.errorhandler(404)
def not_found(error):
    return create_response(None, "资源不存在", 404)


# ============================================================================
# 音频文件下载API
# ============================================================================

@app.route('/api/audio/download/<filename>', methods=['GET'])
@handle_database_error
def download_audio_file(filename: str):
    """
    下载指定的音频文件
    
    Args:
        filename: 音频文件名
    
    Returns:
        音频文件或错误响应
    """
    try:
        # 安全检查：防止路径穿越攻击
        if ".." in filename or "/" in filename or "\\" in filename:
            raise APIError("非法的文件名", 400)
        
        # 构建文件路径
        audio_dir = os.path.join(os.path.dirname(__file__), "../../../data/audio")
        file_path = os.path.join(audio_dir, filename)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.warning(f"请求的音频文件不存在: {filename}")
            raise APIError(f"音频文件 {filename} 不存在", 404)
        
        # 检查是否为文件（不是目录）
        if not os.path.isfile(file_path):
            logger.warning(f"请求的路径不是文件: {filename}")
            raise APIError("请求的路径不是有效的文件", 400)
        
        logger.info(f"📥 下载音频文件: {filename}")
        
        # 返回文件
        return send_file(
            file_path,
            mimetype='audio/wav',
            as_attachment=True,
            download_name=filename
        )
    
    except APIError:
        raise
    except Exception as e:
        logger.error(f"下载音频文件失败: {filename}, 错误: {e}")
        raise APIError(f"下载文件失败: {str(e)}", 500)


@app.route('/api/audio/list', methods=['GET'])
@handle_database_error
def list_audio_files():
    """
    获取所有音频文件列表
    
    Returns:
        音频文件列表
    """
    try:
        audio_dir = os.path.join(os.path.dirname(__file__), "../../../data/audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        # 获取所有WAV文件
        files = []
        for filename in os.listdir(audio_dir):
            file_path = os.path.join(audio_dir, filename)
            
            # 只列出WAV文件
            if os.path.isfile(file_path) and filename.lower().endswith('.wav'):
                file_stat = os.stat(file_path)
                files.append({
                    "filename": filename,
                    "size": file_stat.st_size,
                    "created_time": file_stat.st_ctime,
                    "modified_time": file_stat.st_mtime,
                    "download_url": f"/api/audio/download/{filename}"
                })
        
        # 按修改时间倒序排列
        files.sort(key=lambda x: x['modified_time'], reverse=True)
        
        return create_response({
            "files": files,
            "total": len(files)
        })
    
    except Exception as e:
        logger.error(f"获取音频文件列表失败: {e}")
        raise APIError(f"获取文件列表失败: {str(e)}", 500)


@app.route('/api/audio/delete/<filename>', methods=['DELETE'])
@handle_database_error
def delete_audio_file_by_filename(filename: str):
    """
    删除指定的音频文件
    
    Args:
        filename: 音频文件名
    
    Returns:
        操作结果
    """
    try:
        # 安全检查：防止路径穿越攻击
        if ".." in filename or "/" in filename or "\\" in filename:
            raise APIError("非法的文件名", 400)
        
        audio_dir = os.path.join(os.path.dirname(__file__), "../../../data/audio")
        file_path = os.path.join(audio_dir, filename)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise APIError(f"音频文件 {filename} 不存在", 404)
        
        # 删除文件
        os.remove(file_path)
        logger.info(f"🗑️ 删除音频文件: {filename}")
        
        return create_response({
            "filename": filename
        }, f"音频文件 {filename} 已删除")
    
    except APIError:
        raise
    except Exception as e:
        logger.error(f"删除音频文件失败: {filename}, 错误: {e}")
        raise APIError(f"删除文件失败: {str(e)}", 500)


# ============================================================================
# 前端静态文件
# ============================================================================

def _ui_dist_exists() -> bool:
    return os.path.isfile(os.path.join(UI_DIST_DIR, "index.html"))


@app.route('/', methods=['GET'])
def serve_ui_index():
    """提供前端构建后的首页。"""
    if not _ui_dist_exists():
        raise NotFound("前端构建产物不存在，请先执行 ui 构建")
    return send_from_directory(UI_DIST_DIR, "index.html")


@app.route('/<path:path>', methods=['GET'])
def serve_ui_static(path: str):
    """提供前端静态资源，并支持 SPA 路由回退。"""
    if path.startswith(('api/', 'data/')):
        raise NotFound()
    if not _ui_dist_exists():
        raise NotFound("前端构建产物不存在，请先执行 ui 构建")

    asset_path = os.path.join(UI_DIST_DIR, path)
    if os.path.isfile(asset_path):
        return send_from_directory(UI_DIST_DIR, path)
    return send_from_directory(UI_DIST_DIR, "index.html")


# ============================================================================
# 错误处理
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    max_size = app.config.get('MAX_CONTENT_LENGTH', 500 * 1024 * 1024)
    max_mb = max_size / (1024 * 1024)
    return create_response(None, f"请求数据过大，最大允许: {max_mb:.0f}MB", 413)


@app.errorhandler(500)
def internal_error(error):
    return create_response(None, "服务器内部错误", 500)


# ============================================================================
# 启动函数
# ============================================================================

def create_app(config=None, server_state=None):
    """创建Flask应用
    
    Args:
        config: Flask配置字典
        server_state: 服务器状态对象
    """
    if config:
        app.config.update(config)

    app.config['SERVER_STATE'] = server_state
    
    # 初始化字幕设置API（如果提供了server_state）
    if server_state is not None:
        init_subtitle_settings_api(server_state)

        try:
            _recover_upload_audio_tasks()
        except Exception as e:
            logger.warning(f"恢复上传识别任务失败: {e}")
    
    return app


def run_api_server(host='0.0.0.0', port=8080, debug=False):
    """运行API服务器"""
    logger.info(f"启动数据库API服务器: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 启动API服务器
    run_api_server(debug=True)
