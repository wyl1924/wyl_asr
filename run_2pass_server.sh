#!/bin/bash
# 启动2pass模式的FunASR WebSocket服务器
# 类似于FunASR C++服务器的run_server_2pass.sh

echo "🚀 启动FunASR 2pass模式WebSocket服务器..."
echo "📋 配置信息:"
echo "   • 模式: 2pass (在线+离线双通道)"
echo "   • 离线模型: ./models/SenseVoiceSmall"
echo "   • 在线模型: ./models/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
echo "   • VAD模型: ./models/speech_fsmn_vad_zh-cn-16k-common-pytorch"
echo "   • 标点模型: ./models/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727"
echo "   • 语言模型: ./models/speech_ngram_lm_zh-cn-ai-wesp-fst"
echo "   • ITN模型: ./models/fst_itn_zh"
echo "   • 热词文件: ./data/hotwords.txt"
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

# 检查热词文件
if [ ! -f "./data/hotwords.txt" ]; then
    echo "⚠️ 警告: 热词文件不存在，将跳过热词功能"
    HOTWORD_ARG=""
else
    HOTWORD_ARG="--hotword ./data/hotwords.txt"
fi

# 启动服务器
echo "🔄 正在启动服务器..."
python main.py \
    --enable_2pass \
    --host 0.0.0.0 \
    --port 10095 \
    --api-port 8080 \
    --model_type sensevoice \
    --asr_model ./models/SenseVoiceSmall \
    --online_model_dir ./models/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch \
    --asr_model_online ./models/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch \
    --vad_dir ./models/speech_fsmn_vad_zh-cn-16k-common-pytorch \
    --vad_model ./models/speech_fsmn_vad_zh-cn-16k-common-pytorch \
    --vad_max_single_segment_time 60000 \
    --vad_speech_noise_thres 0.6 \
    --punc_dir ./models/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727 \
    --punc_model ./models/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727 \
    --lm_dir ./models/speech_ngram_lm_zh-cn-ai-wesp-fst \
    --lm_model ./models/speech_ngram_lm_zh-cn-ai-wesp-fst \
    --itn_dir ./models/fst_itn_zh \
    --itn_model ./models/fst_itn_zh \
    $HOTWORD_ARG \
    --fst_inc_wts 20 \
    --quantize false \
    --global_beam 3.0 \
    --lattice_beam 3.0 \
    --am_scale 10.0 \
    --batch_size 4 \
    --io_thread_num 2 \
    --decoder_thread_num 8 \
    --model_thread_num 1 \
    --device cpu \
    --ngpu 0 \
    --ncpu 4

echo "👋 服务器已停止"