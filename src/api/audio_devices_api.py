#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频设备管理API
==============

提供获取服务器端音频设备列表的API接口。
"""

import logging
from typing import Dict, List, Any

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("PyAudio未安装，服务器音频采集功能将不可用")


def get_audio_devices() -> Dict[str, Any]:
    """
    获取服务器端的音频输入设备列表

    Returns:
        Dict包含:
        - devices: 设备列表
        - default_device: 默认设备ID
        - success: 是否成功
        - message: 错误消息（如果有）
    """
    if not PYAUDIO_AVAILABLE:
        return {
            "success": False,
            "message": "PyAudio未安装，无法获取音频设备列表",
            "devices": [],
            "default_device": None
        }

    try:
        p = pyaudio.PyAudio()
        devices = []
        default_device_index = None

        # 获取默认输入设备
        try:
            default_info = p.get_default_input_device_info()
            default_device_index = default_info['index']
        except OSError:
            logging.warning("无法获取默认音频输入设备")

        # 虚拟设备关键词列表（用于识别虚拟音频设备）
        virtual_device_keywords = [
            'virtual', 'loopback', 'aggregate', 'multi-output',
            'iflyrec', 'eshow', 'oray', 'screenflow', 'obs',
            'soundflower', 'blackhole', 'vb-audio'
        ]

        # 遍历所有设备
        device_count = p.get_device_count()
        physical_devices = []  # 物理设备列表

        for i in range(device_count):
            try:
                device_info = p.get_device_info_by_index(i)

                # 只返回输入设备（有输入通道的设备）
                if device_info['maxInputChannels'] > 0:
                    device_name = device_info['name'].lower()

                    # 检查是否为虚拟设备
                    is_virtual = any(keyword in device_name for keyword in virtual_device_keywords)

                    device_data = {
                        "id": str(i),
                        "index": i,
                        "name": device_info['name'],
                        "channels": device_info['maxInputChannels'],
                        "sample_rate": int(device_info['defaultSampleRate']),
                        "is_default": i == default_device_index,
                        "is_virtual": is_virtual
                    }

                    devices.append(device_data)

                    # 收集物理设备
                    if not is_virtual:
                        physical_devices.append(i)

            except Exception as e:
                logging.warning(f"获取设备 {i} 信息失败: {e}")
                continue

        # 智能选择默认设备：优先选择物理麦克风
        if default_device_index is not None:
            try:
                default_device_name = p.get_device_info_by_index(default_device_index)['name'].lower()
                is_default_virtual = any(keyword in default_device_name for keyword in virtual_device_keywords)

                if is_default_virtual and physical_devices:
                    # 如果系统默认设备是虚拟设备，选择第一个物理设备
                    old_default = default_device_index
                    default_device_index = physical_devices[0]
                    logging.info(f"检测到系统默认设备 {old_default} 为虚拟设备，自动选择物理麦克风: 设备 {default_device_index}")
                    # 更新 is_default 标记
                    for device in devices:
                        device['is_default'] = (device['index'] == default_device_index)
            except Exception as e:
                logging.warning(f"检查默认设备类型失败: {e}")
        elif physical_devices:
            # 如果未设置默认设备，选择第一个物理设备
            default_device_index = physical_devices[0]
            logging.info(f"未检测到系统默认设备，自动选择物理麦克风: 设备 {default_device_index}")
            for device in devices:
                device['is_default'] = (device['index'] == default_device_index)

        p.terminate()

        if not devices:
            return {
                "success": False,
                "message": "未检测到可用的音频输入设备",
                "devices": [],
                "default_device": None
            }

        return {
            "success": True,
            "message": "成功获取音频设备列表",
            "devices": devices,
            "default_device": str(default_device_index) if default_device_index is not None else None
        }

    except Exception as e:
        logging.error(f"获取音频设备列表失败: {e}")
        return {
            "success": False,
            "message": f"获取音频设备列表失败: {str(e)}",
            "devices": [],
            "default_device": None
        }


def is_pyaudio_available() -> bool:
    """检查PyAudio是否可用"""
    return PYAUDIO_AVAILABLE

