@echo off
chcp 65001 >nul
echo ========================================
echo Android APK Build Script
echo ========================================
echo.

REM Auto-detect Android SDK
set SDK_FOUND=0

REM Check environment variable first
if defined ANDROID_HOME (
    if exist "%ANDROID_HOME%\platform-tools" (
        echo Using SDK from environment: %ANDROID_HOME%
        set SDK_FOUND=1
        goto :sdk_found
    )
)

REM Check .NET bundled Android SDK (most common)
for /d %%i in ("C:\Program Files\dotnet\packs\Microsoft.Android.Sdk.Windows\*") do (
    if exist "%%i\tools" (
        set ANDROID_HOME=%%i\tools
        set SDK_FOUND=1
        echo Found .NET Android SDK: %%i\tools
        goto :sdk_found
    )
)

REM Check other common locations
if exist "C:\Program Files (x86)\Android\android-sdk\platform-tools" (
    set ANDROID_HOME=C:\Program Files ^(x86^)\Android\android-sdk
    set SDK_FOUND=1
    echo Found SDK: %ANDROID_HOME%
    goto :sdk_found
)

if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools" (
    set ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk
    set SDK_FOUND=1
    echo Found SDK: %ANDROID_HOME%
    goto :sdk_found
)

if exist "%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools" (
    set ANDROID_HOME=%USERPROFILE%\AppData\Local\Android\Sdk
    set SDK_FOUND=1
    echo Found SDK: %ANDROID_HOME%
    goto :sdk_found
)

:sdk_found

if %SDK_FOUND%==0 (
    echo ========================================
    echo ERROR: Android SDK not found!
    echo ========================================
    echo.
    echo Please set ANDROID_HOME manually:
    echo   setx ANDROID_HOME "C:\Path\To\Your\Android\Sdk"
    echo.
    echo Then restart command prompt and run again.
    echo.
    pause
    exit /b 1
)

echo Using Android SDK: %ANDROID_HOME%
echo.

cd VoiceRecognitionDisplay.Android

echo [1/4] Cleaning project...
dotnet clean

echo.
echo [2/4] Restoring dependencies...
dotnet restore

echo.
echo [3/4] Building Release version...
dotnet build -c Release -f net8.0-android34.0 -p:AndroidSdkDirectory="%ANDROID_HOME%"

echo.
echo [4/4] Publishing APK...
dotnet publish -c Release -f net8.0-android34.0 -p:AndroidPackageFormat=apk -p:AndroidSdkDirectory="%ANDROID_HOME%"

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo APK Location:
dir /b /s bin\Release\net8.0-android34.0\*.apk 2>nul
if errorlevel 1 echo No APK found - check errors above
echo.

pause
