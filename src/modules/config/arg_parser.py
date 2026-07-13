#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命令行参数解析模块。

提供完整的命令行参数解析功能，包括网络配置、模型配置和硬件配置。
"""

# 标准库导入
import argparse
from typing import List, Optional


# ============================================================================
# 异常定义
# ============================================================================

class ArgumentError(Exception):
    """参数解析相关异常。"""
    pass


# ============================================================================
# 主要功能函数
# ============================================================================

def build_vad_config(args: argparse.Namespace) -> dict:
    """从命令行参数构建VAD配置字典。
    
    Args:
        args: 解析后的命令行参数
        
    Returns:
        dict: VAD配置参数字典
    """
    return {
        "cache": {},
        "is_final": False,
        "max_end_silence_time": args.vad_max_end_silence_time,
        "max_start_silence_time": args.vad_max_start_silence_time,
        "min_speech_duration_time": args.vad_min_speech_duration_time,
        "speech_noise_thres": args.vad_speech_noise_thres,
        "do_start_point_detection": args.vad_do_start_point_detection,
        "do_end_point_detection": args.vad_do_end_point_detection,
        "window_size_ms": args.vad_window_size_ms,
        "sil_to_speech_time_thres": args.vad_sil_to_speech_time_thres,
        "speech_to_sil_time_thres": args.vad_speech_to_sil_time_thres,
        "max_single_segment_time": args.vad_max_single_segment_time
    }


def reset_vad_config(args: argparse.Namespace) -> dict:
    """从命令行参数构建VAD重置配置字典。
    
    Args:
        args: 解析后的命令行参数
        
    Returns:
        dict: VAD重置配置参数字典
    """
    config = build_vad_config(args)
    config["cache"] = {}
    config["is_final"] = True
    return config

def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """解析命令行参数。

    配置所有可用的命令行选项，包括：
    - 服务器网络配置 (host, port, SSL证书)
    - 模型配置 (ASR, VAD, 标点恢复模型)
    - 硬件配置 (GPU/CPU, 设备选择)

    Args:
        args: 可选的参数列表，用于测试。如果为None，则从sys.argv解析

    Returns:
        argparse.Namespace: 解析后的命令行参数

    Raises:
        ArgumentError: 当参数解析失败时抛出

    Examples:
        >>> args = parse_arguments()
        >>> print(args.host, args.port)
        >>> test_args = parse_arguments(['--host', '127.0.0.1', '--port', '8080'])
    """
    parser = argparse.ArgumentParser(
        description='FunASR WebSocket实时语音识别服务器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py --host 0.0.0.0 --port 10095
  python main.py --model_type sensevoice --device cpu
  python main.py --model_type paraformer --ngpu 1 --device cuda
  python main.py --certfile ssl_key/server.crt --keyfile ssl_key/server.key
        """
    )
    
    # 网络配置
    network_group = parser.add_argument_group('网络配置')
    network_group.add_argument(
        "--host", 
        type=str, 
        default="0.0.0.0", 
        help="服务器监听IP地址 (默认: 0.0.0.0, 监听所有接口)"
    )
    network_group.add_argument(
        "--port", 
        type=int, 
        default=10095, 
        help="WebSocket服务器监听端口号 (默认: 10095)"
    )
    network_group.add_argument(
        "--api-port", 
        type=int, 
        default=8080, 
        help="API服务器监听端口号 (默认: 8080)"
    )
    network_group.add_argument(
        "--certfile",
        type=str,
        default="ssl_key/server.crt",
        required=False,
        help="SSL证书文件路径 (用于HTTPS连接)"
    )
    network_group.add_argument(
        "--keyfile",
        type=str,
        default="ssl_key/server.key",
        required=False,
        help="SSL私钥文件路径 (用于HTTPS连接)"
    )
    
    # 模型配置
    model_group = parser.add_argument_group('模型配置')
    model_group.add_argument(
        "--model_type",
        type=str,
        default="sensevoice",
        choices=["sensevoice", "paraformer"],
        help="ASR模型类型 (sensevoice: SenseVoiceSmall多模态模型, paraformer: 传统Paraformer模型)"
    )
    model_group.add_argument(
        "--asr_model",
        type=str,
        default="iic/SenseVoiceSmall",
        help="离线ASR模型名称 (高精度模型)"
    )
    model_group.add_argument(
        "--asr_model_revision",
        type=str,
        default="master",
        help="离线ASR模型版本号"
    )
    model_group.add_argument(
        "--online_model_dir",
        type=str,
        default="./models/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        help="在线流式ASR模型路径 (低延迟模型)"
    )
    model_group.add_argument(
        "--asr_model_online",
        type=str,
        default="./models/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        help="在线流式ASR模型名称 (低延迟模型)"
    )
    model_group.add_argument(
        "--asr_model_online_revision",
        type=str,
        default="v2.0.4",
        help="在线流式ASR模型版本号"
    )
    model_group.add_argument(
        "--upload_asr_model",
        type=str,
        default="iic/SenseVoiceSmall",
        help="上传音频文件识别专用ASR模型，默认继续使用原有SenseVoiceSmall"
    )
    model_group.add_argument(
        "--upload_asr_model_revision",
        type=str,
        default="master",
        help="上传文件识别专用ASR模型版本号"
    )
    model_group.add_argument(
        "--vad_dir",
        type=str,
        default="",
        help="VAD模型本地路径 (如果指定则优先使用本地模型)"
    )
    model_group.add_argument(
        "--vad_model",
        type=str,
        default="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        help="语音活动检测(VAD)模型名称"
    )
    model_group.add_argument(
        "--vad_quant",
        type=str,
        default="false",
        choices=["true", "false"],
        help="是否使用量化VAD模型 (true: model_quant.onnx, false: model.onnx)"
    )
    model_group.add_argument(
        "--vad_max_single_segment_time",
        type=int,
        default=30000,
        help="VAD单段最大时长(毫秒)"
    )
    model_group.add_argument(
        "--vad_speech_noise_thres",
        type=float,
        default=0.7,
        help="VAD语音/噪声阈值"
    )
    model_group.add_argument(
        "--vad_max_end_silence_time",
        type=int,
        default=800,
        help="VAD尾部静音检测时长(毫秒)"
    )
    model_group.add_argument(
        "--vad_max_start_silence_time",
        type=int,
        default=2000,
        help="VAD开始静音检测时长(毫秒)"
    )
    model_group.add_argument(
        "--vad_min_speech_duration_time",
        type=int,
        default=200,
        help="VAD最小语音持续时长(毫秒)"
    )
    model_group.add_argument(
        "--vad_window_size_ms",
        type=int,
        default=200,
        help="VAD窗口大小(毫秒)"
    )
    model_group.add_argument(
        "--vad_sil_to_speech_time_thres",
        type=int,
        default=150,
        help="VAD静音到语音阈值(毫秒)"
    )
    model_group.add_argument(
        "--vad_speech_to_sil_time_thres",
        type=int,
        default=150,
        help="VAD语音到静音阈值(毫秒)"
    )
    model_group.add_argument(
        "--vad_do_start_point_detection",
        action="store_true",
        default=True,
        help="启用VAD开始点检测"
    )
    model_group.add_argument(
        "--vad_do_end_point_detection",
        action="store_true",
        default=True,
        help="启用VAD结束点检测"
    )
    model_group.add_argument(
        "--vad_model_revision", 
        type=str, 
        default="v2.0.4", 
        help="VAD模型版本号"
    )
    model_group.add_argument(
        "--disable_vad",
        action="store_true",
        default=False,
        help="禁用VAD，直接基于时长进行音频分割 - 适用于已知音频全为语音的场景"
    )
    model_group.add_argument(
        "--segment_duration_ms",
        type=int,
        default=3000,
        help="禁用VAD时的音频分割时长(毫秒) - 仅在disable_vad为True时生效"
    )
    model_group.add_argument(
        "--punc_model",
        type=str,
        default="iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727",
        help="标点符号恢复模型名称 (留空则禁用标点恢复)"
    )
    model_group.add_argument(
        "--punc_model_revision", 
        type=str, 
        default="v2.0.4", 
        help="标点恢复模型版本号"
    )
    model_group.add_argument(
        "--punc_dir",
        type=str,
        default="",
        help="标点恢复模型本地路径 (如果指定则优先使用本地模型)"
    )
    model_group.add_argument(
        "--punc_quant",
        type=str,
        default="false",
        choices=["true", "false"],
        help="是否使用量化标点模型 (true: model_quant.onnx, false: model.onnx)"
    )
    model_group.add_argument(
        "--lm_dir",
        type=str,
        default="iic/speech_ngram_lm_zh-cn-ai-wesp-fst",
        help="语言模型路径 (包含TLG.fst文件)"
    )
    model_group.add_argument(
        "--lm_model",
        type=str,
        default="iic/speech_ngram_lm_zh-cn-ai-wesp-fst",
        help="语言模型名称"
    )
    model_group.add_argument(
        "--lm_revision",
        type=str,
        default="v1.0.2",
        help="语言模型版本号"
    )

    model_group.add_argument(
        "--hotword",
        type=str,
        default="./data/hotwords.txt",
        help="热词文件路径 (每行一个热词，格式: 热词 权重)"
    )
    model_group.add_argument(
        "--fst_inc_wts",
        type=int,
        default=20,
        help="FST热词增量偏置权重"
    )
    model_group.add_argument(
        "--download_model_dir",
        type=str,
        default="./models",
        help="模型下载目录 (从ModelScope下载模型到此目录)"
    )
    model_group.add_argument(
        "--cache_dir",
        type=str,
        default="./models",
        help="模型缓存目录 (模型文件存放路径)"
    )
    model_group.add_argument(
        "--quantize",
        type=str,
        default="true",
        choices=["true", "false"],
        help="是否使用量化ASR模型 (true: model_quant.onnx, false: model.onnx)"
    )
    model_group.add_argument(
        "--bladedisc",
        type=str,
        default="true",
        choices=["true", "false"],
        help="是否使用BladeDisc优化模型 (GPU模式下有效)"
    )
    
    # 音频信号处理优化配置 (基于SenseVoice优化建议)
    audio_group = parser.add_argument_group('音频信号处理优化配置')
    audio_group.add_argument(
        "--sample_rate",
        type=int,
        default=16000,
        choices=[8000, 16000, 22050, 44100, 48000],
        help="音频采样率 (Hz) - 根据奈奎斯特定理，应为信号最高频率的2倍以上"
    )
    audio_group.add_argument(
        "--quantization_bits",
        type=int,
        default=16,
        choices=[8, 16, 24, 32],
        help="音频量化位数 - 位数越高，量化误差越小，音质越好"
    )
    audio_group.add_argument(
        "--enable_anti_aliasing",
        action="store_true",
        default=True,
        help="启用抗混叠滤波器 - 防止采样过程中的频谱混叠现象"
    )
    audio_group.add_argument(
        "--mfcc_num_ceps",
        type=int,
        default=13,
        help="MFCC特征提取的倒谱系数数量 - 影响特征表示的精度"
    )
    audio_group.add_argument(
        "--mfcc_num_filters",
        type=int,
        default=26,
        help="MFCC特征提取的梅尔滤波器数量 - 影响频谱分析的精度"
    )
    audio_group.add_argument(
        "--frame_length_ms",
        type=int,
        default=25,
        help="音频帧长度 (毫秒) - 影响时频分析的时间分辨率"
    )
    audio_group.add_argument(
        "--frame_shift_ms",
        type=int,
        default=10,
        help="音频帧移 (毫秒) - 影响时频分析的时间精度"
    )
    audio_group.add_argument(
        "--enable_noise_reduction",
        action="store_true",
        default=False,
        help="启用噪声抑制算法 - 提升噪声环境下的识别准确率"
    )
    audio_group.add_argument(
        "--noise_reduction_strength",
        type=float,
        default=0.5,
        help="噪声抑制强度 (0.0-1.0) - 值越高抑制越强，但可能影响语音质量"
    )
    audio_group.add_argument(
        "--enable_echo_cancellation",
        action="store_true",
        default=False,
        help="启用回声消除算法 - 消除音频中的回声干扰"
    )
    audio_group.add_argument(
        "--preemphasis_coeff",
        type=float,
        default=0.97,
        help="预加重系数 (0.0-1.0) - 用于平衡高频和低频成分"
    )
    
    # 高级噪声抑制配置
    audio_group.add_argument(
        "--noise_reduction_method",
        type=str,
        default="spectral_subtraction",
        choices=["spectral_subtraction", "wiener_filter", "rnnoise", "adaptive"],
        help="噪声抑制算法类型 - 不同算法适用于不同噪声环境"
    )
    audio_group.add_argument(
        "--noise_estimation_method",
        type=str,
        default="minimum_statistics",
        choices=["minimum_statistics", "voice_activity_detection", "adaptive"],
        help="噪声估计方法 - 影响噪声抑制的准确性"
    )
    audio_group.add_argument(
        "--noise_floor_db",
        type=float,
        default=-40.0,
        help="噪声底限 (dB) - 设置噪声抑制的最低阈值"
    )
    audio_group.add_argument(
        "--spectral_floor_db",
        type=float,
        default=-20.0,
        help="频谱底限 (dB) - 防止过度抑制导致的失真"
    )
    
    # 高级回声消除配置
    audio_group.add_argument(
        "--echo_cancellation_method",
        type=str,
        default="nlms",
        choices=["nlms", "rls", "kalman", "adaptive_filter"],
        help="回声消除算法类型 - NLMS适用于大多数场景"
    )
    audio_group.add_argument(
        "--echo_filter_length",
        type=int,
        default=512,
        help="回声滤波器长度 - 影响回声消除的效果和计算复杂度"
    )
    audio_group.add_argument(
        "--echo_step_size",
        type=float,
        default=0.1,
        help="回声消除步长 - 控制自适应滤波器的收敛速度"
    )
    audio_group.add_argument(
        "--echo_suppression_db",
        type=float,
        default=30.0,
        help="回声抑制强度 (dB) - 回声信号的衰减程度"
    )
    
    # 音频增强配置
    audio_group.add_argument(
        "--enable_agc",
        action="store_true",
        default=False,
        help="启用自动增益控制 (AGC) - 自动调整音频音量"
    )
    audio_group.add_argument(
        "--agc_target_level_db",
        type=float,
        default=-16.0,
        help="AGC目标电平 (dB) - 自动增益控制的目标音量"
    )
    audio_group.add_argument(
        "--enable_compressor",
        action="store_true",
        default=False,
        help="启用动态范围压缩器 - 平衡音频动态范围"
    )
    audio_group.add_argument(
        "--compressor_ratio",
        type=float,
        default=4.0,
        help="压缩比 - 控制动态范围压缩的强度"
    )
    audio_group.add_argument(
        "--compressor_threshold_db",
        type=float,
        default=-20.0,
        help="压缩阈值 (dB) - 触发压缩的音量阈值"
    )
    
    # 频谱分析与特征提取优化配置
    spectrum_group = parser.add_argument_group('频谱分析与特征提取配置')
    spectrum_group.add_argument(
        "--fft_size",
        type=int,
        default=512,
        choices=[256, 512, 1024, 2048],
        help="FFT窗口大小 - 影响频谱分析的频率分辨率"
    )
    spectrum_group.add_argument(
        "--window_type",
        type=str,
        default="hamming",
        choices=["hamming", "hanning", "blackman", "kaiser"],
        help="窗函数类型 - 影响频谱泄漏和旁瓣抑制"
    )
    spectrum_group.add_argument(
        "--mel_fmin",
        type=float,
        default=0.0,
        help="梅尔滤波器组最低频率 (Hz) - 影响低频特征提取"
    )
    spectrum_group.add_argument(
        "--mel_fmax",
        type=float,
        default=8000.0,
        help="梅尔滤波器组最高频率 (Hz) - 影响高频特征提取"
    )
    spectrum_group.add_argument(
        "--enable_delta_features",
        action="store_true",
        default=True,
        help="启用一阶差分特征 (Delta) - 提供时间动态信息"
    )
    spectrum_group.add_argument(
        "--enable_delta_delta_features",
        action="store_true",
        default=True,
        help="启用二阶差分特征 (Delta-Delta) - 提供加速度信息"
    )
    spectrum_group.add_argument(
        "--cepstral_lifter",
        type=int,
        default=22,
        help="倒谱提升参数 - 用于平滑倒谱系数"
    )
    spectrum_group.add_argument(
        "--energy_floor",
        type=float,
        default=1e-10,
        help="能量下限 - 防止对数运算中的数值问题"
    )
    spectrum_group.add_argument(
        "--enable_cmvn",
        action="store_true",
        default=True,
        help="启用倒谱均值方差归一化 (CMVN) - 提升鲁棒性"
    )
    spectrum_group.add_argument(
        "--cmvn_window",
        type=int,
        default=300,
        help="CMVN滑动窗口大小 (帧数) - 影响归一化的时间范围"
    )
    
    # SenseVoice模型优化配置
    sensevoice_group = parser.add_argument_group('SenseVoice模型优化配置')
    sensevoice_group.add_argument(
        "--sv_batch_size_s",
        type=int,
        default=30,
        help="SenseVoice批处理时长 (秒) - 影响推理效率和内存使用"
    )
    sensevoice_group.add_argument(
        "--sv_merge_length_s",
        type=int,
        default=15,
        help="SenseVoice音频合并长度 (秒) - 影响VAD后的音频段合并"
    )
    sensevoice_group.add_argument(
        "--sv_language",
        type=str,
        default="zh",
        choices=["auto", "zh", "en", "yue", "ja", "ko", "nospeech"],
        help="SenseVoice识别语言 - auto为自动检测"
    )
    sensevoice_group.add_argument(
        "--sv_use_itn",
        action="store_true",
        default=True,
        help="启用逆文本正则化 (ITN) - 将数字、时间等转换为标准格式"
    )
    sensevoice_group.add_argument(
        "--sv_enable_emotion",
        action="store_true",
        default=True,
        help="启用情感识别 - 检测语音中的情感状态"
    )
    sensevoice_group.add_argument(
        "--sv_enable_event_detection",
        action="store_true",
        default=False,
        help="启用音频事件检测 - 检测音乐、掌声、笑声等事件"
    )
    sensevoice_group.add_argument(
        "--sv_enable_speaker_id",
        action="store_true",
        default=True,
        help="启用说话人识别 - 区分不同说话人"
    )
    sensevoice_group.add_argument(
        "--sv_output_timestamp",
        action="store_true",
        default=True,
        help="输出时间戳信息 - 提供词级别的时间对齐"
    )
    sensevoice_group.add_argument(
        "--sv_merge_vad",
        action="store_true",
        default=True,
        help="合并VAD结果 - 将相邻的语音段合并处理"
    )
    sensevoice_group.add_argument(
        "--sv_max_single_segment_time",
        type=int,
        default=10000,
        help="单段音频最大时长 (毫秒) - 防止单段音频过长"
    )
    sensevoice_group.add_argument(
        "--sv_inference_mode",
        type=str,
        default="offline",
        choices=["offline", "online", "streaming"],
        help="SenseVoice推理模式 - offline为离线模式，online为在线模式"
    )
    sensevoice_group.add_argument(
        "--sv_beam_size",
        type=int,
        default=1,
        help="束搜索大小 - 影响解码质量和速度，值越大质量越高但速度越慢"
    )
    sensevoice_group.add_argument(
        "--sv_temperature",
        type=float,
        default=1.0,
        help="解码温度 - 控制输出随机性，值越小输出越确定"
    )
    sensevoice_group.add_argument(
        "--sv_repetition_penalty",
        type=float,
        default=1.0,
        help="重复惩罚系数 - 减少重复输出，值大于1时惩罚重复"
    )
    sensevoice_group.add_argument(
        "--sv_length_penalty",
        type=float,
        default=1.0,
        help="长度惩罚系数 - 控制输出长度偏好"
    )
    sensevoice_group.add_argument(
        "--sv_enable_vad_realtime",
        action="store_true",
        default=True,
        help="启用实时VAD - 提升流式识别的响应速度"
    )
    sensevoice_group.add_argument(
        "--sv_chunk_size",
        type=int,
        default=960,
        help="音频块大小 (样本数) - 影响流式处理的延迟"
    )
    sensevoice_group.add_argument(
        "--sv_encoder_chunk_look_back",
        type=int,
        default=4,
        help="编码器回看块数 - 影响上下文信息的利用"
    )
    sensevoice_group.add_argument(
        "--sv_decoder_chunk_look_back",
        type=int,
        default=1,
        help="解码器回看块数 - 影响解码时的上下文"
    )

    upload_asr_group = parser.add_argument_group('上传文件识别配置')
    upload_asr_group.add_argument(
        "--upload_asr_batch_size_s",
        type=int,
        default=60,
        help="上传文件ASR识别批处理时长 (秒)"
    )
    upload_asr_group.add_argument(
        "--upload_asr_merge_length_s",
        type=int,
        default=8,
        help="上传文件ASR识别VAD合并长度 (秒)，仅在upload_asr_merge_vad开启时生效"
    )
    upload_asr_group.add_argument(
        "--upload_asr_merge_vad",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="上传文件ASR是否合并FunASR内部VAD段；默认关闭以优先保留说话人边界"
    )
    upload_asr_group.add_argument(
        "--upload_asr_language",
        type=str,
        default="zh",
        choices=["auto", "zh", "en", "yue", "ja", "ko", "nospeech"],
        help="上传文件ASR识别语言"
    )
    upload_asr_group.add_argument(
        "--upload_asr_vad_model",
        type=str,
        default="fsmn-vad",
        help="上传文件ASR内置分段使用的VAD模型"
    )
    upload_asr_group.add_argument(
        "--upload_diarization_model",
        type=str,
        default="speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx",
        help="已废弃：旧ModelScope asr-inference ONNX diarization入口已不可用，上传人员分离改用FunASR官网AutoModel内置spk_model"
    )
    upload_asr_group.add_argument(
        "--upload_asr_spk_model",
        type=str,
        default="cam++",
        help="上传文件ASR内置说话人分离使用的CAM++模型，仅产生音频内spk编号"
    )
    upload_asr_group.add_argument(
        "--upload_asr_punc_model",
        type=str,
        default="ct-punc",
        help="上传文件ASR内置说话人分离使用的标点模型；默认加载ct-punc但按vad_segment分配说话人，避免punc/timestamp错位"
    )
    upload_asr_group.add_argument(
        "--upload_asr_enable_internal_speaker",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="上传文件ASR主模型启用FunASR官网内置spk_model说话人输出；默认开启"
    )
    upload_asr_group.add_argument(
        "--upload_asr_spk_mode",
        type=str,
        default="vad_segment",
        choices=["vad_segment", "punc_segment"],
        help="上传文件ASR内置说话人分离模式，默认按VAD段分配，避免punc/timestamp错位"
    )
    upload_asr_group.add_argument(
        "--upload_asr_vad_max_single_segment_time",
        type=int,
        default=15000,
        help="上传文件ASR VAD单段最大时长 (毫秒)，较短时更利于保留多人边界"
    )
    
    # 说话人识别配置
    speaker_group = parser.add_argument_group('说话人识别配置')
    speaker_group.add_argument(
        "--enable_speaker_verification",
        action="store_true",
        default=True,
        help="启用说话人验证功能"
    )
    speaker_group.add_argument(
        "--speaker_model",
        type=str,
        default="iic/speech_campplus_sv_zh-cn_16k-common",
        help="声纹注册和实名对比使用的CAM++ speaker-verification模型"
    )
    speaker_group.add_argument(
        "--speaker_model_revision",
        type=str,
        default="v2.0.2",
        help="说话人验证模型版本号"
    )
    speaker_group.add_argument(
        "--speaker_threshold",
        type=float,
        default=0.4,
        help="说话人验证阈值 (0.0-1.0, 越高越严格)"
    )
    speaker_group.add_argument(
        "--speaker_db_path",
        type=str,
        default="./data/speaker",
        help="说话人数据库存储路径"
    )
    speaker_group.add_argument(
        "--enable_speaker_diarization",
        action="store_true",
        default=True,
        help="启用说话人分离功能 (当无已注册说话人时自动启用)"
    )
    speaker_group.add_argument(
        "--speaker_diarization_model",
        type=str,
        default="damo/speech_campplus_sv_zh-cn_16k-common",
        help="说话人分离模型名称"
    )
    speaker_group.add_argument(
        "--speaker_diarization_model_revision",
        type=str,
        default="v2.0.2",
        help="说话人分离模型版本号"
    )
    speaker_group.add_argument(
        "--speaker_labeling_similarity_threshold",
        type=float,
        default=0.4,
        help="说话人标记相似度阈值 (0.0-1.0, 已注册说话人匹配阈值)"
    )
    speaker_group.add_argument(
        "--speaker_labeling_consistency_threshold",
        type=float,
        default=0.3,
        help="说话人标记一致性阈值 (0.0-1.0, 动态标签一致性检查阈值)"
    )

    
    # 翻译模型配置
    translation_group = parser.add_argument_group('翻译模型配置')
    translation_group.add_argument(
        "--enable_translation",
        action="store_true",
        help="启用中英翻译功能"
    )
    translation_group.add_argument(
        "--translation_model",
        type=str,
        default="iic/nlp_csanmt_translation_zh2en",
        help="中英翻译模型名称"
    )
    translation_group.add_argument(
        "--translation_model_revision",
        type=str,
        default="v1.0.0",
        help="翻译模型版本号"
    )
    
    # 文档分段模型配置
    segmentation_group = parser.add_argument_group('文档分段模型配置')
    segmentation_group.add_argument(
        "--enable_segmentation",
        action="store_true",
        help="启用文档分段功能"
    )
    segmentation_group.add_argument(
        "--segmentation_model",
        type=str,
        default="iic/nlp_bert_document-segmentation_chinese-base",
        help="中文文档分段模型名称"
    )
    segmentation_group.add_argument(
        "--segmentation_model_revision",
        type=str,
        default="v1.0.0",
        help="文档分段模型版本号"
    )
    
    # 热词管理配置
    hotword_group = parser.add_argument_group('热词管理配置')
    hotword_group.add_argument(
        "--hotword_storage_path",
        type=str,
        default="data/hotwords.json",
        help="热词存储文件路径"
    )
    
    # 2pass模式配置
    twopass_group = parser.add_argument_group('2pass模式配置')
    twopass_group.add_argument(
        "--enable_2pass",
        action="store_true",
        default=True,
        help="启用2pass模式 (在线+离线双通道识别)"
    )
    twopass_group.add_argument(
        "--disable_2pass",
        action="store_true",
        help="禁用2pass模式 (使用传统单通道模式)"
    )
    # twopass_group.add_argument(
    #     "--global_beam",
    #     type=float,
    #     default=3.0,
    #     help="解码beam搜索的全局beam大小"
    # )
    # twopass_group.add_argument(
    #     "--lattice_beam",
    #     type=float,
    #     default=3.0,
    #     help="lattice生成的beam大小"
    # )
    # twopass_group.add_argument(
    #     "--am_scale",
    #     type=float,
    #     default=10.0,
    #     help="声学模型缩放因子"
    # )
    # twopass_group.add_argument(
    #     "--batch_size",
    #     type=int,
    #     default=4,
    #     help="GPU模式下ASR模型的批处理大小"
    # )
    
    # 线程配置
    thread_group = parser.add_argument_group('线程配置')
    thread_group.add_argument(
        "--io_thread_num",
        type=int,
        default=2,
        help="IO线程数量"
    )
    thread_group.add_argument(
        "--decoder_thread_num",
        type=int,
        default=8,
        help="解码器线程数量"
    )
    thread_group.add_argument(
        "--model_thread_num",
        type=int,
        default=1,
        help="模型线程数量"
    )
    
    # 深度学习推理优化配置
    inference_group = parser.add_argument_group('深度学习推理优化配置')
    inference_group.add_argument(
        "--enable_mixed_precision",
        action="store_true",
        default=False,
        help="启用混合精度推理 - 使用FP16加速推理，减少显存占用"
    )
    inference_group.add_argument(
        "--enable_tensorrt",
        action="store_true",
        default=False,
        help="启用TensorRT优化 - NVIDIA GPU上的推理加速"
    )
    inference_group.add_argument(
        "--enable_onnx_optimization",
        action="store_true",
        default=False,
        help="启用ONNX模型优化 - 跨平台推理优化"
    )
    inference_group.add_argument(
        "--batch_inference_size",
        type=int,
        default=1,
        help="批量推理大小 - 影响推理吞吐量和延迟"
    )
    inference_group.add_argument(
        "--max_sequence_length",
        type=int,
        default=512,
        help="最大序列长度 - 限制输入序列长度以控制内存使用"
    )
    inference_group.add_argument(
        "--enable_kv_cache",
        action="store_true",
        default=True,
        help="启用KV缓存 - 加速自回归模型的推理"
    )
    inference_group.add_argument(
        "--kv_cache_size",
        type=int,
        default=1024,
        help="KV缓存大小 - 影响缓存效果和内存占用"
    )
    inference_group.add_argument(
        "--enable_dynamic_batching",
        action="store_true",
        default=False,
        help="启用动态批处理 - 自动调整批大小以优化吞吐量"
    )
    inference_group.add_argument(
        "--max_batch_delay_ms",
        type=int,
        default=100,
        help="最大批处理延迟 (毫秒) - 动态批处理的等待时间"
    )
    inference_group.add_argument(
        "--enable_model_parallelism",
        action="store_true",
        default=False,
        help="启用模型并行 - 在多GPU上分布模型计算"
    )
    inference_group.add_argument(
        "--pipeline_parallel_size",
        type=int,
        default=1,
        help="流水线并行大小 - 模型层间的并行度"
    )
    inference_group.add_argument(
        "--tensor_parallel_size",
        type=int,
        default=1,
        help="张量并行大小 - 单层内的并行度"
    )
    inference_group.add_argument(
        "--enable_gradient_checkpointing",
        action="store_true",
        default=False,
        help="启用梯度检查点 - 以计算换内存，减少显存占用"
    )
    inference_group.add_argument(
        "--memory_pool_size_mb",
        type=int,
        default=1024,
        help="内存池大小 (MB) - 预分配内存池以减少内存碎片"
    )
    inference_group.add_argument(
        "--enable_cpu_offload",
        action="store_true",
        default=False,
        help="启用CPU卸载 - 将部分计算卸载到CPU以节省GPU内存"
    )
    inference_group.add_argument(
        "--cpu_offload_layers",
        type=int,
        default=0,
        help="CPU卸载层数 - 卸载到CPU的模型层数"
    )
    inference_group.add_argument(
        "--enable_quantization",
        action="store_true",
        default=False,
        help="启用模型量化 - 使用INT8量化减少模型大小和推理时间"
    )
    inference_group.add_argument(
        "--quantization_method",
        type=str,
        default="dynamic",
        choices=["dynamic", "static", "qat"],
        help="量化方法 - dynamic为动态量化，static为静态量化，qat为量化感知训练"
    )
    inference_group.add_argument(
        "--enable_pruning",
        action="store_true",
        default=False,
        help="启用模型剪枝 - 移除不重要的权重以加速推理"
    )
    inference_group.add_argument(
        "--pruning_ratio",
        type=float,
        default=0.1,
        help="剪枝比例 (0.0-1.0) - 移除权重的比例"
    )
    
    # 硬件配置
    hardware_group = parser.add_argument_group('硬件配置')
    hardware_group.add_argument(
        "--ngpu", 
        type=int, 
        default=0, 
        help="GPU数量 (0=仅使用CPU, 1=使用1个GPU)"
    )
    hardware_group.add_argument(
        "--device", 
        type=str, 
        default="cpu", 
        choices=["cuda", "cpu", "mps"],
        help="计算设备类型 (cpu/cuda/mps)"
    )
    hardware_group.add_argument(
        "--ncpu",
        type=int,
        default=4,
        help="CPU核心数 (用于CPU推理时的线程数)",
    )
    
    # 串口配置
    serial_group = parser.add_argument_group('串口配置')
    serial_group.add_argument(
        "--enable_serial",
        action="store_true",
        dest="enable_serial",
        default=True,
        help="启用串口接收功能 (直接运行 main.py 默认启用；start.sh 默认关闭)"
    )
    serial_group.add_argument(
        "--disable_serial",
        action="store_false",
        dest="enable_serial",
        help="禁用串口接收功能"
    )
    serial_group.add_argument(
        "--list_serial_ports",
        action="store_true",
        default=False,
        help="列出所有可用的串口并退出"
    )
    serial_group.add_argument(
        "--serial_port",
        type=str,
        default="/dev/cu.usbserial-A400CKPT",
        help="串口号 (Windows: COM1, COM2; Linux: /dev/ttyUSB0, /dev/ttyS0)"
    )
    serial_group.add_argument(
        "--serial_baudrate",
        type=int,
        default=9600,
        help="串口波特率 (默认: 9600)"
    )
    serial_group.add_argument(
        "--serial_config",
        type=str,
        default="config/serial_config.yaml",
        help="串口配置文件路径"
    )

    try:
        parsed_args = parser.parse_args(args)
        
        # ----------------------------------------------------------------
        # 参数后处理和验证
        # ----------------------------------------------------------------
        
        # 根据model_type自动设置模型配置
        if parsed_args.model_type == "sensevoice":
            # 如果用户没有手动指定模型，则使用SenseVoiceSmall默认配置
            if parsed_args.asr_model == "iic/SenseVoiceSmall":
                parsed_args.asr_model = "iic/SenseVoiceSmall"
                parsed_args.asr_model_revision = "master"
        elif parsed_args.model_type == "paraformer":
            # 如果选择paraformer，则使用传统模型配置
            if parsed_args.asr_model == "iic/SenseVoiceSmall":  # 如果还是默认值，则切换
                parsed_args.asr_model = "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
                parsed_args.asr_model_revision = "v2.0.4"
        
        # 处理disable_2pass参数
        if parsed_args.disable_2pass:
            parsed_args.enable_2pass = False
        
        # 2pass模式配置验证
        if parsed_args.enable_2pass:
            # 确保在线模型和离线模型都已配置
            if not parsed_args.asr_model_online:
                raise ArgumentError("启用2pass模式时必须指定在线模型 (--asr_model_online)")
            if not parsed_args.asr_model:
                raise ArgumentError("启用2pass模式时必须指定离线模型 (--asr_model)")
        
        # 热词文件路径处理
        if parsed_args.hotword and parsed_args.hotword.startswith('/workspace/'):
            # 将/workspace/路径转换为相对于项目根目录的路径
            parsed_args.hotword = parsed_args.hotword.replace('/workspace/', './')
        
        # 下载目录路径处理
        if parsed_args.download_model_dir and parsed_args.download_model_dir.startswith('/workspace/'):
            # 将/workspace/路径转换为相对于项目根目录的路径
            parsed_args.download_model_dir = parsed_args.download_model_dir.replace('/workspace/', './')
        
        # 参数验证
        if parsed_args.port < 1 or parsed_args.port > 65535:
            raise ArgumentError(f"端口号必须在1-65535范围内，当前值: {parsed_args.port}")
        
        if parsed_args.ngpu < 0:
            raise ArgumentError(f"GPU数量不能为负数，当前值: {parsed_args.ngpu}")
            
        if parsed_args.ncpu < 1:
            raise ArgumentError(f"CPU核心数必须大于0，当前值: {parsed_args.ncpu}")
            
        # SSL配置验证
        if bool(parsed_args.certfile) != bool(parsed_args.keyfile):
            raise ArgumentError("SSL证书文件和私钥文件必须同时提供或同时省略")
            
        return parsed_args
        
    except SystemExit as e:
        # argparse在解析失败时会调用sys.exit()，我们捕获并转换为自定义异常
        if e.code != 0:
            raise ArgumentError("参数解析失败") from e
        raise  # 正常的help退出，重新抛出
    except Exception as e:
        raise ArgumentError(f"参数解析错误: {e}") from e
