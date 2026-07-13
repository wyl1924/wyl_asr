@echo off
REM 启动FunASR服务器（串口功能默认启用）
REM 使用方法: 双击运行

echo ========================================
echo FunASR 服务器启动
echo ========================================
echo.
echo [信息] 串口功能: 默认启用
echo [信息] 串口号: COM3 (默认)
echo [信息] 波特率: 9600
echo.
echo [提示] 如需禁用串口，请使用: python main.py --disable_serial
echo [提示] 如需更改串口号，请使用: python main.py --serial_port COM5
echo.

python main.py

pause
