#!/bin/bash

echo "========================================"
echo "Android APK Build Script"
echo "========================================"
echo ""

# Auto-detect Android SDK
SDK_FOUND=0

# Check environment variable first
if [ -n "$ANDROID_HOME" ] && [ -d "$ANDROID_HOME/platform-tools" ]; then
    echo "Using SDK from environment: $ANDROID_HOME"
    SDK_FOUND=1
fi

# Check common macOS locations
if [ $SDK_FOUND -eq 0 ]; then
    if [ -d "$HOME/Library/Android/sdk/platform-tools" ]; then
        export ANDROID_HOME="$HOME/Library/Android/sdk"
        SDK_FOUND=1
        echo "Found SDK: $ANDROID_HOME"
    fi
fi

# Check .NET bundled Android SDK (macOS)
if [ $SDK_FOUND -eq 0 ]; then
    for sdk_path in /usr/local/share/dotnet/packs/Microsoft.Android.Sdk.Darwin/*/tools; do
        if [ -d "$sdk_path" ]; then
            export ANDROID_HOME="$sdk_path"
            SDK_FOUND=1
            echo "Found .NET Android SDK: $sdk_path"
            break
        fi
    done
fi

# Check common Linux locations
if [ $SDK_FOUND -eq 0 ]; then
    if [ -d "$HOME/Android/Sdk/platform-tools" ]; then
        export ANDROID_HOME="$HOME/Android/Sdk"
        SDK_FOUND=1
        echo "Found SDK: $ANDROID_HOME"
    fi
fi

if [ $SDK_FOUND -eq 0 ]; then
    echo "========================================"
    echo "ERROR: Android SDK not found!"
    echo "========================================"
    echo ""
    echo "Please install Android SDK or set ANDROID_HOME:"
    echo "  export ANDROID_HOME=/path/to/android/sdk"
    echo ""
    echo "Add to ~/.bashrc or ~/.zshrc to make permanent"
    echo ""
    exit 1
fi

echo "Using Android SDK: $ANDROID_HOME"
echo ""

cd VoiceRecognitionDisplay.Android

echo "[1/4] Cleaning project..."
dotnet clean

echo ""
echo "[2/4] Restoring dependencies..."
dotnet restore

echo ""
echo "[3/4] Building Release version..."
dotnet build -c Release -f net8.0-android34.0 -p:AndroidSdkDirectory="$ANDROID_HOME"

echo ""
echo "[4/4] Publishing APK..."
dotnet publish -c Release -f net8.0-android34.0 -p:AndroidPackageFormat=apk -p:AndroidSdkDirectory="$ANDROID_HOME"

echo ""
echo "========================================"
echo "Build Complete!"
echo "========================================"
echo ""
echo "APK Location:"
find bin/Release/net8.0-android34.0 -name "*.apk" 2>/dev/null || echo "No APK found - check errors above"
echo ""
