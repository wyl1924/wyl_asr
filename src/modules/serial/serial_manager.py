#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""串口管理器 - 集成串口接收到ASR系统"""

import logging
import yaml
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from .serial_receiver import SerialReceiver


class SerialManager:
    """串口管理器类 - 负责串口接收与ASR系统的集成"""
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        logger: Optional[logging.Logger] = None
    ):
        """初始化串口管理器
        
        Args:
            config_path: 配置文件路径
            port: 串口号（如果指定则覆盖配置文件）
            baudrate: 波特率（如果指定则覆盖配置文件）
            logger: 日志记录器
        """
        self.logger = logger or logging.getLogger(__name__)
        self.config = {}
        self.receiver: Optional[SerialReceiver] = None
        self.callbacks = []
        self.unit_speaker_mapping = {}
        
        # 最后打开的单元信息
        self.last_opened_unit = None
        self.last_opened_speaker = None
        self.last_opened_time = None
        
        # 说话人识别模式配置
        self.speaker_mode = 'voiceprint'  # 默认使用声纹识别
        self.serial_timeout = 30  # 串口信号超时时间
        
        # 加载配置
        if config_path:
            self._load_config(config_path)
        
        # 命令行参数覆盖配置文件
        if port:
            self.config.setdefault('serial', {})['port'] = port
        if baudrate:
            self.config.setdefault('serial', {})['baudrate'] = baudrate
    
    def _load_config(self, config_path: str) -> None:
        """加载配置文件
        
        Args:
            config_path: 配置文件路径
        """
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                self.logger.warning(f"⚠️ 配置文件不存在: {config_path}")
                return
            
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
            
            self.logger.info(f"✅ 串口配置文件加载成功: {config_path}")
            
            # 提取说话人识别模式配置
            if 'speaker_identification' in self.config:
                speaker_config = self.config['speaker_identification']
                self.speaker_mode = speaker_config.get('mode', 'voiceprint')
                self.serial_timeout = speaker_config.get('serial_timeout', 30)
                
                # 加载单元号映射，确保键是整数
                raw_mapping = speaker_config.get('unit_speaker_mapping', {})
                self.unit_speaker_mapping = {int(k): v for k, v in raw_mapping.items()}
                
                self.logger.info(f"🎯 说话人识别模式: {self.speaker_mode}")
                self.logger.info(f"⏱️ 串口超时时间: {self.serial_timeout}秒")
                self.logger.info(f"📋 加载单元号映射: {len(self.unit_speaker_mapping)} 个单元")
                if self.unit_speaker_mapping:
                    for unit, name in self.unit_speaker_mapping.items():
                        self.logger.info(f"  - 单元{unit} -> {name}")
            
            # 兼容旧配置格式
            elif 'callback' in self.config and 'unit_speaker_mapping' in self.config['callback']:
                raw_mapping = self.config['callback']['unit_speaker_mapping']
                self.unit_speaker_mapping = {int(k): v for k, v in raw_mapping.items()}
                self.logger.info(f"📋 加载单元号映射: {len(self.unit_speaker_mapping)} 个单元")
                
        except Exception as e:
            self.logger.error(f"❌ 配置文件加载失败: {e}")
    
    def initialize(self) -> bool:
        """初始化串口接收器
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 检查是否启用
            serial_config = self.config.get('serial', {})
            if not serial_config.get('enabled', False):
                self.logger.info("ℹ️ 串口接收功能未启用")
                return False
            
            # 获取串口配置
            port = serial_config.get('port', 'COM1')
            baudrate = serial_config.get('baudrate', 9600)
            protocol_type = serial_config.get('protocol_type', 'auto')
            
            self.logger.info(f"🔌 准备初始化串口: {port} @ {baudrate}bps")
            self.logger.info(f"📋 协议类型: {protocol_type}")
            
            # 创建串口接收器
            self.receiver = SerialReceiver(
                port=port,
                baudrate=baudrate,
                callback=self._handle_serial_data,
                protocol_type=protocol_type
            )
            
            # 连接串口
            if not self.receiver.connect():
                self.logger.error("❌ 串口连接失败")
                # 列出可用的串口
                self._list_available_ports()
                return False
            
            # 启动接收
            if not self.receiver.start():
                self.logger.error("❌ 串口接收启动失败")
                return False
            
            self.logger.info(f"✅ 串口接收器初始化成功: {port} @ {baudrate}bps")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 串口接收器初始化失败: {e}")
            return False
    
    def shutdown(self) -> None:
        """关闭串口接收器"""
        if self.receiver:
            try:
                self.receiver.stop()
                self.receiver.disconnect()
                self.logger.info("✅ 串口接收器已关闭")
            except Exception as e:
                self.logger.error(f"❌ 串口接收器关闭失败: {e}")
    
    def register_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """注册数据回调函数
        
        Args:
            callback: 回调函数，接收解析后的数据字典
        """
        self.callbacks.append(callback)
        self.logger.info(f"✅ 注册串口数据回调函数: {callback.__name__}")
    
    def _handle_serial_data(self, data: Dict[str, Any]) -> None:
        """处理串口数据
        
        Args:
            data: 解析后的串口数据
        """
        try:
            self.logger.info(f"📨 串口管理器接收到数据: {data}")
            
            # 添加说话人信息
            unit_number = data.get('unit_number')
            self.logger.info(f"🔍 [DEBUG] unit_number: {unit_number}, type: {type(unit_number)}")
            self.logger.info(f"🔍 [DEBUG] unit_speaker_mapping keys: {list(self.unit_speaker_mapping.keys())}")
            
            if unit_number in self.unit_speaker_mapping:
                data['speaker_name'] = self.unit_speaker_mapping[unit_number]
                self.logger.info(f"🔍 单元{unit_number}映射到说话人: {data['speaker_name']}")
            else:
                data['speaker_name'] = f"单元{unit_number}"
                self.logger.warning(f"⚠️ 单元{unit_number}未找到映射，使用默认名称")
            
            # 如果是打开状态，更新最后打开的单元
            is_open = data.get('is_open', False)
            self.logger.info(f"🔍 [DEBUG] is_open: {is_open}")
            
            if is_open:
                import time
                old_speaker = self.last_opened_speaker
                self.last_opened_unit = unit_number
                self.last_opened_speaker = data['speaker_name']
                self.last_opened_time = time.time()
                
                self.logger.info(f"🔍 [DEBUG] 已更新 last_opened_speaker: {self.last_opened_speaker}")
                self.logger.info(f"🔍 [DEBUG] 已更新 last_opened_unit: {self.last_opened_unit}")
                
                if old_speaker:
                    self.logger.info(
                        f"🔄 说话人切换: {old_speaker} -> {data['speaker_name']} (单元{unit_number})"
                    )
                else:
                    self.logger.info(
                        f"🎤 设置当前说话人: {data['speaker_name']} (单元{unit_number})"
                    )
            else:
                self.logger.info(f"🔇 单元{unit_number}关闭: {data['speaker_name']}")
            
            # 记录日志
            self.logger.info(
                f"📡 串口数据处理完成: {data['speaker_name']} ({data['device_type_str']}) - {data['status']}"
            )
            
            # 调用所有注册的回调函数
            if self.callbacks:
                self.logger.info(f"🔔 调用 {len(self.callbacks)} 个回调函数")
            for callback in self.callbacks:
                try:
                    callback(data)
                    self.logger.debug(f"✅ 回调函数执行成功: {callback.__name__}")
                except Exception as e:
                    self.logger.error(f"❌ 回调函数执行失败 ({callback.__name__}): {e}")
                    
        except Exception as e:
            import traceback
            self.logger.error(f"❌ 串口数据处理失败: {e}")
            self.logger.error(f"🐛 异常堆栈:\n{traceback.format_exc()}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        if self.receiver:
            return self.receiver.get_stats()
        return {}
    
    def get_speaker_name(self, unit_number: int) -> str:
        """根据单元号获取说话人名称
        
        Args:
            unit_number: 单元号
            
        Returns:
            说话人名称
        """
        return self.unit_speaker_mapping.get(unit_number, f"单元{unit_number}")
    
    def get_current_speaker(self) -> Optional[str]:
        """获取当前说话人（最后一个打开的单元）
        
        Returns:
            说话人名称，如果没有则返回None
        """
        import time
        
        # 检查是否有最后打开的单元
        if self.last_opened_speaker is None:
            return None
        
        # 检查串口信号是否超时（仅在hybrid模式下检查）
        if self.speaker_mode == 'hybrid' and self.last_opened_time:
            elapsed = time.time() - self.last_opened_time
            if elapsed > self.serial_timeout:
                self.logger.debug(f"串口信号已超时 ({elapsed:.1f}秒 > {self.serial_timeout}秒)")
                return None
        
        return self.last_opened_speaker
    
    def get_speaker_mode(self) -> str:
        """获取说话人识别模式
        
        Returns:
            说话人识别模式 ('voiceprint', 'serial', 'hybrid')
        """
        return self.speaker_mode
    
    def clear_current_speaker(self) -> None:
        """清除当前说话人信息"""
        self.last_opened_unit = None
        self.last_opened_speaker = None
        self.last_opened_time = None
        self.logger.info("🔄 已清除当前说话人信息")
    
    def _list_available_ports(self) -> None:
        """列出所有可用的串口"""
        try:
            import serial.tools.list_ports
            
            self.logger.info("🔍 正在扫描可用串口...")
            ports = list(serial.tools.list_ports.comports())
            
            if not ports:
                self.logger.warning("⚠️ 未找到任何串口设备")
                self.logger.info("💡 请检查:")
                self.logger.info("   1. 串口设备是否已连接")
                self.logger.info("   2. 驱动程序是否已安装")
                self.logger.info("   3. 设备是否被系统识别")
                return
            
            self.logger.info(f"✅ 找到 {len(ports)} 个串口设备:")
            
            available_ports = []
            for i, port in enumerate(ports, 1):
                self.logger.info(f"   [{i}] {port.device}")
                self.logger.info(f"       描述: {port.description}")
                
                # 测试串口是否可用
                try:
                    import serial
                    test_serial = serial.Serial(port.device, 9600, timeout=0.5)
                    test_serial.close()
                    self.logger.info(f"       状态: ✅ 可用")
                    available_ports.append(port.device)
                except serial.SerialException as e:
                    error_msg = str(e).lower()
                    if "access is denied" in error_msg or "permission denied" in error_msg:
                        self.logger.info(f"       状态: 🚫 被占用")
                    else:
                        self.logger.info(f"       状态: ❌ 无法访问")
                except Exception:
                    self.logger.info(f"       状态: ❌ 错误")
            
            if available_ports:
                self.logger.info(f"💡 推荐使用: {available_ports[0]}")
                self.logger.info(f"💡 启动命令: python main.py --serial_port {available_ports[0]}")
            else:
                self.logger.warning("⚠️ 所有串口都被占用或无法访问")
                self.logger.info("💡 请关闭其他占用串口的程序后重试")
                self.logger.info("💡 或使用以下命令禁用串口: python main.py --disable_serial")
                
        except ImportError:
            self.logger.warning("⚠️ 无法列出串口设备（pyserial未安装或版本过低）")
        except Exception as e:
            self.logger.error(f"❌ 列出串口时出错: {e}")


# 全局串口管理器实例
_serial_manager: Optional[SerialManager] = None


def init_serial_manager(
    config_path: Optional[str] = None,
    port: Optional[str] = None,
    baudrate: Optional[int] = None,
    logger: Optional[logging.Logger] = None
) -> Optional[SerialManager]:
    """初始化全局串口管理器
    
    Args:
        config_path: 配置文件路径
        port: 串口号
        baudrate: 波特率
        logger: 日志记录器
        
    Returns:
        SerialManager实例，如果初始化失败则返回None
    """
    global _serial_manager
    
    try:
        _serial_manager = SerialManager(
            config_path=config_path,
            port=port,
            baudrate=baudrate,
            logger=logger
        )
        
        if _serial_manager.initialize():
            return _serial_manager
        else:
            _serial_manager = None
            return None
            
    except Exception as e:
        if logger:
            logger.error(f"❌ 串口管理器初始化失败: {e}")
        _serial_manager = None
        return None


def get_serial_manager() -> Optional[SerialManager]:
    """获取全局串口管理器实例
    
    Returns:
        SerialManager实例，如果未初始化则返回None
    """
    return _serial_manager


def shutdown_serial_manager() -> None:
    """关闭全局串口管理器"""
    global _serial_manager
    
    if _serial_manager:
        _serial_manager.shutdown()
        _serial_manager = None
