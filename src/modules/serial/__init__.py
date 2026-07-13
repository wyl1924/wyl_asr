#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""串口通讯模块"""

from .serial_receiver import SerialReceiver
from .serial_manager import (
    SerialManager,
    init_serial_manager,
    get_serial_manager,
    shutdown_serial_manager
)
from .protocol_parser import (
    MultiProtocolParser,
    ProtocolTypeA,
    ProtocolTypeB,
    get_protocol_info
)

__all__ = [
    'SerialReceiver',
    'SerialManager',
    'init_serial_manager',
    'get_serial_manager',
    'shutdown_serial_manager',
    'MultiProtocolParser',
    'ProtocolTypeA',
    'ProtocolTypeB',
    'get_protocol_info'
]
