@echo off
chcp 65001 >nul
echo ========================================
echo 查找 Android SDK 位置
echo ========================================
echo.

echo 正在检查常见位置...
echo.

REM 检查环境变量
if defined ANDROID_HOME (
    echo [环境变量] ANDROID_HOME = %ANDROID_HOME%
    if exist "%ANDROID_HOME%\platform-tools" (
        echo   ✅ 有效的 SDK 路径
    ) else (
        echo   ❌ 路径无效或不完整
    )
    echo.
)

if defined ANDROID_SDK_ROOT (
    echo [环境变量] ANDROID_SDK_ROOT = %ANDROID_SDK_ROOT%
    if exist "%ANDROID_SDK_ROOT%\platform-tools" (
        echo   ✅ 有效的 SDK 路径
    ) else (
        echo   ❌ 路径无效或不完整
    )
    echo.
)

REM 检查常见安装位置
echo 检查常见安装位置:
echo.

set FOUND_COUNT=0

if exist "C:\Program Files (x86)\Android\android-sdk\platform-tools" (
    echo [找到] C:\Program Files ^(x86^)\Android\android-sdk
    set FOUND_COUNT=1
    set SDK_PATH=C:\Program Files (x86)\Android\android-sdk
)

if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools" (
    echo [找到] %LOCALAPPDATA%\Android\Sdk
    set FOUND_COUNT=1
    set SDK_PATH=%LOCALAPPDATA%\Android\Sdk
)

if exist "%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools" (
    echo [找到] %USERPROFILE%\AppData\Local\Android\Sdk
    set FOUND_COUNT=1
    set SDK_PATH=%USERPROFILE%\AppData\Local\Android\Sdk
)

if exist "C:\Android\android-sdk\platform-tools" (
    echo [找到] C:\Android\android-sdk
    set FOUND_COUNT=1
    set SDK_PATH=C:\Android\android-sdk
)

if exist "%ProgramFiles%\Android\android-sdk\platform-tools" (
    echo [找到] %ProgramFiles%\Android\android-sdk
    set FOUND_COUNT=1
    set SDK_PATH=%ProgramFiles%\Android\android-sdk
)

echo.

if %FOUND_COUNT%==0 (
    echo ❌ 未在常见位置找到 Android SDK
    echo.
    echo 请手动查找包含以下文件夹的目录:
    echo   - platform-tools
    echo   - platforms
    echo   - build-tools
    echo.
    echo 然后运行:
    echo   setx ANDROID_HOME "你的SDK路径"
    echo   setx ANDROID_SDK_ROOT "你的SDK路径"
    echo.
) else (
    echo ========================================
    echo 找到 Android SDK!
    echo ========================================
    echo.
    echo SDK 路径: %SDK_PATH%
    echo.
    echo 设置环境变量 (当前会话):
    set ANDROID_HOME=%SDK_PATH%
    set ANDROID_SDK_ROOT=%SDK_PATH%
    echo   ANDROID_HOME=%ANDROID_HOME%
    echo   ANDROID_SDK_ROOT=%ANDROID_SDK_ROOT%
    echo.
    echo 要永久设置，请运行:
    echo   setx ANDROID_HOME "%SDK_PATH%"
    echo   setx ANDROID_SDK_ROOT "%SDK_PATH%"
    echo.
    echo 或者直接运行 (会自动设置):
    echo   set-android-env.bat
    echo.
)

pause
