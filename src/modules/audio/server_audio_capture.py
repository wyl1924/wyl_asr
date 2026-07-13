#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务器音频采集模块
================

提供从服务器本地音频设备采集音频的功能。
"""

import logging
import asyncio
import time
from typing import Optional, Callable

from .vad_filter import VadFilter

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("PyAudio未安装，服务器音频采集功能将不可用")


class ServerAudioCapture:
    """服务器音频采集类"""
    
    def __init__(self, 
                 device_index: int,
                 sample_rate: int = 16000,
                 channels: int = 1,
                 chunk_size: int = 960,
                 enable_vad: bool = True,
                 vad_mode: int = 2,
                 logger: Optional[logging.Logger] = None):
        """
        初始化服务器音频采集
        
        Args:
            device_index: 音频设备索引
            sample_rate: 采样率 (Hz)
            channels: 声道数
            chunk_size: 每次读取的采样点数
            enable_vad: 是否启用VAD静音消除/降噪
            vad_mode: VAD灵敏度模式 (0-3)
            logger: 日志记录器
        """
        if not PYAUDIO_AVAILABLE:
            raise RuntimeError("PyAudio未安装，无法使用服务器音频采集功能")
        
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.logger = logger or logging.getLogger(__name__)
        
        self.pyaudio_instance = None
        self.stream = None
        self.is_capturing = False
        self.capture_task = None
        
        # 初始化 VAD 过滤器
        self.vad_filter = VadFilter(sample_rate=sample_rate, vad_mode=vad_mode, logger=self.logger) if enable_vad else None
        
    def start(self, audio_callback: Callable[[bytes], None]):
        """
        开始音频采集
        
        Args:
            audio_callback: 音频数据回调函数，接收PCM格式的音频数据
        """
        if not PYAUDIO_AVAILABLE:
            raise RuntimeError("PyAudio未安装")
        
        if self.is_capturing:
            self.logger.warning("音频采集已经在运行")
            return
        
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            
            # 获取设备信息
            device_info = self.pyaudio_instance.get_device_info_by_index(self.device_index)
            self.logger.info(f"🎤 打开音频设备: {device_info['name']}")
            self.logger.info(f"📊 采样率: {self.sample_rate}Hz, 声道数: {self.channels}, 块大小: {self.chunk_size}")
            
            # 打开音频流
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=None  # 使用阻塞模式
            )
            
            self.is_capturing = True
            self.logger.info("✅ 服务器音频采集已开始")
            
            # 创建异步采集任务
            self.capture_task = asyncio.create_task(
                self._capture_loop(audio_callback)
            )
            
        except Exception as e:
            self.logger.error(f"❌ 启动音频采集失败: {e}")
            self.cleanup()
            raise
    
    async def _capture_loop(self, audio_callback: Callable[[bytes], None]):
        """
        音频采集循环（异步）
        
        Args:
            audio_callback: 音频数据回调函数
        """
        try:
            while self.is_capturing and self.stream:
                # 在单独的线程中读取音频数据，避免阻塞事件循环
                audio_data = await asyncio.to_thread(
                    self.stream.read,
                    self.chunk_size,
                    exception_on_overflow=False
                )
                
                if audio_data and self.is_capturing:
                    # 进行 VAD 静音消除/降噪处理 (如果开启)
                    if self.vad_filter:
                        audio_data = self.vad_filter.process_chunk(audio_data)
                        
                    # 调用回调函数处理音频数据
                    audio_callback(audio_data)
                    
        except Exception as e:
            if self.is_capturing:  # 只在非主动停止时记录错误
                self.logger.error(f"❌ 音频采集循环错误: {e}")
        finally:
            self.logger.info("音频采集循环已结束")
    
    def stop(self):
        """停止音频采集"""
        if not self.is_capturing:
            return
        
        self.logger.info("🛑 停止服务器音频采集")
        self.is_capturing = False
        
        # 等待采集任务结束
        if self.capture_task:
            self.capture_task.cancel()
            self.capture_task = None
        
        self.cleanup()
        self.logger.info("✅ 服务器音频采集已停止")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
                
        except Exception as e:
            self.logger.error(f"清理资源时出错: {e}")
    
    def __del__(self):
        """析构函数"""
        self.cleanup()


def is_server_audio_capture_available() -> bool:
    """检查服务器音频采集功能是否可用"""
    return PYAUDIO_AVAILABLE

