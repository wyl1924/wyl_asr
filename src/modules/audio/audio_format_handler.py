#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音频格式处理模块。

解决音频格式识别和转换问题，确保音频数据能被正确处理。
"""

import os
import tempfile
import logging
import json
import shutil
import subprocess
import re
import numpy as np
from typing import Union, Dict, Optional, Tuple
import base64

try:
    import librosa
    import soundfile as sf
    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False
    logging.warning("librosa 或 soundfile 未安装，音频格式处理功能受限")

# 配置日志
logger = logging.getLogger(__name__)


class AudioFormatError(Exception):
    """音频格式处理相关异常。"""
    pass


def check_audio_file(audio_path: str) -> Dict:
    """检查音频文件的基本信息"""
    try:
        if not os.path.exists(audio_path):
            return {"valid": False, "error": f"文件不存在: {audio_path}"}

        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            return {"valid": False, "error": "文件大小为0"}

        # 检查文件扩展名
        ext = os.path.splitext(audio_path)[1].lower()
        supported_formats = [
            '.wav', '.mp3', '.flac', '.m4a', '.aac', '.ogg', '.webm',
            '.mp4', '.mov', '.mkv', '.avi', '.wmv', '.m4v', '.amr',
            '.opus', '.wma'
        ]
        if ext not in supported_formats:
            return {"valid": False, "error": f"不支持的音频格式: {ext}"}

        return {
            "valid": True,
            "size": file_size,
            "format": ext,
            "path": audio_path
        }
    except Exception as e:
        return {"valid": False, "error": f"检查文件时出错: {str(e)}"}


def validate_audio_data(audio_data: bytes) -> Dict:
    """验证音频数据的有效性"""
    try:
        if not audio_data or len(audio_data) == 0:
            return {"valid": False, "error": "音频数据为空"}
        
        # 检查是否是有效的音频数据头
        # WAV文件头检查
        if audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:12]:
            return {"valid": True, "format": "wav", "size": len(audio_data)}
        
        # MP3文件头检查
        if audio_data.startswith(b'ID3') or audio_data.startswith(b'\xff\xfb'):
            return {"valid": True, "format": "mp3", "size": len(audio_data)}
        
        # WebM文件头检查
        if audio_data.startswith(b'\x1a\x45\xdf\xa3'):
            return {"valid": True, "format": "webm", "size": len(audio_data)}
        
        # 其他格式的通用检查
        return {"valid": True, "format": "unknown", "size": len(audio_data)}
        
    except Exception as e:
        return {"valid": False, "error": f"验证音频数据时出错: {str(e)}"}


def convert_audio_to_wav(audio_input: Union[str, bytes], 
                        target_sr: int = 16000,
                        target_channels: int = 1) -> str:
    """将音频转换为标准WAV格式
    
    Args:
        audio_input: 音频文件路径或音频数据
        target_sr: 目标采样率
        target_channels: 目标声道数
        
    Returns:
        转换后的WAV文件路径
    """
    if not AUDIO_LIBS_AVAILABLE:
        raise AudioFormatError("librosa 或 soundfile 未安装，无法进行音频格式转换")
    
    try:
        # 创建临时文件
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_wav_path = temp_wav.name
        temp_wav.close()
        
        if isinstance(audio_input, str):
            # 文件路径输入
            logger.info(f"加载音频文件: {audio_input}")
            audio_data, sr = librosa.load(audio_input, sr=target_sr, mono=(target_channels==1))
        else:
            # 字节数据输入
            logger.info("处理音频字节数据")
            
            # 先保存为临时文件
            temp_input = tempfile.NamedTemporaryFile(delete=False)
            temp_input.write(audio_input)
            temp_input.close()
            
            try:
                # 尝试加载音频数据
                audio_data, sr = librosa.load(temp_input.name, sr=target_sr, mono=(target_channels==1))
            finally:
                # 清理临时输入文件
                if os.path.exists(temp_input.name):
                    os.unlink(temp_input.name)
        
        # 保存为WAV格式
        sf.write(temp_wav_path, audio_data, target_sr)
        
        logger.info(f"音频转换完成: {temp_wav_path}, 采样率: {target_sr}, 声道数: {target_channels}")
        return temp_wav_path
        
    except Exception as e:
        logger.error(f"音频格式转换失败: {str(e)}")
        raise AudioFormatError(f"音频格式转换失败: {str(e)}")


def _media_binary(name: str) -> Optional[str]:
    """返回 ffmpeg/ffprobe 可执行文件路径。"""
    env_key = name.upper()
    configured = os.getenv(env_key) or os.getenv(f"WYL_ASR_{env_key}")
    if configured and os.path.exists(configured):
        return configured
    project_binary = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools", "bin", name)
    )
    if os.path.exists(project_binary):
        return project_binary
    return shutil.which(name)


def _fallback_probe_media_info_with_ffmpeg(media_path: str) -> Dict:
    """没有 ffprobe 时，从 ffmpeg 输入探测日志里读取基础媒体信息。"""
    fallback = {
        "duration": 0.0,
        "format": os.path.splitext(media_path)[1].lower().lstrip("."),
        "size": os.path.getsize(media_path) if os.path.exists(media_path) else None,
    }
    ffmpeg = _media_binary("ffmpeg")
    if not ffmpeg:
        return fallback

    try:
        completed = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", media_path],
            check=False,
            capture_output=True,
            text=True,
        )
        output = "\n".join(part for part in [completed.stderr, completed.stdout] if part)
        duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        if duration_match:
            hours, minutes, seconds = duration_match.groups()
            fallback["duration"] = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

        format_match = re.search(r"Input #0,\s*([^,]+(?:,[^,]+)*)\s*, from", output)
        if format_match:
            fallback["format"] = format_match.group(1).strip()

        audio_match = re.search(r"Audio:\s*([^,\n]+)(?:,\s*(\d+)\s*Hz)?(?:,\s*([^,\n]+))?", output)
        if audio_match:
            codec, sample_rate, channel_desc = audio_match.groups()
            fallback["codec"] = codec.split(" ", 1)[0].strip()
            fallback["sample_rate"] = int(sample_rate) if sample_rate else None
            channel_desc = (channel_desc or "").strip().lower()
            if channel_desc == "mono":
                fallback["channels"] = 1
            elif channel_desc == "stereo":
                fallback["channels"] = 2
            else:
                channels_match = re.search(r"(\d+)\s*channels?", channel_desc)
                fallback["channels"] = int(channels_match.group(1)) if channels_match else None
        return fallback
    except Exception as e:
        logger.warning(f"ffmpeg 读取媒体信息异常: {e}")
        return fallback


def probe_media_info(media_path: str) -> Dict:
    """使用 ffprobe 读取媒体时长、容器和音频流信息。"""
    ffprobe = _media_binary("ffprobe")
    if not ffprobe:
        return _fallback_probe_media_info_with_ffmpeg(media_path)

    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration,format_name,size:stream=codec_type,codec_name,sample_rate,channels",
                "-of", "json",
                media_path,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            logger.warning(f"ffprobe 读取媒体信息失败: {completed.stderr.strip()}")
            return _fallback_probe_media_info_with_ffmpeg(media_path)

        payload = json.loads(completed.stdout or "{}")
        fmt = payload.get("format") or {}
        audio_stream = next(
            (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"),
            {},
        )
        try:
            duration = float(fmt.get("duration") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0

        return {
            "duration": duration,
            "format": fmt.get("format_name") or os.path.splitext(media_path)[1].lower().lstrip("."),
            "codec": audio_stream.get("codec_name"),
            "sample_rate": int(audio_stream.get("sample_rate") or 0) or None,
            "channels": int(audio_stream.get("channels") or 0) or None,
            "size": int(fmt.get("size") or os.path.getsize(media_path)),
        }
    except Exception as e:
        logger.warning(f"ffprobe 读取媒体信息异常: {e}")
        return _fallback_probe_media_info_with_ffmpeg(media_path)


def convert_media_to_wav(
    media_input: Union[str, bytes],
    target_sr: int = 16000,
    target_channels: int = 1,
) -> str:
    """将音频或视频容器抽取并转为标准 WAV。

    优先使用 ffmpeg，兼容 mp4/mov/webm/opus/amr/wma 等容器；没有 ffmpeg
    时回退到现有 librosa 转换。
    """
    ffmpeg = _media_binary("ffmpeg")
    if not ffmpeg:
        return convert_audio_to_wav(media_input, target_sr=target_sr, target_channels=target_channels)

    temp_input_path = None
    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav_path = temp_wav.name
    temp_wav.close()

    try:
        if isinstance(media_input, str):
            source_path = media_input
        else:
            temp_input = tempfile.NamedTemporaryFile(delete=False)
            temp_input.write(media_input)
            temp_input.close()
            temp_input_path = temp_input.name
            source_path = temp_input_path

        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", source_path,
                "-vn",
                "-ar", str(target_sr),
                "-ac", str(target_channels),
                "-f", "wav",
                temp_wav_path,
            ],
            check=True,
        )
        logger.info(f"媒体转WAV完成: {temp_wav_path}, 采样率: {target_sr}, 声道数: {target_channels}")
        return temp_wav_path
    except Exception as e:
        if os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)
        logger.warning(f"ffmpeg 媒体转WAV失败，尝试回退音频库: {e}")
        return convert_audio_to_wav(media_input, target_sr=target_sr, target_channels=target_channels)
    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            os.unlink(temp_input_path)


def extract_media_segment_to_wav(
    media_path: str,
    start_ms: int,
    end_ms: int,
    target_sr: int = 16000,
    target_channels: int = 1,
) -> str:
    """从媒体文件中抽取指定时间片段为标准 WAV。"""
    if start_ms is None or end_ms is None or end_ms <= start_ms:
        raise AudioFormatError("无效的音频片段时间范围")

    ffmpeg = _media_binary("ffmpeg")
    if not ffmpeg:
        raise AudioFormatError("ffmpeg 不可用，无法按时间片段抽取媒体")

    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav_path = temp_wav.name
    temp_wav.close()

    try:
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-ss", f"{max(0, int(start_ms)) / 1000:.3f}",
                "-i", media_path,
                "-t", f"{(int(end_ms) - int(start_ms)) / 1000:.3f}",
                "-vn",
                "-ar", str(target_sr),
                "-ac", str(target_channels),
                "-f", "wav",
                temp_wav_path,
            ],
            check=True,
        )
        return temp_wav_path
    except Exception as e:
        if os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)
        raise AudioFormatError(f"抽取媒体片段失败: {e}")


def process_base64_audio(base64_audio: str, 
                        expected_format: str = "wav",
                        target_sr: int = 16000) -> str:
    """处理base64编码的音频数据
    
    Args:
        base64_audio: base64编码的音频数据
        expected_format: 期望的音频格式
        target_sr: 目标采样率
        
    Returns:
        处理后的WAV文件路径
    """
    try:
        # 解码base64数据
        logger.info("解码base64音频数据")
        audio_bytes = base64.b64decode(base64_audio)
        
        # 验证音频数据
        validation = validate_audio_data(audio_bytes)
        if not validation["valid"]:
            raise AudioFormatError(f"音频数据验证失败: {validation['error']}")
        
        logger.info(f"音频数据验证通过: {validation}")
        
        # 转换为标准WAV格式
        wav_path = convert_audio_to_wav(audio_bytes, target_sr=target_sr)
        
        return wav_path
        
    except Exception as e:
        logger.error(f"处理base64音频数据失败: {str(e)}")
        raise AudioFormatError(f"处理base64音频数据失败: {str(e)}")


def create_pcm_wav_file(pcm_data: bytes, 
                       sample_rate: int = 16000,
                       channels: int = 1,
                       sample_width: int = 2) -> str:
    """从PCM数据创建WAV文件
    
    Args:
        pcm_data: PCM音频数据
        sample_rate: 采样率
        channels: 声道数
        sample_width: 样本宽度（字节）
        
    Returns:
        创建的WAV文件路径
    """
    try:
        # 创建临时WAV文件
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_wav_path = temp_wav.name
        temp_wav.close()
        
        # 将PCM数据转换为numpy数组
        if sample_width == 2:
            # 16位PCM
            audio_data = np.frombuffer(pcm_data, dtype=np.int16)
        elif sample_width == 1:
            # 8位PCM
            audio_data = np.frombuffer(pcm_data, dtype=np.uint8)
            audio_data = (audio_data.astype(np.float32) - 128) / 128.0
        else:
            raise AudioFormatError(f"不支持的样本宽度: {sample_width}")
        
        # 如果是立体声，转换为单声道
        if channels == 2 and len(audio_data) % 2 == 0:
            audio_data = audio_data.reshape(-1, 2).mean(axis=1)
        
        # 标准化到[-1, 1]范围
        if sample_width == 2:
            audio_data = audio_data.astype(np.float32) / 32768.0
        
        # 保存为WAV文件
        sf.write(temp_wav_path, audio_data, sample_rate)
        
        logger.info(f"PCM转WAV完成: {temp_wav_path}")
        return temp_wav_path
        
    except Exception as e:
        logger.error(f"PCM转WAV失败: {str(e)}")
        raise AudioFormatError(f"PCM转WAV失败: {str(e)}")


def cleanup_temp_file(file_path: str) -> None:
    """清理临时文件"""
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
            logger.debug(f"清理临时文件: {file_path}")
    except Exception as e:
        logger.warning(f"清理临时文件失败: {e}")


# 全局状态
_audio_format_handler_initialized = False


def init_audio_format_handler():
    """初始化音频格式处理器"""
    global _audio_format_handler_initialized
    
    if _audio_format_handler_initialized:
        return
    
    if not AUDIO_LIBS_AVAILABLE:
        logger.warning("音频处理库未安装，建议安装: pip install librosa soundfile")
    else:
        logger.info("音频格式处理器初始化完成")
    
    _audio_format_handler_initialized = True


def get_audio_format_handler():
    """获取音频格式处理器状态"""
    if not _audio_format_handler_initialized:
        init_audio_format_handler()
    
    return {
        "initialized": _audio_format_handler_initialized,
        "libraries_available": AUDIO_LIBS_AVAILABLE
    }
