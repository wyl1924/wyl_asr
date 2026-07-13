#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""串口诊断工具 - 列出所有可用的串口并测试连接"""

import sys
import platform

def list_serial_ports():
    """列出所有可用的串口"""
    print("=" * 60)
    print("🔍 串口诊断工具")
    print("=" * 60)
    print()
    
    try:
        import serial.tools.list_ports
        
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            print("❌ 未找到任何串口设备")
            print()
            print("💡 可能的原因:")
            print("   1. 串口设备未连接")
            print("   2. 驱动程序未安装")
            print("   3. 设备未被系统识别")
            print()
            return []
        
        print(f"✅ 找到 {len(ports)} 个串口设备:")
        print()
        
        available_ports = []
        
        for i, port in enumerate(ports, 1):
            print(f"【串口 {i}】")
            print(f"   端口号: {port.device}")
            print(f"   描述: {port.description}")
            print(f"   硬件ID: {port.hwid}")
            
            # 尝试打开串口测试
            try:
                import serial
                test_serial = serial.Serial(port.device, 9600, timeout=0.5)
                test_serial.close()
                print(f"   状态: ✅ 可用")
                available_ports.append(port.device)
            except serial.SerialException as e:
                error_msg = str(e).lower()
                if "access is denied" in error_msg or "permission denied" in error_msg:
                    print(f"   状态: 🚫 拒绝访问（可能被其他程序占用）")
                elif "could not open port" in error_msg:
                    print(f"   状态: ❌ 无法打开")
                else:
                    print(f"   状态: ⚠️ 错误 - {e}")
            except Exception as e:
                print(f"   状态: ❌ 异常 - {e}")
            
            print()
        
        return available_ports
        
    except ImportError:
        print("❌ 错误: 未安装 pyserial 库")
        print("💡 请运行: pip install pyserial")
        return []

def show_recommendations(available_ports):
    """显示推荐配置"""
    print("=" * 60)
    print("📋 推荐配置")
    print("=" * 60)
    print()
    
    if available_ports:
        recommended_port = available_ports[0]
        print(f"✅ 推荐使用串口: {recommended_port}")
        print()
        print("🚀 启动命令:")
        print(f"   python main.py --serial_port {recommended_port}")
        print()
        
        if len(available_ports) > 1:
            print("📝 其他可用串口:")
            for port in available_ports[1:]:
                print(f"   python main.py --serial_port {port}")
            print()
    else:
        print("⚠️ 没有可用的串口")
        print()
        print("💡 建议:")
        print("   1. 检查串口设备是否已连接")
        print("   2. 关闭所有占用串口的程序")
        print("   3. 重新插拔串口设备")
        print("   4. 检查设备驱动是否正常")
        print()
        print("🔧 如果不需要串口功能，可以禁用:")
        print("   python main.py --disable_serial")
        print()

def check_occupied_ports():
    """检查可能占用串口的程序"""
    print("=" * 60)
    print("🔍 检查可能占用串口的程序")
    print("=" * 60)
    print()
    
    system = platform.system()
    
    if system == "Windows":
        print("💡 Windows 系统检查方法:")
        print("   1. 打开任务管理器 (Ctrl+Shift+Esc)")
        print("   2. 查找以下可能占用串口的程序:")
        print("      - 串口调试助手")
        print("      - Arduino IDE")
        print("      - PuTTY")
        print("      - Tera Term")
        print("      - 其他串口通信软件")
        print()
        print("   3. 在设备管理器中查看串口状态:")
        print("      - 按 Win+X，选择'设备管理器'")
        print("      - 展开'端口(COM和LPT)'")
        print("      - 查看串口设备状态")
        print()
        
    elif system == "Linux":
        print("💡 Linux 系统检查方法:")
        print("   1. 查看串口设备:")
        print("      ls -l /dev/tty*")
        print()
        print("   2. 检查占用串口的进程:")
        print("      lsof /dev/ttyUSB0  # 替换为你的串口号")
        print()
        print("   3. 添加用户到 dialout 组:")
        print("      sudo usermod -a -G dialout $USER")
        print("      # 需要重新登录生效")
        print()
        
    elif system == "Darwin":  # macOS
        print("💡 macOS 系统检查方法:")
        print("   1. 查看串口设备:")
        print("      ls -l /dev/tty.*")
        print()
        print("   2. 检查占用串口的进程:")
        print("      lsof /dev/tty.usbserial-*")
        print()
    
    print()

def main():
    """主函数"""
    print()
    
    # 列出所有串口
    available_ports = list_serial_ports()
    
    # 显示推荐配置
    show_recommendations(available_ports)
    
    # 显示检查方法
    check_occupied_ports()
    
    print("=" * 60)
    print("✅ 诊断完成")
    print("=" * 60)
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
