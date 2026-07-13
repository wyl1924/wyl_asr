@echo off
setlocal enabledelayedexpansion

REM 完整的混淆构建脚本 (Windows版本)
REM 支持前端Vue.js和后端Python的完整混淆构建

echo === WYL ASR 混淆构建脚本 ===
echo 开始混淆构建...

REM 项目根目录
set PROJECT_ROOT=%~dp0..
cd /d "%PROJECT_ROOT%"

echo 项目根目录: %PROJECT_ROOT%

REM 检查必要的工具
echo 检查构建依赖...

REM 检查Node.js和npm
node --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Node.js，请先安装 Node.js
    pause
    exit /b 1
)

npm --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 npm，请先安装 npm
    pause
    exit /b 1
)

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3
    pause
    exit /b 1
)

REM 检查PyArmor
python -c "import pyarmor" >nul 2>&1
if errorlevel 1 (
    echo 警告: PyArmor未安装，将自动安装...
    python -m pip install pyarmor
    if errorlevel 1 (
        echo 错误: PyArmor安装失败
        pause
        exit /b 1
    )
)

echo 依赖检查完成

REM 清理之前的构建
echo 清理之前的构建...
if exist dist rmdir /s /q dist
mkdir dist
echo 清理完成

REM 构建前端
echo === 构建前端 ===
cd ui

REM 检查package.json是否存在
if not exist package.json (
    echo 错误: 未找到 package.json
    pause
    exit /b 1
)

REM 安装依赖（如果需要）
if not exist node_modules (
    echo 安装前端依赖...
    npm install
    if errorlevel 1 (
        echo 错误: 前端依赖安装失败
        pause
        exit /b 1
    )
) else (
    echo 前端依赖已存在，跳过安装
)

REM 构建生产版本
echo 构建混淆后的前端...
npm run build
if errorlevel 1 (
    echo 错误: 前端构建失败
    pause
    exit /b 1
)

if not exist dist (
    echo 错误: 前端构建失败，未生成 dist 目录
    pause
    exit /b 1
)

echo 前端构建完成

REM 返回项目根目录
cd /d "%PROJECT_ROOT%"

REM 混淆Python代码
echo === 混淆Python代码 ===

if not exist scripts\obfuscate_python.py (
    echo 错误: 未找到混淆脚本 scripts\obfuscate_python.py
    pause
    exit /b 1
)

python scripts\obfuscate_python.py
if errorlevel 1 (
    echo 错误: Python代码混淆失败
    pause
    exit /b 1
)

if not exist dist\obfuscated (
    echo 错误: Python代码混淆失败，未生成混淆目录
    pause
    exit /b 1
)

echo Python代码混淆完成

REM 混淆关键模块
echo === 混淆关键模块 ===

if not exist scripts\obfuscate_modules.py (
    echo 警告: 未找到模块混淆脚本，跳过模块混淆
    goto :skip_modules
)

python scripts\obfuscate_modules.py
if errorlevel 1 (
    echo 警告: 关键模块混淆失败，但继续构建
)

echo 关键模块混淆完成

:skip_modules

REM 创建部署包
echo === 创建部署包 ===
cd dist

REM 创建时间戳
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "TIMESTAMP=%YYYY%%MM%%DD%_%HH%%Min%%Sec%"
set "PACKAGE_NAME=wyl_asr_obfuscated_%TIMESTAMP%"

REM 创建zip包
if exist "%ProgramFiles%\7-Zip\7z.exe" (
    echo 创建 zip 部署包...
    "%ProgramFiles%\7-Zip\7z.exe" a -tzip "%PACKAGE_NAME%.zip" obfuscated\
    if not errorlevel 1 (
        echo 部署包创建完成: dist\%PACKAGE_NAME%.zip
    )
) else (
    echo 警告: 未找到 7-Zip，跳过压缩包创建
    echo 建议安装 7-Zip 或手动压缩 dist\obfuscated 目录
)

cd /d "%PROJECT_ROOT%"

REM 验证构建结果
echo === 验证构建结果 ===

set OBFUSCATED_DIR=dist\obfuscated

REM 检查主要文件
if not exist "%OBFUSCATED_DIR%\main.py" (
    echo 错误: 未找到混淆后的 main.py
    pause
    exit /b 1
)

REM 检查前端文件
if not exist "%OBFUSCATED_DIR%\ui\dist" (
    echo 警告: 未找到前端构建文件
)

REM 检查启动脚本
if not exist "%OBFUSCATED_DIR%\start.bat" (
    echo 警告: 未找到启动脚本
)

echo 构建结果验证完成

REM 显示构建信息
echo.
echo === 构建完成 ===
echo 混淆代码位置: dist\obfuscated\
echo 部署包位置: dist\wyl_asr_obfuscated_*.zip
echo.
echo 使用方法:
echo 1. 解压部署包到目标服务器
echo 2. cd dist\obfuscated\
echo 3. start.bat 或 python main.py
echo.
echo 注意事项:
echo - 混淆后的代码无法直接修改
echo - 请保留原始源码用于开发和调试
echo - 建议在测试环境充分验证后再部署到生产环境
echo.

echo 混淆构建完成！
pause