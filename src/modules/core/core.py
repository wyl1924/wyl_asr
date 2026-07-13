#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WYL ASR 核心模块。

基于FunASR的实时语音识别服务核心模块，提供完整的WebSocket语音识别服务。
"""

# 导入所有核心模块 (按照PEP 8规范：本地模块最后导入)
from ..config.arg_parser import parse_arguments
from ..audio.audio_processing import async_asr, async_asr_online, async_asr_with_speaker, async_vad, async_asr_2pass, async_asr_complete_pipeline
from ..audio.vad_monitor import get_vad_monitor, reset_vad_monitor
from ..config.logging_config import setup_logging
from ..core.server_state import ServerState, load_models
from ..config.ssl_config import setup_ssl_context
from ..network.websocket_manager import clear_websocket, ws_reset
from ..network.websocket_service import ws_serve
from ..speaker.speaker_manager import get_speaker_manager
from ..speaker.speaker_verification import init_speaker_verification
from ..audio.audio_format_handler import init_audio_format_handler, get_audio_format_handler
from ..speaker.speaker_labeling import init_speaker_labeler, get_speaker_labeler, process_speaker_identification

# 导出所有公共接口
__all__ = [
    "setup_logging",
    "parse_arguments",
    "ServerState",
    "load_models",
    "async_vad",
    "async_asr",
    "async_asr_online",
    "async_asr_with_speaker",
    "async_asr_2pass",
    "async_asr_complete_pipeline",
    "ws_reset",
    "clear_websocket",
    "get_speaker_manager",
    "init_speaker_verification",
    "init_audio_format_handler",
    "get_audio_format_handler",
    "init_speaker_labeler",
    "get_speaker_labeler",
    "process_speaker_identification",
    "get_vad_monitor",
    "reset_vad_monitor",
    "ws_serve",                     
    "setup_ssl_context",
]