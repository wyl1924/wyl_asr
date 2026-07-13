@echo off
chcp 65001 >nul
echo ========================================
echo Android SDK Setup for Windows
echo ========================================
echo.

REM Check common Android SDK locations
set SDK_FOUND=0
set ANDROID_SDK_ROOT=

echo Checking for Android SDK...
echo.

REM Location 1: Visual Studio
if exist "C:\Program Files (x86)\Android\android-sdk" (
    set ANDROID_SDK_ROOT=C:\Program Files ^(x86^)\Android\android-sdk
    set SDK_FOUND=1
    echo [Found] Visual Studio SDK: %ANDROID_SDK_ROOT%
)

REM Location 2: User AppData
if exist "%LOCALAPPDATA%\Android\Sdk" (
    set ANDROID_SDK_ROOT=%LOCALAPPDATA%\Android\Sdk
    set SDK_FOUND=1
    echo [Found] User SDK: %ANDROID_SDK_ROOT%
)

REM Location 3: Android Studio default
if exist "%USERPROFILE%\AppData\Local\Android\Sdk" (
    set ANDROID_SDK_ROOT=%USERPROFILE%\AppData\Local\Android\Sdk
    set SDK_FOUND=1
    echo [Found] Android Studio SDK: %ANDROID_SDK_ROOT%
)

echo.

if %SDK_FOUND%==0 (
    echo ========================================
    echo ERROR: Android SDK not found!
    echo ========================================
    echo.
    echo Please install Android SDK using one of these methods:
    echo.
    echo Method 1: Install via Visual Studio 2022
    echo   1. Open Visual Studio Installer
    echo   2. Modify your installation
    echo   3. Select ".NET Multi-platform App UI development"
    echo   4. Install
    echo.
    echo Method 2: Install Android Studio
    echo   1. Download from: https://developer.android.com/studio
    echo   2. Install Android Studio
    echo   3. Open SDK Manager and install Android SDK
    echo.
    echo Method 3: Install via dotnet CLI
    echo   Run: dotnet workload install android
    echo.
    pause
    exit /b 1
)

echo ========================================
echo Setting up environment...
echo ========================================
echo.

REM Set environment variables for current session
set ANDROID_HOME=%ANDROID_SDK_ROOT%
set ANDROID_SDK_ROOT=%ANDROID_SDK_ROOT%

echo ANDROID_HOME=%ANDROID_HOME%
echo ANDROID_SDK_ROOT=%ANDROID_SDK_ROOT%

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Environment variables set for current session.
echo.
echo To make this permanent, run as Administrator:
echo   setx ANDROID_HOME "%ANDROID_HOME%" /M
echo   setx ANDROID_SDK_ROOT "%ANDROID_SDK_ROOT%" /M
echo.
echo Now you can run: build-android.bat
echo.

pause
