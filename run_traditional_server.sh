#!/bin/bash
# 启动传统模式的FunASR WebSocket服务器
# 禁用2pass模式，使用单通道识别

echo "🚀 启动FunASR 传统模式WebSocket服务器..."
echo "📋 配置信息:"
echo "   • 模式: 传统模式 (单通道识别)"
echo "   • 支持模式: online, offline (客户端指定)"
echo "   • 离线模型: iic/SenseVoiceSmall-onnx"
echo "   • 在线模型: damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online-onnx"
echo "   • VAD模型: damo/speech_fsmn_vad_zh-cn-16k-common-onnx"
echo "   • 标点模型: damo/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727"
echo "   • 服务器地址: 0.0.0.0:10095"
echo "   • API地址: 0.0.0.0:8080"
echo ""

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "❌ 错误: 未找到Python解释器"
    exit 1
fi

# 检查是否在正确的目录
if [ ! -f "main.py" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 创建models目录（如果不存在）
if [ ! -d "./models" ]; then
    echo "📁 创建models目录..."
    mkdir -p ./models
fi

echo "🔄 正在启动传统模式服务器..."
echo "💡 提示: 使用--disable_2pass禁用2pass模式"
echo ""

# 启动传统模式服务器
python main.py \
    --disable_2pass \
    --host 0.0.0.0 \
    --port 10095 \
    --api-port 8080 \
    --model_type sensevoice \
    --device cpu \
    --ngpu 0 \
    --ncpu 4

echo "👋 服务器已停止"