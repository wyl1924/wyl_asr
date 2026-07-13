@echo off
chcp 65001 >nul
echo ========================================
echo 设置 Android SDK 环境变量
echo ========================================
echo.

REM 自动检测 SDK 路径
set SDK_PATH=

if exist "C:\Program Files (x86)\Android\android-sdk\platform-tools" (
    set SDK_PATH=C:\Program Files (x86)\Android\android-sdk
)

if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools" (
    set SDK_PATH=%LOCALAPPDATA%\Android\Sdk
)

if exist "%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools" (
    set SDK_PATH=%USERPROFILE%\AppData\Local\Android\Sdk
)

if exist "C:\Android\android-sdk\platform-tools" (
    set SDK_PATH=C:\Android\android-sdk
)

if not defined SDK_PATH (
    echo ❌ 未找到 Android SDK
    echo.
    echo 请手动指定 SDK 路径:
    set /p SDK_PATH="输入 Android SDK 完整路径: "
)

if not exist "%SDK_PATH%\platform-tools" (
    echo.
    echo ❌ 错误: 指定的路径不是有效的 Android SDK
    echo 路径: %SDK_PATH%
    echo.
    pause
    exit /b 1
)

echo.
echo 找到 SDK: %SDK_PATH%
echo.
echo 正在设置环境变量...
echo.

REM 设置用户级环境变量 (不需要管理员权限)
setx ANDROID_HOME "%SDK_PATH%"
setx ANDROID_SDK_ROOT "%SDK_PATH%"

echo.
echo ========================================
echo 设置完成!
echo ========================================
echo.
echo 环境变量已设置:
echo   ANDROID_HOME=%SDK_PATH%
echo   ANDROID_SDK_ROOT=%SDK_PATH%
echo.
echo ⚠️ 重要: 请关闭当前命令提示符，打开新的命令提示符
echo 然后运行: build-android.bat
echo.

pause
