# 🚀 快速启动指南

## 系统架构

系统由三个服务组成：

1. **WebSocket 服务器**（端口 10095）- 负责语音识别
2. **HTTP API 服务器**（端口 8080）- 提供数据库和设备管理API
3. **前端界面**（端口 3000/5173）- 用户界面

## 启动步骤

### 1. 启动 WebSocket 服务器（语音识别）

```bash
# 进入项目目录
cd /Users/wyl/Documents/wyl/wyl_asr/wyl_asr

# 启动 WebSocket 服务器
python main.py --host 0.0.0.0 --port 10095
```

**日志输出：**
```
🚀 启动WebSocket服务器...
✅ WebSocket服务器启动成功: ws://0.0.0.0:10095
```

### 2. 启动 HTTP API 服务器（数据库API）

**新开一个终端窗口：**

```bash
# 进入项目目录
cd /Users/wyl/Documents/wyl/wyl_asr/wyl_asr

# 启动 API 服务器
python -m src.modules.network.start_api --host 0.0.0.0 --port 8080
```

**日志输出：**
```
╔══════════════════════════════════════════════════════════════╗
║                    WYL ASR 数据库API服务器                    ║
║                                                              ║
║  提供完整的RESTful API接口来操作数据库功能                     ║
╚══════════════════════════════════════════════════════════════╝
✅ Flask版本: x.x.x
✅ 数据库连接正常
 * Running on http://0.0.0.0:8080
```

### 3. 启动前端界面

**新开一个终端窗口：**

```bash
# 进入前端目录
cd /Users/wyl/Documents/wyl/wyl_asr/wyl_asr/ui

# 安装依赖（首次运行）
npm install

# 启动开发服务器
npm run dev
```

**访问地址：**
```
http://localhost:5173
```

## 验证服务

### 检查 WebSocket 服务器
```bash
curl -i http://127.0.0.1:10095
# 应该返回 426 Upgrade Required（这是正常的，因为这是WebSocket端口）
```

### 检查 API 服务器
```bash
# 获取音频设备列表
curl http://127.0.0.1:8080/api/audio-devices

# 应该返回类似：
# {
#   "code": 200,
#   "message": "获取音频设备列表成功",
#   "data": {
#     "devices": [...],
#     "default_device": "0"
#   }
# }
```

### 检查前端
打开浏览器访问：`http://localhost:5173`

## 使用音频采集功能

### 浏览器采集模式（默认）

1. 打开前端界面
2. 点击右下角⚙️设置按钮
3. 确认"音频采集"选择为"浏览器采集"
4. 在"音频设备"中选择麦克风
5. 点击录音按钮开始

### 服务器采集模式（需要PyAudio）

#### 安装 PyAudio

**Windows:**
```bash
pip install pyaudio
```

**Linux:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

**macOS:**
```bash
brew install portaudio
pip install pyaudio
```

#### 使用步骤

1. 确保API服务器已启动（端口8080）
2. 打开前端界面
3. 点击右下角⚙️设置按钮
4. 将"音频采集"切换为"服务器采集"
5. 系统会自动从服务器获取音频设备列表
6. 在"音频设备"中选择服务器端的音频设备
7. 点击录音按钮开始

## 常见问题

### ❌ 问题：访问 API 返回 426 Upgrade Required

**原因：** 访问了错误的端口（10095是WebSocket端口，不是API端口）

**解决：**
- 确保访问 `http://127.0.0.1:8080/api/audio-devices`（端口8080）
- 而不是 `http://127.0.0.1:10095/api/audio-devices`（端口10095）

### ❌ 问题：API 服务器无法连接

**检查：**
```bash
# 1. 确认API服务器是否运行
netstat -an | grep 8080

# 2. 查看进程
ps aux | grep start_api

# 3. 重启API服务器
python -m src.modules.network.start_api --host 0.0.0.0 --port 8080
```

### ❌ 问题：服务器采集模式不可用

**检查PyAudio：**
```bash
python -c "import pyaudio; print('PyAudio 已安装')"
```

如果报错，安装PyAudio：
```bash
pip install pyaudio
```

**检查音频设备：**
```bash
python -c "
import pyaudio
p = pyaudio.PyAudio()
print('可用的音频输入设备：')
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f'{i}: {info[\"name\"]}')
"
```

### ❌ 问题：前端无法连接到服务器

**检查配置：**
编辑 `ui/src/config/api.ts`：
```typescript
const SERVER_IP = '127.0.0.1'  // 确保IP地址正确
```

**检查CORS：**
确保API服务器已启用CORS（默认已启用）

## 端口说明

| 服务 | 端口 | 协议 | 用途 |
|------|------|------|------|
| WebSocket | 10095 | ws:// | 语音识别服务 |
| HTTP API | 8080 | http:// | 数据库和设备管理 |
| 前端 | 5173 | http:// | 用户界面（开发模式） |
| 前端 | 3000 | http:// | 用户界面（生产模式） |

## 一键启动脚本

### Linux/macOS

创建 `start_all.sh`：
```bash
#!/bin/bash

# 启动 WebSocket 服务器
python main.py --host 0.0.0.0 --port 10095 &
WS_PID=$!
echo "WebSocket 服务器启动: PID=$WS_PID"

# 等待1秒
sleep 1

# 启动 API 服务器
python -m src.modules.network.start_api --host 0.0.0.0 --port 8080 &
API_PID=$!
echo "API 服务器启动: PID=$API_PID"

# 等待1秒
sleep 1

# 启动前端（可选）
cd ui && npm run dev &
UI_PID=$!
echo "前端服务启动: PID=$UI_PID"

echo ""
echo "所有服务已启动！"
echo "WebSocket: ws://127.0.0.1:10095"
echo "API: http://127.0.0.1:8080"
echo "前端: http://127.0.0.1:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待
wait
```

运行：
```bash
chmod +x start_all.sh
./start_all.sh
```

### Windows

创建 `start_all.bat`：
```batch
@echo off
echo 启动所有服务...

start "WebSocket Server" python main.py --host 0.0.0.0 --port 10095
timeout /t 2

start "API Server" python -m src.modules.network.start_api --host 0.0.0.0 --port 8080
timeout /t 2

cd ui
start "Frontend" npm run dev

echo.
echo 所有服务已启动！
echo WebSocket: ws://127.0.0.1:10095
echo API: http://127.0.0.1:8080
echo 前端: http://127.0.0.1:5173
echo.
pause
```

运行：
```batch
start_all.bat
```

## 日志位置

- WebSocket服务器日志：控制台输出
- API服务器日志：`api_server.log`
- 前端日志：浏览器开发者工具控制台

## 需要帮助？

查看详细文档：`docs/audio_capture_modes.md`

