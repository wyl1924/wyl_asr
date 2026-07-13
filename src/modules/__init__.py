#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模块包初始化文件。

按功能重新组织的模块结构：
- audio: 音频处理相关模块
- speaker: 说话人识别相关模块  
- network: 网络服务相关模块
- database: 数据库相关模块
- config: 配置相关模块
- core: 核心功能模块
"""

# 音频处理模块
from .audio.audio_processing import *
from .audio.audio_duration_handler import *
from .audio.audio_format_handler import *
from .audio.vad_monitor import *

# 说话人识别模块
from .speaker.speaker_manager import *
from .speaker.speaker_verification import *
from .speaker.speaker_labeling import *
from .speaker.hotword_manager import *

# 网络服务模块
from .network.websocket_service import *
from .network.websocket_manager import *
from .network.start_api import *
from .network.translation_service import *

# 数据库模块
from .database.database_api import *
from .database.database_manager import *

# 配置模块
from .config.arg_parser import *
from .config.logging_config import *
from .config.ssl_config import *

# 核心功能模块
from .core.core import *
from .core.server_state import *
from .core.document_segmentation_service import *

__all__ = [
    # 导出所有子模块的公共接口
    # 这里可以根据需要添加具体的类和函数名
]