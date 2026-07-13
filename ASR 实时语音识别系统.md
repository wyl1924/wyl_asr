# WYL ASR 实时语音识别系统 — 功能文档

---

## 一、系统概述

WYL ASR 是一套基于 **WebSocket** 的实时语音识别服务，面向会议场景设计，提供从音频采集、语音识别、说话人识别到翻译、会议记录存储的完整处理链路。

### 1.1 整体架构

```
客户端（浏览器 / 会议设备）
        │  WebSocket (ws/wss :10095)
        ▼
┌─────────────────────────────────────────────┐
│             WebSocket 服务层                 │
│  接收音频流 → 缓冲 → 在线识别(600ms) → 离线识别(4.5~7s) │
└────────────┬────────────────────────────────┘
             │
    ┌────────┼────────────┐
    ▼        ▼            ▼
  ASR      说话人        翻译
SenseVoice  串口/声纹    opus-mt
             │
    ┌────────┼────────────┐
    ▼                     ▼
 串口会议系统           REST API 服务 (:8080)
 (麦克风开关信号)        数据库 / 会议管理
```

### 1.2 技术栈

| 组件 | 技术 |
|---|---|
| 语音识别 | FunASR + SenseVoiceSmall |
| WebSocket 服务 | Python asyncio + websockets |
| REST API | Flask + SQLite |
| 翻译 | opus-mt-zh-en（本地优先）/ opus-mt-zh-en-ct2（量化备用） |
| 串口通信 | pyserial |
| 音频采集 | 浏览器 MediaRecorder / PyAudio（服务端采集） |

---

## 二、核心功能模块

### 2.1 语音识别（ASR）

#### 识别模式

系统支持以下三种识别模式，通过 WebSocket 消息的 `mode` 字段指定：

| 模式 | 说明 | 延迟 |
|---|---|---|
| `2pass`（默认） | 双通道：先实时返回在线结果，再返回精确的离线结果 | 在线 <600ms，离线 4.5~7s |
| `online` | 仅在线流式识别，低延迟 | <600ms |
| `offline` | 仅离线识别，精确度更高 | 4.5~7s |

#### 双通道（2pass）工作机制

```
音频流到达
   │
   ├─ 每 600ms → 在线识别 → 发送 mode=2pass-online（实时字幕，可能有误）
   │
   └─ 每 4.5~7s（智能静音切分）→ 离线识别 → 发送 mode=2pass-offline（最终结果）
                ↑
        静音点检测（RMS < 300）触发提前切分，避免断词
        无静音则 7s 强制切分
```

#### 支持的音频格式

- **采样率**：16000 Hz
- **位深**：16 bit
- **声道数**：单声道（Mono）
- **编码**：PCM（原始二进制数据流）

#### 识别能力（SenseVoiceSmall）

- 多语言识别：中文（默认）、英文、日文、韩文、粤语、自动检测
- 自带标点符号输出
- 逆文本标准化（ITN）：数字、时间、单位自动格式化
- 情感识别（可选）
- 音频事件检测（可选，如掌声、音乐）
- 热词增强：支持配置热词列表提升特定词汇识别率

---

### 2.2 说话人识别

系统支持两种说话人来源，优先级从高到低：

#### 优先级 1：串口会议系统（硬件信号）

通过串口接收会议话筒的开关信号，直接知道是谁在讲话，**无需声纹计算**，准确率 100%。

```
麦克风开启信号 → 串口 → 解析出座位号 → 查绑定表 → 得到参会人姓名
```

支持的串口协议：

**协议 A**（格式：`FE F7 [开关] [单元号] [设备类型] EF`）

```
FE F7 01 01 00 EF  →  1号代表 打开（开始讲话）
FE F7 00 01 01 EF  →  1号主席 关闭（停止讲话）
```

**协议 B**（格式：`01 03 [开关] [设备类型] [ID号] 02`）

```
01 03 20 20 21 02  →  33号代表 打开
01 03 21 21 21 02  →  33号主席 关闭
```

#### 优先级 2：手动指定（WebSocket 消息）

客户端可发送 `manual_speaker_name` 指定当前会话的讲话人，覆盖串口自动判断：

```json
{"manual_speaker_name": "张三"}
// 恢复自动判断：
{"clear_manual_speaker": true}
```

#### 优先级 3：声纹识别（延迟加载）

注册过声纹的说话人，通过 CAM++ 模型提取声纹特征进行余弦相似度匹配。仅在串口未配置时生效，首次调用时按需加载模型。

- 支持声纹注册、识别、验证、删除
- 相似度阈值默认 0.4，可配置
- 通过 WebSocket `speaker_*` 动作或 REST API `/api/speakers/*` 操作

---

### 2.3 翻译功能

#### 工作逻辑

系统启动时**自动检测**可用后端，优先顺序：

```
1. models/opus-mt-zh-en  存在 → 本地 HuggingFace 模型（质量最好）
2. models/opus-mt-zh-en-ct2 存在 → 本地 ctranslate2 量化版（速度更快）
```

#### 触发条件

- WebSocket 消息中 `enable_translation: true`
- 或客户端在识别结果返回后单独请求翻译

#### 翻译语言

- 源语言：中文（zh）
- 目标语言：英文（en）

---

### 2.4 热词管理

#### 静态热词（文件配置）

在 `data/hotwords.txt` 中配置，格式：

```
真视通 20
紫荆视通 30
博数智源 25
无纸化
```

服务启动时加载，自动注入 SenseVoice 推理，权重默认 1.5。

#### 动态热词（API 管理）

通过 REST API 实时增删热词，无需重启服务：

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/hotwords` | GET | 获取热词列表 |
| `/api/hotwords` | POST | 添加热词 |
| `/api/hotwords/{id}` | DELETE | 删除热词 |

#### WebSocket 实时更新

```json
{"hotwords": "真视通,紫荆,博数"}
{"type": "update_config", "fst_inc_wts": 25}
```

---

### 2.5 会议管理与数据存储

SQLite 数据库存储所有会议数据，包含以下实体：

| 数据表 | 内容 |
|---|---|
| 会议（meetings） | 标题、开始/结束时间、文件名 |
| 音频文件（audio_files） | 文件名、路径、大小、时长、格式 |
| 识别结果（speech_results） | 说话人、文本、置信度、时间戳、语言 |
| 翻译内容（meeting_translations） | 原文、译文、源/目标语言 |
| 说话人（speakers） | 姓名、邮箱、声纹特征 |
| 会议纪要（meeting_minutes） | LLM 生成的会议纪要 |

---

### 2.6 AI 会议纪要（LLM）

支持调用外部 LLM 服务自动生成会议纪要，支持多种推理后端：

| 后端 | 默认端点 | 默认模型 |
|---|---|---|
| Ollama | `https://10.1.0.27/ollama/api/chat` | `qwen3:30b-a3b-q4_K_M` |
| Xinference | `http://localhost:9997/v1` | `qwen-chat` |
| vLLM | `http://localhost:8000/v1` | 可配置 |
| SGLang | `http://localhost:30000/v1` | 可配置 |

- 最大上下文：32768 tokens
- 最大输出：8192 tokens
- LLM 任务串行执行（防止资源争抢）
- 支持异步任务，可通过 task_id 查询进度

---

## 三、WebSocket 通信协议

### 3.1 连接信息

```
地址：ws://host:10095
子协议：binary
```

### 3.2 客户端 → 服务端消息

#### 初始化配置（JSON 文本帧）

```json
{
  "mode": "2pass",              // 识别模式: 2pass | online | offline
  "wav_name": "microphone",     // 音频源名称（用于日志）
  "chunk_size": [5, 10, 5],     // 在线模型分块大小
  "chunk_interval": 10,         // 处理间隔
  "hotwords": "真视通,紫荆",    // 实时热词
  "language": "zh",             // 识别语言: zh|en|yue|ja|ko|auto
  "is_speaking": true,          // 开始/停止说话
  "enable_speaker_diarization": true,   // 启用说话人识别
  "manual_speaker_name": "张三",        // 手动指定讲话人
  "clear_manual_speaker": false,        // 恢复自动判断
  "enable_translation": true,           // 启用翻译
  "audio_capture_mode": "browser"       // 音频采集: browser | server
}
```

#### 实时配置更新（可在录音中途发送）

```json
{
  "type": "update_config",
  "enable_speaker_diarization": true,
  "fst_inc_wts": 25
}
```

#### 音频数据（二进制帧）

直接发送 PCM 16bit 16kHz 单声道原始字节流，无需封装。

#### 说话人操作消息

```json
// 注册声纹
{"action": "speaker_register", "speaker_name": "张三", "audio_data": "<base64>", "description": "研发部"}

// 识别说话人
{"action": "speaker_identify", "audio_data": "<base64>", "top_k": 3}

// 验证说话人
{"action": "speaker_verify", "speaker_name": "张三", "audio_data": "<base64>"}

// 获取列表
{"action": "speaker_list"}

// 删除说话人
{"action": "speaker_delete", "speaker_name": "张三"}
```

---

### 3.3 服务端 → 客户端消息

#### 识别结果

```json
{
  "mode": "2pass-online",       // 2pass-online=实时结果 | 2pass-offline=最终结果
  "text": "今天的会议开始，",
  "wav_name": "microphone",
  "is_final": false,
  "timestamp": [[0, 500], [500, 1000]],   // 词级时间戳（毫秒）
  "speaker": "张三",             // 说话人姓名（如已识别）
  "emotion": "neutral",          // 情感（如启用）
  "translation": "The meeting begins today,"  // 翻译（如启用）
}
```

#### 连接时推送字幕设置

```json
{
  "type": "settings_update",
  "data": { /* 字幕显示设置 */ }
}
```

#### 说话人操作响应

```json
{
  "action": "speaker_register",
  "success": true,
  "message": "说话人注册成功",
  "speaker_name": "张三",
  "speaker_info": { /* 注册信息 */ }
}
```

---

## 四、REST API 接口

服务地址：`http://host:8080`

### 4.1 系统

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/health` | GET | 健康检查 |
| `/api/audio-devices` | GET | 获取服务器音频设备列表 |

### 4.2 会议管理

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/meetings` | POST | 创建会议 |
| `/api/meetings` | GET | 获取会议列表 |
| `/api/meetings/{id}` | GET | 获取会议详情 |
| `/api/meetings/{id}` | DELETE | 删除会议（级联删除） |
| `/api/meetings/{id}/end` | PUT | 结束会议（记录结束时间） |

### 4.3 音频文件

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/meetings/{id}/audio-files` | POST | 登记音频文件元数据 |
| `/api/meetings/{id}/audio-files` | GET | 获取会议音频文件列表 |
| `/api/audio-files/{id}` | GET | 获取音频文件信息 |
| `/api/audio-files/{id}` | DELETE | 删除音频文件记录 |

### 4.4 语音识别结果

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/meetings/{id}/speech-results` | POST | 保存识别结果 |
| `/api/meetings/{id}/speech-results` | GET | 获取会议识别结果列表 |
| `/api/meetings/{id}/recognition-modes` | POST | 保存识别模式结果 |
| `/api/meetings/{id}/recognition-modes` | GET | 获取识别模式结果 |

### 4.5 翻译

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/meetings/{id}/translations` | POST | 保存翻译内容 |
| `/api/meetings/{id}/translations` | GET | 获取会议翻译列表 |
| `/api/translations/by-source` | GET | 按源记录查询翻译 |
| `/api/speech-results/{id}/translations` | POST | 保存识别结果的翻译 |

### 4.6 说话人管理

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/speakers` | POST | 保存说话人基础信息 |
| `/api/speakers/{id}` | GET | 获取说话人信息 |
| `/api/speakers/register` | POST | 注册声纹（上传音频） |
| `/api/speakers/list` | GET | 获取已注册说话人列表 |
| `/api/speakers/identify` | POST | 通过音频识别说话人 |
| `/api/speakers/delete` | POST | 删除说话人及声纹 |

### 4.7 会议纪要（LLM）

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/meetings/{id}/minutes` | POST | 触发 LLM 生成会议纪要 |
| `/api/meetings/{id}/minutes` | GET | 获取会议纪要 |
| `/api/llm/tasks/{task_id}` | GET | 查询 LLM 任务进度 |
| `/api/llm/config` | GET/POST | 获取/更新 LLM 配置 |

### 4.8 热词管理

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/hotwords` | GET | 获取热词列表 |
| `/api/hotwords` | POST | 添加热词 |
| `/api/hotwords/{id}` | DELETE | 删除热词 |

### 4.9 字幕显示设置

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/subtitle-settings` | GET | 获取字幕显示配置 |
| `/api/subtitle-settings` | POST | 更新字幕显示配置（广播给所有客户端） |

### 4.10 串口单元号管理

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/serial/units` | GET | 获取所有座位号 → 姓名映射 |
| `/api/serial/units/{unit}` | PUT | 更新单元号绑定的说话人姓名 |
| `/api/serial/units/{unit}` | DELETE | 删除某个单元号绑定 |
| `/api/serial/units/batch` | POST | 批量更新座位绑定 |

### 4.11 文档管理

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/meetings/save-complete` | POST | 完整保存会议（音频+转录+纪要一次性） |
| `/api/meetings/save-documents` | POST | 保存关联文档 |
| `/api/meetings/documents/list` | GET | 文档列表 |
| `/api/meetings/documents/download` | GET | 下载文档 |
| `/api/meetings/documents/{id}` | DELETE | 删除文档 |

### 4.12 文档分段

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/segment/text` | POST | 对单段文本语义分段（需 `--enable_segmentation`） |
| `/api/segment/batch` | POST | 批量分段 |
| `/api/segment/status` | GET | 获取分段服务状态 |

### 4.13 系统与数据库

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/database/info` | GET | 数据库文件信息 |
| `/api/database/vacuum` | POST | 数据库碎片整理压缩 |
| `/api/config` | POST | 保存配置项 |
| `/api/config/{key}` | GET | 获取指定配置值 |

---

## 五、关键阈值与默认值

| 参数 | 默认值 | 说明 |
|---|---|---|
| 在线识别间隔 | 600 ms | 每 600ms 触发一次在线 ASR |
| 离线智能切分区间 | 4500 ~ 7000 ms | 在此区间内找静音点提前切分 |
| 强制切分上限 | 7000 ms | 7s 无静音则强制切分 |
| 静音 RMS 阈值 | 300 | 低于此值判断为静音 |
| 说话人匹配阈值 | 0.4 | 余弦相似度低于此值视为陌生人 |
| 串口超时（hybrid 模式） | 30 s | 串口无信号 30s 后切回声纹识别 |
| 热词权重范围 | 1.0 ~ 10.0 | 默认 4.0，文件配置默认 20（FST 单位） |
| ASR 热词注入权重 | 1.5 | 注入 SenseVoice 的 hotword_weight |
| LLM 最大上下文 | 32768 tokens | 生成会议纪要时的上下文限制 |
| LLM 最大输出 | 8192 tokens | 生成内容最大长度 |
| API 最大请求体 | 1 GB | 支持超大音频文件上传 |

---

## 六、模型说明

| 模型 | 大小 | 作用 | 加载时机 |
|---|---|---|---|
| `SenseVoiceSmall` | 897M | 主 ASR（离线+在线，自带标点） | 启动时 |
| `fst_itn_zh` | 892K | 逆文本标准化（数字/时间格式化） | 启动时 |
| `opus-mt-zh-en` | 299M | 中英翻译（HuggingFace 格式） | 首次翻译请求时 |
| `opus-mt-zh-en-ct2` | 78M | 中英翻译备用（量化版） | opus-mt-zh-en 不存在时 |
| `speech_campplus_sv_zh-cn_16k-common` | 28M | 说话人声纹特征提取 | 首次声纹操作时（延迟加载） |
| `speech_fsmn_vad_zh-cn-16k-common-pytorch` | 6M | VAD 语音活动检测（备用，当前不启用） | 未加载 |
| `nlp_bert_document-segmentation_chinese-base` | 389M | 长文档分段（需 `--enable_segmentation`） | 按需 |

---

## 七、启动配置

### 6.1 主要启动参数

```bash
python main.py \
  --model_type sensevoice \          # ASR模型类型
  --asr_model ./models/SenseVoiceSmall \   # 离线ASR模型路径
  --asr_model_online ./models/SenseVoiceSmall \ # 在线ASR模型路径
  --host 0.0.0.0 \                   # 监听地址
  --port 10095 \                     # WebSocket端口
  --api-port 8080 \                  # REST API端口
  --device cpu \                     # 计算设备: cpu | cuda | mps
  --ncpu 4 \                         # CPU线程数
  --enable_2pass \                   # 启用双通道识别（默认）
  --hotword ./data/hotwords.txt \    # 热词文件
  --serial_port /dev/cu.usbserial-XXX  # 串口设备（会议系统）
```

### 6.2 使用本地配置文件启动

```bash
python main.py $(cat local_models.conf | grep -v '^#' | tr '\n' ' ')
```

### 6.3 可选功能参数

```bash
# 翻译（本地模型自动检测，无需额外参数）
--enable_translation

# 文档分段功能
--enable_segmentation

# 禁用串口
--disable_serial

# SSL 加密
--certfile ./ssl_key/cert.pem --keyfile ./ssl_key/key.pem

# 识别语言
--sv_language zh          # zh|en|yue|ja|ko|auto
```

---

## 八、音频采集模式

### 7.1 浏览器采集（默认）

客户端使用 MediaRecorder API 采集麦克风音频，以二进制帧发送到 WebSocket。

### 7.2 服务器端采集

服务器直接通过 PyAudio 采集本地音频设备，适用于服务器直接连接音频硬件的场景：

```json
{
  "audio_capture_mode": "server",
  "server_audio_device": 0,    // 设备索引（通过 /api/audio-devices 获取）
  "is_speaking": true
}
```

---

## 九、串口会议系统集成

### 8.1 配置文件

`config/serial_config.yaml` 中配置串口参数和座位号-姓名绑定关系：

```yaml
serial:
  enabled: true
  port: /dev/cu.usbserial-A400CKPT
  baudrate: 9600
  protocol: auto   # auto | A | B

# 座位号到参会人的映射
bindings:
  1: 张三
  2: 李四
  3: 主席
```

### 8.2 工作流程

```
串口收到数据 → 多协议自动识别(A/B) → 解析座位号+开关状态
                                              │
        ┌─────────────────────────────────────┘
        │  开关=打开：从绑定表查找姓名 → 广播给所有 WebSocket 客户端
        │  开关=关闭：标记该座位已停止讲话
```

---
