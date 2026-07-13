#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""串口协议解析器 - 支持多种会议系统协议"""

from typing import Dict, Any, Optional
from enum import Enum


class ProtocolType(Enum):
    """协议类型枚举"""
    TYPE_A = "type_a"  # FE F7 [开关] [单元号] [设备类型] EF
    TYPE_B = "type_b"  # 01 03 [开关] [设备类型] [ID号] 02


class ProtocolParser:
    """协议解析器基类"""
    
    def parse(self, packet: bytes) -> Optional[Dict[str, Any]]:
        """解析数据包
        
        Args:
            packet: 数据包字节
            
        Returns:
            解析后的数据字典，如果解析失败返回None
        """
        raise NotImplementedError


class ProtocolTypeA(ProtocolParser):
    """协议类型A: FE F7 [开关] [单元号] [设备类型] EF
    
    字段说明：
    - FE: 包头
    - F7: 命令
    - [开关]: 01=打开, 00=关闭
    - [单元号]: 01-0F (1-15号)
    - [设备类型]: 00=代表, 01=主席
    - EF: 包尾
    
    示例：
    - FE F7 01 01 00 EF → 1号代表打开
    - FE F7 00 01 01 EF → 1号主席关闭
    """
    
    HEADER = 0xFE
    COMMAND = 0xF7
    TAIL = 0xEF
    PACKET_LENGTH = 6
    
    def validate(self, packet: bytes) -> bool:
        """验证数据包"""
        if len(packet) != self.PACKET_LENGTH:
            return False
        if packet[0] != self.HEADER or packet[5] != self.TAIL:
            return False
        if packet[1] != self.COMMAND:
            return False
        return True
    
    def parse(self, packet: bytes) -> Optional[Dict[str, Any]]:
        """解析协议A数据包"""
        if not self.validate(packet):
            return None
        
        open_flag = packet[2]      # 01=打开, 00=关闭
        unit_number = packet[3]    # 单元号
        device_type = packet[4]    # 00=代表, 01=主席
        
        return {
            'protocol_type': 'A',
            'unit_number': unit_number,
            'device_type': device_type,
            'device_type_str': '主席' if device_type == 0x01 else '代表',
            'status': '打开' if open_flag == 0x01 else '关闭',
            'is_open': open_flag == 0x01,
            'raw_packet': packet.hex()
        }


class ProtocolTypeB(ProtocolParser):
    """协议类型B: 01 03 [开关] [设备类型] [ID号] 02
    
    字段说明：
    - 01: 包头
    - 03: 命令
    - [开关]: 20=打开, 21=关闭
    - [设备类型]: 20=代表, 21=主席
    - [ID号]: 21-36 (十六进制) → 单元号 33-54（保留原始值）
    - 02: 包尾
    
    单元号映射规则：
    - 0x21 → 单元33（通道1）
    - 0x22 → 单元34（通道2）
    - ...
    - 0x36 → 单元54（通道22）
    
    示例：
    - 01 03 20 20 21 02 → 33号代表打开
    - 01 03 21 20 21 02 → 33号代表关闭
    - 01 03 20 21 22 02 → 34号主席打开
    """
    
    HEADER = 0x01
    COMMAND = 0x03
    TAIL = 0x02
    PACKET_LENGTH = 6
    
    # 开关状态
    STATUS_OPEN = 0x20
    STATUS_CLOSE = 0x21
    
    # 设备类型
    DEVICE_DELEGATE = 0x20
    DEVICE_CHAIRMAN = 0x21
    
    def validate(self, packet: bytes) -> bool:
        """验证数据包"""
        if len(packet) != self.PACKET_LENGTH:
            return False
        if packet[0] != self.HEADER or packet[5] != self.TAIL:
            return False
        if packet[1] != self.COMMAND:
            return False
        return True
    
    def parse(self, packet: bytes) -> Optional[Dict[str, Any]]:
        """解析协议B数据包"""
        if not self.validate(packet):
            return None
        
        open_flag = packet[2]      # 20=打开, 21=关闭
        device_type = packet[3]    # 20=代表, 21=主席
        id_number = packet[4]      # ID号（十六进制）
        
        # 协议B的绑定配置和UI都使用原始ID值作为单元号：
        # 0x21 -> 33, 0x22 -> 34, ... 0x36 -> 54
        unit_number = id_number
        channel_number = id_number - 0x20
        
        return {
            'protocol_type': 'B',
            'unit_number': unit_number,
            'channel_number': channel_number,
            'device_type': device_type,
            'device_type_str': '主席' if device_type == self.DEVICE_CHAIRMAN else '代表',
            'status': '打开' if open_flag == self.STATUS_OPEN else '关闭',
            'is_open': open_flag == self.STATUS_OPEN,
            'raw_packet': packet.hex()
        }


class MultiProtocolParser:
    """多协议解析器 - 自动识别并解析不同协议"""
    
    def __init__(self):
        """初始化多协议解析器"""
        self.parsers = [
            ProtocolTypeA(),
            ProtocolTypeB()
        ]
    
    def parse(self, packet: bytes) -> Optional[Dict[str, Any]]:
        """尝试使用所有协议解析数据包
        
        Args:
            packet: 数据包字节
            
        Returns:
            解析后的数据字典，如果所有协议都无法解析则返回None
        """
        for parser in self.parsers:
            result = parser.parse(packet)
            if result is not None:
                return result
        return None
    
    def identify_protocol(self, packet: bytes) -> Optional[str]:
        """识别数据包使用的协议类型
        
        Args:
            packet: 数据包字节
            
        Returns:
            协议类型字符串，如果无法识别返回None
        """
        if len(packet) < 2:
            return None
        
        # 根据包头识别协议
        if packet[0] == 0xFE and len(packet) >= 6 and packet[5] == 0xEF:
            return 'A'
        elif packet[0] == 0x01 and len(packet) >= 6 and packet[5] == 0x02:
            return 'B'
        
        return None


def get_protocol_info() -> Dict[str, Dict[str, Any]]:
    """获取所有支持的协议信息
    
    Returns:
        协议信息字典
    """
    return {
        'A': {
            'name': '协议A',
            'description': 'FE F7 [开关] [单元号] [设备类型] EF',
            'packet_length': 6,
            'header': 'FE',
            'tail': 'EF',
            'examples': [
                {'packet': 'FE F7 01 01 00 EF', 'description': '1号代表打开'},
                {'packet': 'FE F7 00 01 01 EF', 'description': '1号主席关闭'}
            ]
        },
        'B': {
            'name': '协议B',
            'description': '01 03 [开关] [设备类型] [ID号] 02',
            'packet_length': 6,
            'header': '01',
            'tail': '02',
            'examples': [
                {'packet': '01 03 20 20 21 02', 'description': '33号代表打开'},
                {'packet': '01 03 21 21 21 02', 'description': '33号主席关闭'}
            ]
        }
    }


if __name__ == "__main__":
    """测试协议解析器"""
    import binascii
    
    parser = MultiProtocolParser()
    
    # 测试协议A
    print("="*60)
    print("测试协议A:")
    print("="*60)
    
    test_packets_a = [
        bytes.fromhex('FEF7010100EF'),  # 1号代表打开
        bytes.fromhex('FEF7000101EF'),  # 1号主席关闭
        bytes.fromhex('FEF7010201EF'),  # 2号主席打开
    ]
    
    for packet in test_packets_a:
        result = parser.parse(packet)
        if result:
            print(f"数据包: {packet.hex().upper()}")
            print(f"  协议: {result['protocol_type']}")
            print(f"  单元号: {result['unit_number']}")
            print(f"  设备类型: {result['device_type_str']}")
            print(f"  状态: {result['status']}")
            print()
    
    # 测试协议B
    print("="*60)
    print("测试协议B:")
    print("="*60)
    
    test_packets_b = [
        bytes.fromhex('01032020'+'21'+'02'),  # 33号代表打开
        bytes.fromhex('01032120'+'22'+'02'),  # 34号代表关闭
        bytes.fromhex('01032021'+'23'+'02'),  # 35号主席打开
    ]
    
    for packet in test_packets_b:
        result = parser.parse(packet)
        if result:
            print(f"数据包: {packet.hex().upper()}")
            print(f"  协议: {result['protocol_type']}")
            print(f"  单元号: {result['unit_number']} (0x{result['unit_number']:02X})")
            print(f"  设备类型: {result['device_type_str']}")
            print(f"  状态: {result['status']}")
            print()
    
    # 打印协议信息
    print("="*60)
    print("支持的协议:")
    print("="*60)
    
    protocols = get_protocol_info()
    for proto_id, info in protocols.items():
        print(f"\n{info['name']} (类型{proto_id}):")
        print(f"  格式: {info['description']}")
        print(f"  包长: {info['packet_length']}字节")
        print(f"  包头: {info['header']}, 包尾: {info['tail']}")
        print(f"  示例:")
        for example in info['examples']:
            print(f"    {example['packet']} → {example['description']}")
