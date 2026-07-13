#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器状态管理模块。

负责管理服务器状态、模型加载和连接管理。
"""

import logging
import os
import time
from typing import Any, Optional, Set, Dict

import websockets


class ModelLoadError(Exception):
    """模型加载相关异常。"""
    pass


MODEL_NAME_ALIASES = {
    "fsmn-vad": "speech_fsmn_vad_zh-cn-16k-common-pytorch",
    "ct-punc": "punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
    "cam++": "speech_campplus_sv_zh-cn_16k-common",
}

MODEL_CONFIG_FILES = ("config.yaml", "configuration.json", "config.json")
MODEL_FILE_EXTENSIONS = ("*.onnx", "*.pt", "*.torchscript", "*.bin", "*.fst", "*.safetensors")


class ServerState:
    """服务器状态管理类。

    负责维护全局状态，包括：
    - WebSocket连接管理
    - 模型实例存储
    - 服务器配置信息

    Attributes:
        websocket_users: 当前连接的WebSocket客户端集合
        model_asr: 离线ASR模型实例
        model_asr_streaming: 在线流式ASR模型实例
        model_asr_upload: 上传文件识别专用ASR模型实例
        model_vad: VAD模型实例
        model_punc: 标点恢复模型实例
        model_speaker: 说话人验证模型实例
        args: 命令行参数
        logger: 日志记录器
        subtitle_settings: 字幕显示设置字典
    """

    def __init__(self) -> None:
        """初始化服务器状态。"""
        self.websocket_users: Set[websockets.WebSocketServerProtocol] = set()
        self.model_asr: Optional[Any] = None
        self.model_asr_streaming: Optional[Any] = None
        self.model_asr_upload: Optional[Any] = None
        self.model_vad: Optional[Any] = None
        self.model_punc: Optional[Any] = None
        self.model_lm: Optional[Any] = None
        self.model_itn: Optional[Any] = None
        self.model_speaker: Optional[Any] = None
        self.model_translation: Optional[Any] = None
        self.model_segmentation: Optional[Any] = None
        self.hotword_map: dict = {}  # 热词映射表
        self.args: Optional[Any] = None
        self.logger: Optional[logging.Logger] = None
        self.subtitle_settings: Optional[dict] = None  # 字幕显示设置


def load_hotwords(hotword_path: str) -> dict:
    """加载热词文件，类似C++服务器的ExtractHws函数。
    
    Args:
        hotword_path: 热词文件路径
        
    Returns:
        热词映射字典 {热词: 权重}
    """
    hotword_map = {}
    try:
        with open(hotword_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):  # 跳过空行和注释
                    continue
                
                # 解析格式: "热词 权重" 或 "热词\t权重"
                parts = line.split()
                if len(parts) >= 2:
                    hotword = parts[0]
                    try:
                        weight = int(parts[1])
                        hotword_map[hotword] = weight
                    except ValueError:
                        print(f"警告: 热词文件第{line_num}行权重格式错误: {line}")
                elif len(parts) == 1:
                    # 只有热词，使用默认权重
                    hotword_map[parts[0]] = 20
                else:
                    print(f"警告: 热词文件第{line_num}行格式错误: {line}")
    except Exception as e:
        print(f"错误: 无法读取热词文件 {hotword_path}: {e}")
    
    return hotword_map


def load_hotword_list(hotword_path: str) -> list:
    """从热词文件中提取热词列表（仅热词，不包含权重）。
    
    Args:
        hotword_path: 热词文件路径
        
    Returns:
        热词列表
    """
    hotword_list = []
    try:
        with open(hotword_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):  # 跳过空行和注释
                    continue
                
                # 解析格式: "热词 权重" 或 "热词\t权重"
                parts = line.split()
                if len(parts) >= 1:
                    hotword = parts[0]
                    if hotword not in hotword_list:  # 避免重复
                        hotword_list.append(hotword)
    except Exception as e:
        print(f"错误: 无法读取热词文件 {hotword_path}: {e}")
        # 返回默认热词列表
        hotword_list = ["真视通", "数字科技", "紫荆视通", "紫荆", "玲珑AI", "玲珑", "博数", "博数智源", "视频会议", "音视频", "无纸化", "AV", "AI", "无纸化系统", "南"]
    
    return hotword_list


def _is_complete_local_model_dir(model_path: str) -> bool:
    if not os.path.isdir(model_path):
        return False

    has_config = any(os.path.exists(os.path.join(model_path, name)) for name in MODEL_CONFIG_FILES)

    import glob
    has_model_file = any(
        glob.glob(os.path.join(model_path, pattern))
        for pattern in MODEL_FILE_EXTENSIONS
    )

    return has_config and has_model_file


def _local_model_candidates(model_name: str, root_dir: str) -> list:
    if not model_name:
        return []

    candidates = []
    expanded_name = os.path.expanduser(model_name)
    if os.path.isabs(expanded_name):
        candidates.append(expanded_name)
    elif expanded_name.startswith(".") or os.sep in expanded_name:
        candidates.append(os.path.abspath(os.path.join(root_dir, expanded_name)))

    actual_model_name = model_name.split('/')[-1] if '/' in model_name else model_name
    local_name = MODEL_NAME_ALIASES.get(actual_model_name, actual_model_name)
    candidates.append(os.path.join(root_dir, 'models', local_name))

    if local_name != actual_model_name:
        candidates.append(os.path.join(root_dir, 'models', actual_model_name))

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if normalized not in seen:
            seen.add(normalized)
            unique_candidates.append(normalized)
    return unique_candidates


def get_local_model_path(model_name: str, root_dir: str) -> Optional[str]:
    """检查本地是否存在模型文件。
    
    Args:
        model_name: 模型名称，如 'iic/SenseVoiceSmall'
        root_dir: 项目根目录
        
    Returns:
        如果找到本地模型则返回路径，否则返回None
    """
    for local_model_path in _local_model_candidates(model_name, root_dir):
        if _is_complete_local_model_dir(local_model_path):
            return local_model_path

    return None


def require_local_model_path(model_name: str, root_dir: str, purpose: str) -> str:
    local_model_path = get_local_model_path(model_name, root_dir)
    if local_model_path:
        return local_model_path

    candidates = ", ".join(_local_model_candidates(model_name, root_dir))
    raise ModelLoadError(
        f"{purpose}模型未在本地 models 目录找到: {model_name}. "
        f"已检查: {candidates}. "
        "请先运行 `.venv/bin/python organize_models.py` 下载/整理模型后再启动服务。"
    )


def build_sensevoice_config(args) -> Dict[str, Any]:
    """构建SenseVoice模型的配置参数。
    
    将命令行参数中的sv_*参数转换为SenseVoice模型可识别的格式。
    
    Args:
        args: 命令行参数对象
        
    Returns:
        Dict[str, Any]: SenseVoice模型配置字典
    """
    config = {}
    
    # 基础配置参数
    if hasattr(args, 'sv_batch_size_s') and args.sv_batch_size_s is not None:
        config['batch_size_s'] = args.sv_batch_size_s
        
    if hasattr(args, 'sv_merge_length_s') and args.sv_merge_length_s is not None:
        config['merge_length_s'] = args.sv_merge_length_s
        
    if hasattr(args, 'sv_language') and args.sv_language is not None:
        config['language'] = args.sv_language
        
    if hasattr(args, 'sv_use_itn') and args.sv_use_itn is not None:
        config['use_itn'] = args.sv_use_itn
        
    if hasattr(args, 'sv_enable_emotion') and args.sv_enable_emotion is not None:
        config['ban_emo_unk'] = not args.sv_enable_emotion  # 反向映射
        
    if hasattr(args, 'sv_enable_event_detection') and args.sv_enable_event_detection is not None:
        config['enable_event_detection'] = args.sv_enable_event_detection
        
    if hasattr(args, 'sv_enable_speaker_id') and args.sv_enable_speaker_id is not None:
        config['enable_speaker_id'] = args.sv_enable_speaker_id
        
    if hasattr(args, 'sv_output_timestamp') and args.sv_output_timestamp is not None:
        config['output_timestamp'] = args.sv_output_timestamp
        
    if hasattr(args, 'sv_merge_vad') and args.sv_merge_vad is not None:
        config['merge_vad'] = args.sv_merge_vad
        
    if hasattr(args, 'sv_max_single_segment_time') and args.sv_max_single_segment_time is not None:
        config['max_single_segment_time'] = args.sv_max_single_segment_time
        
    # 推理模式和解码参数
    if hasattr(args, 'sv_inference_mode') and args.sv_inference_mode is not None:
        config['inference_mode'] = args.sv_inference_mode
        
    if hasattr(args, 'sv_beam_size') and args.sv_beam_size is not None:
        config['beam_size'] = args.sv_beam_size
        
    if hasattr(args, 'sv_temperature') and args.sv_temperature is not None:
        config['temperature'] = args.sv_temperature
        
    if hasattr(args, 'sv_repetition_penalty') and args.sv_repetition_penalty is not None:
        config['repetition_penalty'] = args.sv_repetition_penalty
        
    if hasattr(args, 'sv_length_penalty') and args.sv_length_penalty is not None:
        config['length_penalty'] = args.sv_length_penalty
        
    # VAD和流式处理参数
    if hasattr(args, 'sv_enable_vad_realtime') and args.sv_enable_vad_realtime is not None:
        config['enable_vad_realtime'] = args.sv_enable_vad_realtime
        
    if hasattr(args, 'sv_chunk_size') and args.sv_chunk_size is not None:
        config['chunk_size'] = args.sv_chunk_size
        
    if hasattr(args, 'sv_encoder_chunk_look_back') and args.sv_encoder_chunk_look_back is not None:
        config['encoder_chunk_look_back'] = args.sv_encoder_chunk_look_back
        
    if hasattr(args, 'sv_decoder_chunk_look_back') and args.sv_decoder_chunk_look_back is not None:
        config['decoder_chunk_look_back'] = args.sv_decoder_chunk_look_back
    
    # 禁用VAD (根据ModelScope官方文档，设置vad_model=None)
    config['vad_model'] = None
        
    return config


def _resolve_model_reference(model_name: Optional[str], root_dir: str) -> Optional[str]:
    if not model_name:
        return None
    return get_local_model_path(model_name, root_dir)


def build_upload_asr_config(args, root_dir: str) -> Dict[str, Any]:
    """构建上传文件识别专用的FunASR配置。"""
    config = {
        'trust_remote_code': True,
        'vad_model': _resolve_model_reference(getattr(args, 'upload_asr_vad_model', 'fsmn-vad'), root_dir),
        'vad_kwargs': {
            'max_single_segment_time': getattr(args, 'upload_asr_vad_max_single_segment_time', 30000)
        },
    }

    if getattr(args, 'upload_asr_enable_internal_speaker', False):
        punc_model = _resolve_model_reference(getattr(args, 'upload_asr_punc_model', 'ct-punc'), root_dir)
        spk_model = _resolve_model_reference(getattr(args, 'upload_asr_spk_model', 'cam++'), root_dir)
        if spk_model:
            config['spk_model'] = spk_model
            config['spk_mode'] = getattr(args, 'upload_asr_spk_mode', 'vad_segment')
            if punc_model:
                config['punc_model'] = punc_model
        else:
            logging.getLogger(__name__).warning(
                "上传ASR内置说话人模型未在本地找到，已仅启用VAD文本识别配置"
            )

    return {key: value for key, value in config.items() if value}


def load_models(server_state: ServerState) -> None:
    """加载所有AI模型。

    按顺序加载：
    1. 离线ASR模型 (高精度，延迟较高)
    2. 在线流式ASR模型 (低延迟，精度较高)
    3. VAD语音活动检测模型
    4. 标点符号恢复模型 (可选)
    5. 说话人验证模型 (可选)
    
    只使用本地模型文件。如果本地不存在，需要先运行 organize_models.py 下载到 models 目录。

    Args:
        server_state: 服务器状态对象

    Raises:
        ModelLoadError: 当模型加载失败时抛出
        ImportError: 如果无法导入funasr模块

    Examples:
        >>> state = ServerState()
        >>> state.args = parse_arguments()
        >>> state.logger = setup_logging()
        >>> load_models(state)
    """
    logger = server_state.logger
    args = server_state.args
    
    logger.info("🤖 开始加载AI模型...")
    start_time = time.time()
    
    # 获取项目根目录 - 从 src/modules/core/server_state.py 到项目根目录需要4级
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 动态读取热词列表
    hotword_file_path = os.path.join(root_dir, "data", "hotwords.txt")
    dynamic_hotword_list = load_hotword_list(hotword_file_path)
    logger.info(f"📝 从 {hotword_file_path} 动态加载热词列表: {dynamic_hotword_list}")
    
    try:
        # 导入FunASR库
        logger.info("📦 正在导入FunASR库...")
        from funasr import AutoModel
        logger.info("✅ FunASR库导入成功")
        
        # 1. 加载离线ASR模型
        local_asr_path = require_local_model_path(args.asr_model, root_dir, "离线ASR")
        logger.info(f"🔍 检查本地模型路径: {args.asr_model} -> {local_asr_path}")
        
        # 检查是否为SenseVoice模型并构建配置
        is_sensevoice = 'sensevoice' in args.asr_model.lower()
        sensevoice_config = build_sensevoice_config(args) if is_sensevoice else {}
        
        logger.info(f"🎯 使用本地离线ASR模型: {local_asr_path}")
        if is_sensevoice and sensevoice_config:
            logger.info(f"🔧 应用SenseVoice优化配置: {sensevoice_config}")
        model_config = {
            'model': local_asr_path,
            'ngpu': args.ngpu,
            'ncpu': args.ncpu,
            'device': args.device,
            'disable_pbar': True,
            'disable_log': True,
            'disable_update': True,
            'device_id': 0,
            'vad_model': None,
            "hotword_list": dynamic_hotword_list,
            "hotword_weight": 1.5
        }
        if is_sensevoice:
            model_config.update(sensevoice_config)

        server_state.model_asr = AutoModel(**model_config)
        logger.info("✅ 离线ASR模型加载完成")
        
        # 2. 加载在线流式ASR模型
        if getattr(args, 'enable_2pass', True):
            local_asr_online_path = require_local_model_path(args.asr_model_online, root_dir, "在线流式ASR")
            
            # 检查在线模型是否为SenseVoice
            is_sensevoice_online = 'sensevoice' in args.asr_model_online.lower()
            sensevoice_online_config = build_sensevoice_config(args) if is_sensevoice_online else {}
            
            logger.info(f"🌊 使用本地在线流式ASR模型: {local_asr_online_path}")
            if is_sensevoice_online and sensevoice_online_config:
                logger.info(f"🔧 应用SenseVoice在线优化配置: {sensevoice_online_config}")
            model_config = {
                'model': local_asr_online_path,
                'ngpu': args.ngpu,
                'ncpu': args.ncpu,
                'device': args.device,
                'disable_pbar': True,
                'disable_log': True,
                'disable_update': True,
                'device_id': 0,
                "hotword_list": dynamic_hotword_list,
                "hotword_weight": 1.5
            }
            if is_sensevoice_online:
                model_config.update(sensevoice_online_config)

            server_state.model_asr_streaming = AutoModel(**model_config)
            logger.info("✅ 在线流式ASR模型加载完成")
        else:
            server_state.model_asr_streaming = None
            logger.info("⚠️ 2pass模式已禁用，跳过在线流式ASR模型加载")

        # 3. 加载上传文件识别专用ASR模型
        upload_asr_model = getattr(args, 'upload_asr_model', 'iic/SenseVoiceSmall')
        local_upload_asr_path = require_local_model_path(upload_asr_model, root_dir, "上传文件ASR")
        upload_asr_config = build_upload_asr_config(args, root_dir)
        logger.info(f"🔍 检查上传文件ASR模型路径: {upload_asr_model} -> {local_upload_asr_path}")

        logger.info(f"📤 使用本地上传文件ASR模型: {local_upload_asr_path}")
        model_config = {
            'model': local_upload_asr_path,
            'ngpu': args.ngpu,
            'ncpu': args.ncpu,
            'device': args.device,
            'disable_pbar': True,
            'disable_log': True,
            'disable_update': True,
            'device_id': 0,
            'hotword_list': dynamic_hotword_list,
            'hotword_weight': 1.5,
        }
        model_config.update(upload_asr_config)
        server_state.model_asr_upload = AutoModel(**model_config)
        logger.info("✅ 上传文件ASR模型加载完成")
        
        # 4. 加载VAD模型
        # local_vad_path = get_local_model_path(args.vad_model, root_dir)
        # # 构建VAD模型配置参数
        # vad_config = {
        #     "ngpu": args.ngpu,
        #     "ncpu": args.ncpu,
        #     "device": args.device,
        #     "disable_pbar": True,
        #     "disable_log": True,
        #     "disable_update": True,
        # }
        
        # # 构建VAD特定配置参数 (使用vad_kwargs统一传递)
        # vad_kwargs = {}
        # if hasattr(args, 'vad_max_single_segment_time'):
        #     vad_kwargs["max_single_segment_time"] = args.vad_max_single_segment_time
        # if hasattr(args, 'vad_speech_noise_thres'):
        #     vad_kwargs["speech_noise_thres"] = args.vad_speech_noise_thres
        
        # # 将VAD特定参数添加到配置中
        # if vad_kwargs:
        #     vad_config["vad_kwargs"] = vad_kwargs
        # if local_vad_path:
        #     logger.info(f"🔊 使用本地VAD语音检测模型: {local_vad_path}")
        #     server_state.model_vad = AutoModel(
        #         model=local_vad_path,
        #         device_id=0,
        #         **vad_config
        #     )
        # else:
        #     logger.info(f"🔊 从远程加载VAD语音检测模型: {args.vad_model}")
        #     vad_config["model_revision"] = args.vad_model_revision
        #     vad_config["cache_dir"] = args.cache_dir
        #     server_state.model_vad = AutoModel(
        #         model=args.vad_model,
        #         device_id=0,
        #         **vad_config
        #     )
        # # 记录VAD配置信息
        # logger.info(f"🎚️ VAD配置: 量化={args.vad_quant}, 最大段长={getattr(args, 'vad_max_single_segment_time', 60000)}ms")
        # logger.info(f"🎚️ VAD阈值: 语音/噪声={getattr(args, 'vad_speech_noise_thres', 0.6)}")
        # logger.info("✅ VAD模型加载完成")
        
        # # 4. 加载标点恢复模型 (可选)
        # if args.punc_model and args.punc_model.strip():
        #     local_punc_path = get_local_model_path(args.punc_model, root_dir)
        #     if local_punc_path:
        #         logger.info(f"📝 使用本地标点恢复模型: {local_punc_path}")
        #         server_state.model_punc = AutoModel(
        #             model=local_punc_path,
        #             inference_mode="onnxruntime",
        #             ngpu=args.ngpu,
        #             ncpu=args.ncpu,
        #             device=args.device,
        #             device_id=0,
        #             disable_pbar=True,
        #             disable_update=True,
        #             disable_log=True,
        #         )
        #     else:
        #         logger.info(f"📝 从远程加载标点恢复模型: {args.punc_model}")
        #         server_state.model_punc = AutoModel(
        #             model=args.punc_model,
        #             inference_mode="onnxruntime",
        #             model_revision=args.punc_model_revision,
        #             cache_dir=args.cache_dir,
        #             ngpu=args.ngpu,
        #             ncpu=args.ncpu,
        #             device=args.device,
        #             disable_update=True,
        #             device_id=0,
        #             disable_pbar=True,
        #             disable_log=True,
        #         )
        #     logger.info("✅ 标点恢复模型加载完成")
        # else:
        #     logger.info("⚠️ 跳过标点恢复模型加载 (未指定模型)")
        #     server_state.model_punc = None
            
        # 5. 加载说话人验证/分离模型 (已禁用 - 使用串口识别说话人)
        # 串口模式下不需要声纹模型，直接跳过加载以节省内存和启动时间
        speaker_enabled = False  # 强制禁用声纹模型加载
        # speaker_enabled = (
        #     (hasattr(args, 'enable_speaker_verification') and args.enable_speaker_verification) or
        #     (hasattr(args, 'enable_speaker_diarization') and args.enable_speaker_diarization)
        # )
        
        if speaker_enabled:
            # 优先使用说话人验证模型，如果未指定则使用分离模型
            speaker_model = getattr(args, 'speaker_model', None)
            if not speaker_model or not speaker_model.strip():
                speaker_model = getattr(args, 'speaker_diarization_model', 'damo/speech_campplus_sv_zh-cn_16k-common')
            
            if speaker_model:
                local_speaker_path = require_local_model_path(speaker_model, root_dir, "说话人")
                logger.info(f"🔍 说话人模型检查: {speaker_model} -> {local_speaker_path}")
                logger.info(f"🎭 使用本地说话人模型: {local_speaker_path}")
                server_state.model_speaker = AutoModel(
                    model=local_speaker_path,
                    inference_mode="onnxruntime",
                    ngpu=args.ngpu,
                    ncpu=args.ncpu,
                    device=args.device,
                    device_id=0,
                    disable_pbar=True,
                    disable_log=True,
                    disable_update=True,
                )
                
                # 记录启用的功能
                enabled_features = []
                if hasattr(args, 'enable_speaker_verification') and args.enable_speaker_verification:
                    enabled_features.append("说话人验证")
                if hasattr(args, 'enable_speaker_diarization') and args.enable_speaker_diarization:
                    enabled_features.append("说话人分离")
                
                logger.info(f"✅ 说话人模型加载完成 (支持: {', '.join(enabled_features)})")
            else:
                logger.info("⚠️ 跳过说话人模型加载 (未指定模型)")
                server_state.model_speaker = None
        else:
            logger.info("⚠️ 跳过说话人模型加载 (功能未启用)")
            server_state.model_speaker = None
            
        # 6. 加载语言模型 (可选)
        # lm_model_name = getattr(args, 'lm_model', None) or getattr(args, 'lm_dir', None)
        # if lm_model_name and lm_model_name.strip() and lm_model_name.lower() not in ['none', 'null', '']:
        #     # 检查本地路径
        #     if hasattr(args, 'lm_dir') and args.lm_dir and os.path.exists(args.lm_dir):
        #         logger.info(f"🔤 使用本地语言模型路径: {args.lm_dir}")
        #         # 对于FST语言模型，我们只需要记录路径，不需要通过AutoModel加载
        #         server_state.model_lm = {'path': args.lm_dir, 'type': 'fst'}
        #     else:
        #         local_lm_path = get_local_model_path(lm_model_name, root_dir)
        #         logger.info(f"🔍 语言模型检查: {lm_model_name} -> {local_lm_path}")
        #         if local_lm_path:
        #             logger.info(f"🔤 使用本地语言模型: {local_lm_path}")
        #             server_state.model_lm = {'path': local_lm_path, 'type': 'fst'}
        #         else:
        #             logger.info(f"🔤 从远程加载语言模型: {lm_model_name}")
        #             lm_revision = getattr(args, 'lm_revision', 'v1.0.2')
        #             try:
        #                 # 下载FST语言模型
        #                 temp_model = AutoModel(
        #                     model=lm_model_name,
        #                     inference_mode="onnxruntime",
        #                     model_revision=lm_revision,
        #                     cache_dir=args.cache_dir,
        #                     disable_pbar=True,
        #                     disable_log=True,
        #                     device_id=0,
        #                     disable_update=True,
        #                 )
        #                 # 获取下载后的路径
        #                 lm_cache_path = os.path.join(args.cache_dir, lm_model_name.replace('/', '--'))
        #                 server_state.model_lm = {'path': lm_cache_path, 'type': 'fst'}
        #             except Exception as e:
        #                 logger.warning(f"⚠️ 语言模型下载失败: {e}")
        #                 server_state.model_lm = None
        #     logger.info("✅ 语言模型配置完成")
        # else:
        #     logger.info("⚠️ 跳过语言模型加载 (未指定模型)")
        #     server_state.model_lm = None
             
         # 8. 加载翻译模型 (可选)
        if hasattr(args, 'enable_translation') and args.enable_translation:
            if hasattr(args, 'translation_model') and args.translation_model:
                local_translation_path = require_local_model_path(args.translation_model, root_dir, "翻译")
                logger.info(f"🌐 使用本地翻译模型: {local_translation_path}")
                server_state.model_translation = AutoModel(
                    model=local_translation_path,
                    inference_mode="onnxruntime",
                    ngpu=args.ngpu,
                    ncpu=args.ncpu,
                    device=args.device,
                    disable_pbar=True,
                    disable_log=True,
                    disable_update=True,
                    device_id=0,
                )
                logger.info("✅ 翻译模型加载完成")
            else:
                logger.info("⚠️ 跳过翻译模型加载 (未指定模型)")
                server_state.model_translation = None
        else:
            logger.info("⚠️ 跳过翻译模型加载 (功能未启用)")
            server_state.model_translation = None
            
        # 7. 初始化文档分段服务 (可选)
        if hasattr(args, 'enable_segmentation') and args.enable_segmentation:
            try:
                from ..core.document_segmentation_service import init_document_segmentation
                init_document_segmentation(args)
                logger.info("✅ 文档分段服务初始化完成")
                server_state.model_segmentation = True  # 标记为已启用
            except Exception as e:
                logger.warning(f"⚠️ 文档分段服务初始化失败: {e}")
                server_state.model_segmentation = None
        else:
            logger.info("⚠️ 跳过文档分段服务初始化 (功能未启用)")
            server_state.model_segmentation = None
            
        # 9. 加载热词文件 (类似C++服务器的热词处理)
        if hasattr(args, 'hotword') and args.hotword and args.hotword.strip():
            try:
                hotword_path = args.hotword.strip()
                # 处理相对路径
                if not os.path.isabs(hotword_path):
                    hotword_path = os.path.join(root_dir, hotword_path)
                
                if os.path.exists(hotword_path):
                    logger.info(f"📝 加载热词文件: {hotword_path}")
                    server_state.hotword_map = load_hotwords(hotword_path)
                    fst_inc_wts = getattr(args, 'fst_inc_wts', 20)
                    logger.info(f"🎯 热词配置: 文件={hotword_path}, 权重增量={fst_inc_wts}")
                    logger.info(f"📊 加载热词数量: {len(server_state.hotword_map)}")
                else:
                    logger.warning(f"⚠️ 热词文件不存在: {hotword_path}")
                    server_state.hotword_map = {}
            except Exception as e:
                logger.warning(f"⚠️ 热词文件加载失败: {e}")
                server_state.hotword_map = {}
        else:
            logger.info("⚠️ 跳过热词文件加载 (未指定文件)")
            server_state.hotword_map = {}
        
        # 10. 初始化热词管理器 (保持原有功能)
        try:
            from ..speaker.hotword_manager import init_hotword_manager
            hotword_storage_path = getattr(args, 'hotword_storage_path', 'data/hotwords.json')
            init_hotword_manager(hotword_storage_path, args)
            logger.info("✅ 热词管理器初始化完成")
        except Exception as e:
            logger.warning(f"⚠️ 热词管理器初始化失败: {e}")
            
        load_time = time.time() - start_time
        logger.info(f"🎉 所有模型加载完成! 耗时: {load_time:.2f}秒")
        logger.info("✅ 服务器现在支持多客户端并发连接")
        
    except ImportError as e:
        error_msg = f"无法导入FunASR库: {e}"
        logger.error(f"❌ {error_msg}")
        logger.error("请确保已正确安装FunASR: pip install funasr")
        raise ModelLoadError(f"{error_msg}. 请安装funasr库") from e
    except Exception as e:
        error_msg = f"模型加载失败: {e}"
        logger.error(f"❌ {error_msg}")
        logger.error("请检查模型名称、本地 models 目录和设备配置")
        raise ModelLoadError(f"{error_msg}. 请检查配置和本地模型目录") from e
