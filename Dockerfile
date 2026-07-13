# WYL ASR Docker Image
# 构建前端静态资源
FROM node:20-bookworm-slim AS ui-builder

WORKDIR /ui

COPY ui/package*.json ./
RUN npm ci

COPY ui/ ./
RUN npm run build

# 基于 Python 3.11 的官方镜像
FROM python:3.11-slim

# 设置维护者信息
LABEL maintainer="AIM ZST Team <team@wyl-asr.com>"
LABEL description="FunASR-based WebSocket Real-time Speech Recognition Server"
LABEL version="1.0.0"

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    sox \
    libsox-fmt-all \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip
RUN pip install --upgrade pip setuptools wheel

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 复制前端构建产物，最终镜像不需要 Node/Vite 运行时
COPY --from=ui-builder /ui/dist /app/ui/dist

# 创建必要的目录
RUN mkdir -p logs data output cache models

# 设置文件权限
RUN chmod +x main.py

# 创建非 root 用户
RUN groupadd -r wylasr && useradd -r -g wylasr wylasr

# 更改文件所有者
RUN chown -R wylasr:wylasr /app

# 切换到非 root 用户
USER wylasr

# 暴露端口
EXPOSE 10095 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 启动命令
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "10095", "--api-port", "8080", "--asr_model", "/app/models/SenseVoiceSmall", "--upload_asr_model", "/app/models/SenseVoiceSmall", "--upload_asr_vad_model", "/app/models/speech_fsmn_vad_zh-cn-16k-common-pytorch", "--upload_asr_spk_model", "/app/models/speech_campplus_sv_zh-cn_16k-common", "--upload_asr_punc_model", "/app/models/punc_ct-transformer_zh-cn-common-vocab272727-pytorch", "--disable_2pass", "--disable_serial"]
