@echo off
REM 启动FunASR服务器并启用串口功能
REM 使用方法: 双击运行或在命令行中执行

echo ========================================
echo FunASR 服务器启动脚本 (串口功能已启用)
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

echo [信息] 正在启动服务器...
echo [信息] 串口功能: 已启用
echo [信息] 串口号: COM3 (可通过 --serial_port 参数修改)
echo [信息] 波特率: 9600
echo.

REM 启动服务器，启用串口功能
python main.py --enable_serial --serial_port COM3 --serial_baudrate 9600

pause
