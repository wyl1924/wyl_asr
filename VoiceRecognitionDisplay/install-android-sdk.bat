@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo Android SDK Auto-Installer for Windows
echo ========================================
echo.

REM Define SDK installation path
set SDK_DIR=%LOCALAPPDATA%\Android\Sdk
set CMDLINE_TOOLS_DIR=%SDK_DIR%\cmdline-tools\latest

echo Installation directory: %SDK_DIR%
echo.

REM Check if SDK already exists
if exist "%SDK_DIR%\platform-tools" (
    echo Android SDK already installed at: %SDK_DIR%
    echo.
    set ANDROID_HOME=%SDK_DIR%
    goto :setup_env
)

echo [1/5] Creating SDK directory...
if not exist "%SDK_DIR%" mkdir "%SDK_DIR%"
if not exist "%SDK_DIR%\cmdline-tools" mkdir "%SDK_DIR%\cmdline-tools"

echo.
echo [2/5] Downloading Android SDK Command-line Tools...
echo This may take a few minutes...
echo.

REM Download URL for Windows
set DOWNLOAD_URL=https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip
set DOWNLOAD_FILE=%TEMP%\cmdline-tools.zip

REM Use PowerShell to download
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%DOWNLOAD_FILE%'}"

if not exist "%DOWNLOAD_FILE%" (
    echo ERROR: Download failed!
    echo Please download manually from: https://developer.android.com/studio#command-tools
    pause
    exit /b 1
)

echo.
echo [3/5] Extracting SDK tools...

REM Extract using PowerShell
powershell -Command "& {Expand-Archive -Path '%DOWNLOAD_FILE%' -DestinationPath '%SDK_DIR%\cmdline-tools' -Force}"

REM Rename cmdline-tools folder to latest
if exist "%SDK_DIR%\cmdline-tools\cmdline-tools" (
    if exist "%CMDLINE_TOOLS_DIR%" rmdir /s /q "%CMDLINE_TOOLS_DIR%"
    move "%SDK_DIR%\cmdline-tools\cmdline-tools" "%CMDLINE_TOOLS_DIR%"
)

REM Clean up download
del "%DOWNLOAD_FILE%"

echo.
echo [4/5] Installing Android SDK components...
echo This will install:
echo   - Android SDK Platform 34 (Android 14)
echo   - Android SDK Build-Tools 34.0.0
echo   - Android SDK Platform-Tools
echo.

REM Set JAVA_HOME if not set (use bundled JDK from .NET)
if not defined JAVA_HOME (
    for /f "tokens=*" %%i in ('where /r "C:\Program Files\dotnet" java.exe 2^>nul') do (
        set "JAVA_PATH=%%i"
        goto :found_java
    )
    :found_java
    if defined JAVA_PATH (
        for %%i in ("!JAVA_PATH!") do set "JAVA_HOME=%%~dpi.."
        echo Using Java from: !JAVA_HOME!
    )
)

REM Accept licenses
echo y | "%CMDLINE_TOOLS_DIR%\bin\sdkmanager.bat" --licenses

REM Install required components
"%CMDLINE_TOOLS_DIR%\bin\sdkmanager.bat" "platform-tools" "platforms;android-34" "build-tools;34.0.0"

if errorlevel 1 (
    echo.
    echo WARNING: SDK component installation had issues.
    echo You may need to run this manually:
    echo   "%CMDLINE_TOOLS_DIR%\bin\sdkmanager.bat" "platform-tools" "platforms;android-34" "build-tools;34.0.0"
    echo.
)

:setup_env
echo.
echo [5/5] Setting up environment variables...

set ANDROID_HOME=%SDK_DIR%
set ANDROID_SDK_ROOT=%SDK_DIR%

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Android SDK installed at: %SDK_DIR%
echo.
echo Environment variables (current session):
echo   ANDROID_HOME=%ANDROID_HOME%
echo   ANDROID_SDK_ROOT=%ANDROID_SDK_ROOT%
echo.
echo To make environment variables permanent, run as Administrator:
echo   setx ANDROID_HOME "%ANDROID_HOME%" /M
echo   setx ANDROID_SDK_ROOT "%ANDROID_SDK_ROOT%" /M
echo.
echo Or add to user environment (no admin needed):
echo   setx ANDROID_HOME "%ANDROID_HOME%"
echo   setx ANDROID_SDK_ROOT "%ANDROID_SDK_ROOT%"
echo.
echo ========================================
echo Next Steps:
echo ========================================
echo 1. Close this window
echo 2. Open a NEW command prompt (to load environment variables)
echo 3. Run: build-android.bat
echo.

pause
