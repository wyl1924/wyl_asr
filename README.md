# 魔盒AI（Magic Box AI）

[English](README_EN.md) · [中文](README.md)

魔盒AI是一个基于 FunASR 的本地语音内容处理服务，提供实时 WebSocket 转写、音视频文件上传识别，以及配套的会议、说话人、热词、字幕与文档能力。

项目由 Python 后端、Vue 3 管理界面和可选的 .NET 字幕客户端组成。后端在同一进程中启动 WebSocket 服务与 Flask REST API；前端以 Vite 开发服务器运行，或在 Docker 镜像中构建为静态文件由后端提供。

> 模型、运行数据、上传媒体和构建产物均不纳入版本控制。服务只加载本地模型目录；首次运行前请先准备模型。

## 功能范围

| 场景 | 当前实现 |
| --- | --- |
| 实时转写 | 通过 `ws://<host>:10095/` 接收二进制 PCM 音频流，返回在线、离线和 2pass 识别结果。 |
| 文件识别 | 通过 REST API 上传音频或视频，以后台任务形式进行媒体转换、识别、分段、说话人整理与结果查询。 |
| 会议数据 | 保存会议、音频、转写、翻译、纪要版本和相关文档。 |
| 说话人和热词 | 提供说话人注册、识别、上传片段校正与热词管理接口。 |
| 字幕 | Web 管理端可配置字幕；`VoiceRecognitionDisplay/` 和 `subtitle_display/` 提供 .NET 客户端工程。 |
| 本地服务集成 | 提供 LLM/纪要任务接口、健康检查、CORS、API Key、串口和 SSL 配置入口。 |

## 服务与默认端口

| 服务 | 默认地址 | 代码入口 |
| --- | --- | --- |
| WebSocket 转写 | `ws://127.0.0.1:10095/` | `main.py`、`src/modules/network/websocket_service.py` |
| REST API | `http://127.0.0.1:8080/api` | `src/modules/database/database_api.py` |
| 健康检查 | `http://127.0.0.1:8080/api/health` | `GET /api/health` |
| Web 管理端（开发模式） | `http://127.0.0.1:5173` | `ui/` |

前端的默认后端地址在 `ui/src/config/api.ts` 中定义。页面从远程主机访问时会使用浏览器当前主机名，并仍使用 `10095`、`8080` 两个端口。

## 系统要求

- Python 3.8 或更高版本（Docker 镜像使用 Python 3.11）。
- Node.js 与 npm，用于 Web 管理端；Docker 构建使用 Node.js 20。
- `ffmpeg`，用于上传媒体的转换和音频提取；项目中的 `tools/bin/ffmpeg` 存在时，`start.sh` 会优先使用它。
- 可选：.NET 8 SDK，用于构建字幕客户端。
- 本地 FunASR 模型。模型不会在服务启动时自动下载。

## 快速开始

以下步骤从项目根目录执行。

### 1. 创建 Python 环境并安装依赖

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. 安装 Web 管理端依赖

```bash
cd ui
npm ci
cd ..
```

### 3. 下载并整理基础模型

`organize_models.py` 会使用 ModelScope 下载基础模型，并将其整理到 `models/`。模型文件很大，不会被 Git 跟踪。

```bash
python organize_models.py
```

首次启动至少应确认 `models/SenseVoiceSmall` 可用。若上传识别启用了内置说话人分离，还需要其所配置的 VAD、CAM++ 和标点模型。

### 4. 启动

```bash
./start.sh start
```

默认会启动后端和 Vite 前端。脚本会检查 `curl`、`nc`、Python 和前端依赖，并把 PID 与日志写入 `.runtime/wyl-asr/`。

```bash
./start.sh status
./start.sh logs backend
./start.sh logs ui
./start.sh stop
```

验证 REST API：

```bash
curl http://127.0.0.1:8080/api/health
```

### 首次启动建议

`start.sh` 的 `WYL_ASR_ENABLE_2PASS` 默认为 `auto`：当指定的在线 Paraformer 本地目录不存在时，脚本会自动以 `--disable_2pass` 启动。若希望明确只启动离线/上传识别，可使用：

```bash
WYL_ASR_ENABLE_2PASS=0 ./start.sh start
```

启用 2pass 前，请将 `WYL_ASR_ONLINE_ASR_MODEL` 指向一个已准备好的本地兼容在线模型目录。

## 配置

`start.sh` 读取环境变量；也会自动加载项目根目录的 `.env.local`（该文件不应提交）。常用项如下：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WYL_ASR_HOST` | `0.0.0.0` | WebSocket 与 API 的监听地址。 |
| `WYL_ASR_WS_PORT` | `10095` | WebSocket 端口。 |
| `WYL_ASR_API_PORT` | `8080` | REST API 端口。 |
| `WYL_ASR_ENABLE_UI` | `1` | 设为 `0` 时不启动 Vite 前端。 |
| `WYL_ASR_UI_HOST` / `WYL_ASR_UI_PORT` | `127.0.0.1` / `5173` | Vite 开发服务地址。 |
| `WYL_ASR_MODEL_DEVICE` | `auto` | `auto`、`cpu`、`cuda` 或 `mps`；`auto` 优先 CUDA、其次 MPS。 |
| `WYL_ASR_NGPU` / `WYL_ASR_NCPU` | 自动 / `4` | 传给 FunASR 的 GPU 与 CPU 配置。 |
| `WYL_ASR_ASR_MODEL` | `models/SenseVoiceSmall` | 实时离线 ASR 本地模型目录。 |
| `WYL_ASR_UPLOAD_ASR_MODEL` | 与 ASR 模型相同 | 上传识别专用 ASR 模型目录。 |
| `WYL_ASR_ENABLE_2PASS` | `auto` | `auto`、`1` 或 `0`。 |
| `WYL_ASR_ONLINE_ASR_MODEL` | 脚本内 Paraformer 路径 | 2pass 在线模型的本地目录。 |
| `WYL_ASR_ENABLE_SERIAL` | `0` | 设为 `1` 启用串口接收。 |
| `WYL_ASR_SERIAL_PORT` / `WYL_ASR_SERIAL_BAUDRATE` | 空 / `9600` | 串口设备与波特率。 |
| `WYL_ASR_UPLOAD_ASR_LANGUAGE` | `zh` | 上传识别语言；支持 `auto`、`zh`、`en`、`yue`、`ja`、`ko`、`nospeech`。 |

示例：以 CPU、关闭 2pass 启动后端而不启动前端：

```bash
WYL_ASR_MODEL_DEVICE=cpu \
WYL_ASR_ENABLE_2PASS=0 \
WYL_ASR_ENABLE_UI=0 \
./start.sh start
```

## API 概览

所有业务接口位于 `/api` 下；详细请求体和响应结构以 `src/modules/database/database_api.py` 及前端调用为准。

| 分组 | 代表接口 | 用途 |
| --- | --- | --- |
| 健康检查 | `GET /api/health` | 检查数据库、分段服务和任务队列状态。 |
| 上传识别 | `POST /api/upload/audio/recognize`、`GET /api/upload/audio/tasks/<task_id>` | 创建并查询上传音视频识别任务。 |
| 上传校正 | `/api/upload/audio/tasks/<task_id>/corrections`、`/speakers/*` | 校正上传结果中的说话人和片段。 |
| 会议 | `/api/meetings`、`/api/meetings/<id>/speech-results` | 管理会议、录音与转写数据。 |
| 纪要与文档 | `/api/meetings/<id>/minutes`、`/api/summary/tasks` | 保存纪要、版本、文档和异步纪要任务。 |
| 说话人 | `/api/speakers/register`、`/api/speakers/list`、`/api/speakers/identify` | 注册、列出和识别说话人。 |
| 热词 | `/api/hotwords`、`/api/hotwords/import` | 管理热词及导入。 |
| LLM | `/api/llm/config`、`/api/llm/chat`、`/api/llm/tasks` | 管理本地 LLM 配置和任务。 |

上传接口接受的扩展名包括：`wav`、`mp3`、`flac`、`m4a`、`aac`、`ogg`、`webm`、`mp4`、`mov`、`mkv`、`avi`、`wmv`、`m4v`、`amr`、`opus` 和 `wma`。Flask 的请求大小上限为 2 GB。

### API 访问控制与跨域

- 设置 `WYL_ASR_API_KEY` 后，所有 `/api/*` 请求都必须携带 `X-API-Key`，或 `Authorization: Bearer <key>`。
- `WYL_ASR_CORS_ORIGINS` 用逗号分隔允许的来源；默认值为 `*`。生产环境应设置为明确的前端来源。
- HTTPS/WSS 可通过 `main.py` 的 `--certfile` 与 `--keyfile` 参数配置。

## Docker

Dockerfile 会构建 Vue 前端，并在最终 Python 镜像中通过 REST 应用提供静态资源。镜像默认关闭 2pass 和串口，并使用容器中的 `/app/models` 本地模型路径。

```bash
docker build -t magic-box-ai .

docker run --rm \
  -p 10095:10095 \
  -p 8080:8080 \
  -v "$PWD/models:/app/models:ro" \
  -v "$PWD/data:/app/data" \
  magic-box-ai
```

容器启动前，请确保挂载的 `models/` 中包含 Dockerfile 所引用的模型目录。

## 可选字幕客户端

- `VoiceRecognitionDisplay/VoiceRecognitionDisplay.sln`：跨平台字幕客户端解决方案，包含 Desktop、Android、iOS、macOS、Linux 和测试工程。
- `subtitle_display/`：轻量滚动字幕客户端。

两者都使用 .NET 8。以轻量客户端为例：

```bash
cd subtitle_display
dotnet restore
dotnet run
```

## 项目结构

```text
.
├── main.py                         # WebSocket 与 Flask API 的进程入口
├── start.sh                        # 本地启动、停止、日志与状态管理
├── organize_models.py              # ModelScope 模型下载与整理工具
├── requirements.txt                # Python 依赖
├── src/modules/
│   ├── audio/                      # 音频处理、媒体转换、VAD
│   ├── config/                     # 参数、日志与 SSL 配置
│   ├── core/                       # 服务状态与模型加载
│   ├── database/                   # Flask API、SQLite 数据与上传任务
│   ├── network/                    # WebSocket 和翻译服务
│   ├── serial/                     # 串口接收
│   └── speaker/                    # 说话人识别、标注与声纹
├── ui/                             # Vue 3 + Vite 管理端
├── VoiceRecognitionDisplay/        # .NET 跨平台字幕客户端
├── subtitle_display/               # .NET 轻量滚动字幕客户端
├── tests/                          # Python 测试
└── Dockerfile                      # 前后端多阶段容器构建
```

## 开发检查

```bash
# Python 测试（模型相关测试可能需要本地模型与音频设备）
pytest

# 前端类型检查与生产构建
cd ui
npm run build

# .NET 字幕客户端测试（可选）
dotnet test VoiceRecognitionDisplay/VoiceRecognitionDisplay.sln
```

## 许可证

本项目采用 [MIT License](LICENSE)。
