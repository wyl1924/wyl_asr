#!/bin/bash
# 简化版2pass模式启动脚本
# 使用默认配置，最少参数启动

echo "🚀 启动FunASR 2pass模式WebSocket服务器 (简化版)..."
echo "📋 使用默认配置:"
echo "   • 模式: 2pass (在线+离线双通道)"
echo "   • 离线模型: damo/SenseVoiceSmall-onnx (默认)"
echo "   • 在线模型: damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online-onnx (默认)"
echo "   • VAD模型: damo/speech_fsmn_vad_zh-cn-16k-common-onnx (默认)"
echo "   • 标点模型: damo/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727 (默认)"
echo "   • 语言模型: damo/speech_ngram_lm_zh-cn-ai-wesp-fst (默认)"
echo "   • ITN模型: thuduj12/fst_itn_zh (默认)"
echo "   • 热词文件: ./models/hotwords.txt (默认)"
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
# 创建models目录（如果不存在）
if [ ! -d "./data" ]; then
    echo "📁 创建models目录..."
    mkdir -p ./data
fi
# 检查热词文件，如果不存在则创建默认的
if [ ! -f "./data/hotwords.txt" ]; then
    echo "📝 创建默认热词文件..."
    cat > ./data/hotwords.txt << 'EOF'
# 默认热词文件
# 格式: 热词 权重

# 常用技术词汇
人工智能 25
语音识别 30
机器学习 25
深度学习 25
自然语言处理 25

# 常用词汇
会议 20
项目 20
报告 20
文档 20
系统 20
EOF
fi

echo "🔄 正在启动服务器..."
echo "💡 提示: 所有配置都使用默认值，如需自定义请使用 run_2pass_server.sh"
echo ""

# 使用最简配置启动 (2pass模式现在默认启用)
python main.py \
    --host 0.0.0.0 \
    --port 10095 \
    --api-port 8080 \
    --model_type sensevoice \
    --device cpu \
    --ngpu 0 \
    --ncpu 4

echo "👋 服务器已停止"