#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频VAD（静音消除/降噪）过滤器模块
"""

import logging
from typing import Optional

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    logging.warning("webrtcvad未安装，音频VAD过滤功能将不可用")

class VadFilter:
    """基于 WebRTC VAD 的静音过滤类"""
    
    def __init__(self, 
                 sample_rate: int = 16000, 
                 vad_mode: int = 2,
                 logger: Optional[logging.Logger] = None):
        """
        初始化VAD过滤器
        
        Args:
            sample_rate: 采样率，目前我们固定使用16000Hz
            vad_mode: 过滤强度 (0-3，0最不激进，3最激进降噪)
            logger: 日志记录器
        """
        self.sample_rate = sample_rate
        self.logger = logger or logging.getLogger(__name__)
        self.is_available = VAD_AVAILABLE
        
        if self.is_available:
            self.vad = webrtcvad.Vad(vad_mode)
            # 计算30ms帧的字节长 (16000Hz * 0.03s * 2 bytes = 960 bytes)
            self.frame_duration_ms = 30
            self.frame_bytes = int(self.sample_rate * (self.frame_duration_ms / 1000) * 2)
            self.logger.info(f"✅ VAD过滤器已初始化 (Mode: {vad_mode}, FrameSize: {self.frame_bytes} bytes)")
        else:
            self.logger.warning("❌ webrtcvad 未安装，VAD过滤器被禁用")
            self.vad = None

    def process_chunk(self, pcm_data: bytes) -> bytes:
        """
        处理传入的音频PCM块，将非人声帧静音填充。
        
        Args:
            pcm_data: 原始 PCM_16LE 音频数据块
        Returns:
            过滤后的 PCM 数据块 (长度结构与输入保持完全一致)
        """
        if not self.is_available or not self.vad:
            return pcm_data

        filtered_data = bytearray()
        
        # 将传入的数据划分为 30ms 的小帧
        # 注意: 剩余不足一个完整 30ms 帧的数据块直接透传（或丢弃，我们这里选择透传保留对齐）
        offset = 0
        total_length = len(pcm_data)
        
        while offset + self.frame_bytes <= total_length:
            frame = pcm_data[offset:offset + self.frame_bytes]
            
            try:
                # 检查该帧是否包含语音
                is_speech = self.vad.is_speech(frame, self.sample_rate)
            except Exception as e:
                # 异常情况下直接视为有语音以防丢字
                self.logger.debug(f"VAD检测异常: {e}")
                is_speech = True

            if is_speech:
                # 有人声，保留原始声音
                filtered_data.extend(frame)
            else:
                # 没人声（纯噪音），将整帧数据替换为绝对静音数据 (全为 \x00)
                filtered_data.extend(b'\x00' * self.frame_bytes)

            offset += self.frame_bytes

        # 把尾部不够一帧长度的零碎数据原样拼回去
        if offset < total_length:
            filtered_data.extend(pcm_data[offset:])

        return bytes(filtered_data)
