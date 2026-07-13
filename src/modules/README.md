# 模块结构说明

本项目的模块已按功能重新组织，采用分层架构设计，提高代码的可维护性和可扩展性。

## 目录结构

```
src/modules/
├── __init__.py                 # 模块包初始化文件
├── audio/                      # 音频处理模块
│   ├── __init__.py
│   ├── audio_processing.py     # 核心音频处理逻辑
│   ├── audio_duration_handler.py # 音频时长处理
│   ├── audio_format_handler.py # 音频格式处理
│   └── vad_monitor.py         # 语音活动检测
├── speaker/                    # 说话人识别模块
│   ├── __init__.py
│   ├── speaker_manager.py      # 说话人管理
│   ├── speaker_verification.py # 说话人验证
│   ├── speaker_labeling.py     # 说话人标记
│   └── hotword_manager.py      # 热词管理
├── network/                    # 网络服务模块
│   ├── __init__.py
│   ├── websocket_service.py    # WebSocket服务
│   ├── websocket_manager.py    # WebSocket管理
│   ├── start_api.py           # API启动
│   └── translation_service.py  # 翻译服务
├── database/                   # 数据库模块
│   ├── __init__.py
│   ├── database_api.py         # 数据库API
│   └── database_manager.py     # 数据库管理
├── config/                     # 配置模块
│   ├── __init__.py
│   ├── arg_parser.py          # 参数解析
│   ├── logging_config.py      # 日志配置
│   └── ssl_config.py          # SSL配置
└── core/                       # 核心功能模块
    ├── __init__.py
    ├── core.py                # 核心功能
    ├── server_state.py        # 服务器状态
    └── document_segmentation_service.py # 文档分割服务
```

## 模块功能说明

### 🎵 Audio 模块
负责所有音频相关的处理功能：
- **audio_processing.py**: 核心音频处理逻辑，包括VAD、ASR等
- **audio_duration_handler.py**: 音频时长检测和处理
- **audio_format_handler.py**: 音频格式转换和处理
- **vad_monitor.py**: 语音活动检测监控

### 👤 Speaker 模块
负责说话人识别和管理功能：
- **speaker_manager.py**: 说话人注册、识别、管理
- **speaker_verification.py**: 说话人身份验证
- **speaker_labeling.py**: 动态说话人标记
- **hotword_manager.py**: 热词检测和管理

### 🌐 Network 模块
负责网络通信和服务功能：
- **websocket_service.py**: WebSocket服务核心逻辑
- **websocket_manager.py**: WebSocket连接管理
- **start_api.py**: API服务启动
- **translation_service.py**: 翻译服务

### 🗄️ Database 模块
负责数据存储和管理功能：
- **database_api.py**: 数据库REST API接口
- **database_manager.py**: 数据库连接和操作管理

### ⚙️ Config 模块
负责配置和参数管理功能：
- **arg_parser.py**: 命令行参数解析
- **logging_config.py**: 日志系统配置
- **ssl_config.py**: SSL/TLS配置

### 🔧 Core 模块
负责核心基础功能：
- **core.py**: 核心功能和工具函数
- **server_state.py**: 服务器状态管理
- **document_segmentation_service.py**: 文档分割服务

## 导入方式

### 方式一：直接导入（推荐）
```python
# 导入特定功能
from src.modules.audio.audio_processing import async_asr
from src.modules.speaker.speaker_manager import get_speaker_manager
from src.modules.network.websocket_service import ws_serve
```

### 方式二：通过包导入
```python
# 导入整个模块包（会导入所有子模块）
from src.modules import *
```

## 设计原则

1. **单一职责原则**: 每个模块专注于特定的功能领域
2. **低耦合高内聚**: 模块间依赖关系清晰，内部功能紧密相关
3. **分层架构**: 按照功能层次组织，便于维护和扩展
4. **可测试性**: 模块化设计便于单元测试和集成测试

## 迁移说明

从旧的扁平结构迁移到新的分层结构时，主要变化：

- 原来的 `from .module_name import` 改为 `from ..category.module_name import`
- 主程序中的导入路径需要更新为完整路径
- 所有相对导入都已自动更新

## 扩展指南

添加新功能时，请按照以下原则：

1. 确定功能所属的模块类别
2. 在对应的文件夹中创建新文件
3. 更新对应的 `__init__.py` 文件
4. 在主 `__init__.py` 中添加导入（如需要）
5. 更新相关文档

这种模块化结构使得项目更加清晰、易于维护和扩展。