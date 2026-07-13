#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""串口接收模块 - 用于接收会议系统控制信号

协议说明：
- 波特率：9600
- 数据位：8
- 停止位：1
- 校验位：无
- 通讯方式：RS232

数据格式（16进制）：
数据包格式：FE F7 [开关] [单元号] [设备类型] EF

开关状态：
- 01 = 打开
- 00 = 关闭

设备类型：
- 00 = 代表
- 01 = 主席

示例：
- 1号代表打开：FE F7 01 01 00 EF
- 2号代表打开：FE F7 01 02 00 EF
- 1号主席打开：FE F7 01 01 01 EF
- 1号代表关闭：FE F7 00 01 00 EF
- 1号主席关闭：FE F7 00 01 01 EF
"""

import serial
import threading
import logging
from typing import Optional, Callable, Dict, Any
from queue import Queue
import time

from .protocol_parser import MultiProtocolParser


class SerialReceiver:
    """串口接收器类"""
    
    # 协议A常量
    HEADER_A = 0xFE
    TAIL_A = 0xEF
    
    # 协议B常量
    HEADER_B = 0x01
    TAIL_B = 0x02
    
    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        protocol_type: str = 'auto'
    ):
        """初始化串口接收器
        
        Args:
            port: 串口号，如 'COM1' (Windows) 或 '/dev/ttyUSB0' (Linux)
            baudrate: 波特率，默认9600
            callback: 接收到数据后的回调函数
            protocol_type: 协议类型 ('auto', 'A', 'B')，默认自动识别
        """
        self.port = port
        self.baudrate = baudrate
        self.callback = callback
        self.protocol_type = protocol_type.upper() if protocol_type else 'AUTO'
        self.logger = logging.getLogger(__name__)
        
        # 根据协议类型设置包头包尾
        if self.protocol_type == 'B':
            self.valid_headers = [self.HEADER_B]
            self.valid_tails = [self.TAIL_B]
            self.logger.info(f"🔧 使用协议B: 包头=0x{self.HEADER_B:02X}, 包尾=0x{self.TAIL_B:02X}")
        elif self.protocol_type == 'A':
            self.valid_headers = [self.HEADER_A]
            self.valid_tails = [self.TAIL_A]
            self.logger.info(f"🔧 使用协议A: 包头=0x{self.HEADER_A:02X}, 包尾=0x{self.TAIL_A:02X}")
        else:  # AUTO
            self.valid_headers = [self.HEADER_A, self.HEADER_B]
            self.valid_tails = [self.TAIL_A, self.TAIL_B]
            self.logger.info(f"🔧 使用自动协议识别: 支持协议A和协议B")
        
        # 串口对象
        self.serial_port: Optional[serial.Serial] = None
        
        # 接收线程
        self.receive_thread: Optional[threading.Thread] = None
        self.running = False
        
        # 数据队列
        self.data_queue = Queue()
        
        # 多协议解析器
        self.protocol_parser = MultiProtocolParser()
        
        # 统计信息
        self.stats = {
            'total_received': 0,
            'valid_packets': 0,
            'invalid_packets': 0,
            'last_receive_time': None,
            'protocol_stats': {}  # 各协议的统计
        }
    
    def connect(self) -> bool:
        """连接串口
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 先尝试关闭可能已打开的串口
            try:
                temp_ser = serial.Serial(self.port)
                temp_ser.close()
                self.logger.info(f"🔧 关闭了已存在的串口连接")
            except:
                pass
            
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0,  # 非阻塞模式，立即返回
                rtscts=False,  # 禁用硬件流控
                dsrdtr=True    # 启用DTR/DSR流控
            )
            
            # 验证串口是否真的打开了
            if not self.serial_port.is_open:
                self.logger.error(f"❌ 串口打开失败: {self.port}")
                return False
            
            # 设置 DTR（不设置 RTS）
            self.serial_port.dtr = True
            self.serial_port.rts = False
            
            # 清空缓冲区
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            
            self.logger.info(f"🔧 DTR={self.serial_port.dtr}, RTS={self.serial_port.rts}")
            self.logger.info(f"🔧 DSR/DTR流控: 已启用")
            
            self.logger.info(f"✅ 串口连接成功: {self.port} @ {self.baudrate}bps")
            self.logger.info(f"🔧 串口配置: timeout=0 (非阻塞), dsrdtr=True, hex接收模式")
            self.logger.info(f"🔍 串口对象: {self.serial_port}")
            self.logger.info(f"🔍 串口is_open: {self.serial_port.is_open}")
            
            # 立即测试读取
            test_waiting = self.serial_port.in_waiting
            self.logger.info(f"🔍 连接后立即检测 in_waiting: {test_waiting}")
            
            return True
        except serial.SerialException as e:
            error_msg = str(e).lower()
            self.logger.error(f"❌ 串口连接失败: {e}")
            
            # 提供详细的错误提示
            if "access is denied" in error_msg or "permission denied" in error_msg:
                self.logger.error("🚫 错误原因: 串口访问被拒绝")
                self.logger.info("💡 可能的解决方案:")
                self.logger.info("   1. 关闭所有正在使用该串口的程序（如串口调试助手、Arduino IDE等）")
                self.logger.info("   2. 检查设备管理器中串口是否正常")
                self.logger.info("   3. 尝试以管理员权限运行程序")
                self.logger.info("   4. 重新插拔串口设备")
                self.logger.info("   5. 检查串口号是否正确（Windows: 设备管理器，Linux: ls /dev/tty*）")
            elif "could not open port" in error_msg or "no such file" in error_msg:
                self.logger.error(f"🚫 错误原因: 串口 {self.port} 不存在")
                self.logger.info("💡 可能的解决方案:")
                self.logger.info("   1. 检查串口设备是否已连接")
                self.logger.info("   2. Windows: 在设备管理器中查看正确的COM口号")
                self.logger.info("   3. Linux: 使用 'ls /dev/tty*' 查看可用串口")
                self.logger.info("   4. macOS: 使用 'ls /dev/tty.*' 查看可用串口")
                self.logger.info(f"   5. 使用参数指定正确的串口: --serial_port <串口号>")
            else:
                self.logger.info("💡 常见解决方案:")
                self.logger.info("   1. 确认串口设备已正确连接")
                self.logger.info("   2. 关闭其他占用串口的程序")
                self.logger.info("   3. 检查串口号和波特率是否正确")
            
            return False
        except Exception as e:
            self.logger.error(f"❌ 串口连接异常: {e}")
            self.logger.info("💡 请检查串口配置是否正确")
            return False
    
    def disconnect(self) -> None:
        """断开串口连接"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.logger.info("🔌 串口已断开")
    
    def start(self) -> bool:
        """启动接收线程
        
        Returns:
            bool: 启动是否成功
        """
        if not self.serial_port or not self.serial_port.is_open:
            self.logger.error("❌ 串口未连接，无法启动接收")
            return False
        
        if self.running:
            self.logger.warning("⚠️ 接收线程已在运行")
            return True
        
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        self.logger.info(f"🎧 串口接收线程已启动，正在监听 {self.port}...")
        self.logger.info(f"📋 串口配置: 波特率={self.baudrate}, 数据位=8, 停止位=1, 校验=无")
        return True
    
    def stop(self) -> None:
        """停止接收线程"""
        if not self.running:
            return
        
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=2)
        self.logger.info("🛑 串口接收线程已停止")
    
    def _receive_loop(self) -> None:
        """接收循环（在独立线程中运行）"""
        buffer = bytearray()
        last_log_time = time.time()
        last_debug_time = time.time()
        
        self.logger.info("🔄 串口接收循环开始运行")
        self.logger.info(f"🔍 串口状态: is_open={self.serial_port.is_open if self.serial_port else 'None'}")
        
        while self.running:
            try:
                # 每30秒记录一次心跳日志
                current_time = time.time()
                if current_time - last_log_time > 30:
                    self.logger.info(f"💓 串口接收心跳: 已接收 {self.stats['total_received']} 个数据包")
                    last_log_time = current_time
                
                # 每5秒记录一次调试信息（仅在没有接收到数据时）
                if current_time - last_debug_time > 5 and self.stats['total_received'] == 0:
                    waiting = self.serial_port.in_waiting if self.serial_port else 0
                    self.logger.info(f"🔍 调试: in_waiting={waiting}, 串口状态={self.serial_port.is_open if self.serial_port else 'None'}")
                    last_debug_time = current_time
                
                # 强制读取模式：不依赖in_waiting，直接尝试读取
                # 因为某些串口驱动的in_waiting可能不可靠
                try:
                    # 尝试读取最多100字节（非阻塞，timeout=0会立即返回）
                    data = self.serial_port.read(100)
                    
                    if data:
                        # 收到数据
                        self.logger.info(f"📥 接收到原始数据 ({len(data)} 字节): {data.hex().upper()}")
                        buffer.extend(data)
                        
                        # 处理缓冲区中的数据包
                        self._process_buffer(buffer)
                    else:
                        # 没有数据，短暂休眠
                        time.sleep(0.01)
                        
                except Exception as read_err:
                    self.logger.error(f"❌ 读取数据时出错: {read_err}")
                    time.sleep(0.01)
                    
            except serial.SerialException as e:
                self.logger.error(f"❌ 串口读取错误: {e}")
                break
            except Exception as e:
                self.logger.error(f"❌ 接收循环异常: {e}")
                break
    
    def _process_buffer(self, buffer: bytearray) -> None:
        """处理接收缓冲区
        
        Args:
            buffer: 接收缓冲区
        """
        self.logger.debug(f"🔍 处理缓冲区: 当前长度={len(buffer)} 字节, 内容={buffer.hex().upper()}")
        
        while len(buffer) >= 6:  # 最小数据包长度
            # 查找包头
            if buffer[0] not in self.valid_headers:
                discarded_byte = buffer.pop(0)
                expected = ', '.join([f"0x{h:02X}" for h in self.valid_headers])
                self.logger.warning(f"⚠️ 丢弃非包头字节: 0x{discarded_byte:02X} (期望: {expected})")
                continue
            
            # 检查是否有完整的数据包
            if len(buffer) < 6:
                self.logger.debug(f"📦 缓冲区数据不足6字节，等待更多数据...")
                break
            
            # 验证包尾（根据包头确定期望的包尾）
            expected_tail = None
            if buffer[0] == self.HEADER_A:
                expected_tail = self.TAIL_A
            elif buffer[0] == self.HEADER_B:
                expected_tail = self.TAIL_B
            
            # 验证数据包
            if buffer[5] == expected_tail:
                # 提取完整数据包
                packet = buffer[:6]
                del buffer[:6]
                
                self.logger.info(f"✅ 发现完整数据包: {packet.hex().upper()}")
                
                # 解析数据包
                self._parse_packet(packet)
                
                # 更新统计
                self.stats['total_received'] += 1
                self.stats['last_receive_time'] = time.time()
            else:
                # 无效数据包，丢弃包头
                invalid_tail = buffer[5]
                self.logger.warning(
                    f"⚠️ 包尾验证失败: 0x{invalid_tail:02X} (期望: 0x{expected_tail:02X}), "
                    f"数据包={buffer[:6].hex().upper()}, 丢弃包头"
                )
                buffer.pop(0)
                self.stats['invalid_packets'] += 1
    
    def _parse_packet(self, packet: bytes) -> None:
        """解析数据包（支持多协议）
        
        Args:
            packet: 数据包字节
        """
        try:
            # 使用多协议解析器
            parsed_data = self.protocol_parser.parse(packet)
            
            if parsed_data is None:
                self.logger.warning(f"⚠️ 无法解析数据包: {packet.hex().upper()}")
                self.stats['invalid_packets'] += 1
                return
            
            # 添加时间戳
            parsed_data['timestamp'] = time.time()
            
            # 获取协议类型
            protocol_type = parsed_data.get('protocol_type', 'Unknown')
            
            # 记录日志
            self.logger.info(
                f"📡 接收到信号 [协议{protocol_type}]: "
                f"{parsed_data['unit_number']}号{parsed_data['device_type_str']} - "
                f"{parsed_data['status']} [{packet.hex().upper()}]"
            )
            
            # 更新统计
            self.stats['valid_packets'] += 1
            
            # 更新协议统计
            if protocol_type not in self.stats['protocol_stats']:
                self.stats['protocol_stats'][protocol_type] = 0
            self.stats['protocol_stats'][protocol_type] += 1
            
            # 放入队列
            self.data_queue.put(parsed_data)
            
            # 调用回调函数
            if self.callback:
                try:
                    self.callback(parsed_data)
                except Exception as e:
                    self.logger.error(f"❌ 回调函数执行失败: {e}")
                    
        except Exception as e:
            self.logger.error(f"❌ 数据包解析失败: {e}")
            self.stats['invalid_packets'] += 1
    
    def get_data(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """从队列获取解析后的数据
        
        Args:
            timeout: 超时时间（秒），None表示不阻塞
            
        Returns:
            解析后的数据字典，如果队列为空则返回None
        """
        try:
            if timeout is None:
                return self.data_queue.get_nowait()
            else:
                return self.data_queue.get(timeout=timeout)
        except:
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        return self.stats.copy()
    
    def clear_stats(self) -> None:
        """清除统计信息"""
        self.stats = {
            'total_received': 0,
            'valid_packets': 0,
            'invalid_packets': 0,
            'last_receive_time': None
        }


def example_callback(data: Dict[str, Any]) -> None:
    """示例回调函数
    
    Args:
        data: 解析后的数据
    """
    print(f"收到数据: {data['unit_number']}号{data['device_type_str']} - {data['status']}")


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建串口接收器
    # Windows: 'COM1', 'COM2', etc.
    # Linux: '/dev/ttyUSB0', '/dev/ttyS0', etc.
    receiver = SerialReceiver(
        port='COM1',  # 根据实际情况修改
        baudrate=9600,
        callback=example_callback
    )
    
    # 连接串口
    if receiver.connect():
        # 启动接收
        if receiver.start():
            try:
                print("串口接收器运行中，按 Ctrl+C 停止...")
                while True:
                    time.sleep(1)
                    # 打印统计信息
                    stats = receiver.get_stats()
                    print(f"统计: 总接收={stats['total_received']}, "
                          f"有效={stats['valid_packets']}, "
                          f"无效={stats['invalid_packets']}")
            except KeyboardInterrupt:
                print("\n停止接收...")
            finally:
                receiver.stop()
                receiver.disconnect()
    else:
        print("串口连接失败")
