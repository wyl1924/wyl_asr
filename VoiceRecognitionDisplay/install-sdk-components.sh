#!/bin/bash

echo "========================================"
echo "安装 Android SDK 组件"
echo "========================================"
echo ""

if [ -z "$ANDROID_HOME" ]; then
    export ANDROID_HOME=$HOME/Library/Android/sdk
fi

echo "SDK 路径: $ANDROID_HOME"
echo ""

SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"

if [ ! -f "$SDKMANAGER" ]; then
    echo "❌ 找不到 sdkmanager"
    echo "请先运行: ./setup-android-sdk-macos.sh"
    exit 1
fi

echo "[1/4] 接受许可协议..."
yes | "$SDKMANAGER" --licenses

echo ""
echo "[2/4] 安装 Platform Tools..."
"$SDKMANAGER" "platform-tools"

echo ""
echo "[3/4] 安装 Android Platform 34..."
"$SDKMANAGER" "platforms;android-34"

echo ""
echo "[4/4] 安装 Build Tools 34.0.0..."
"$SDKMANAGER" "build-tools;34.0.0"

echo ""
echo "========================================"
echo "✅ 安装完成！"
echo "========================================"
echo ""
echo "验证:"
ls -la "$ANDROID_HOME/platforms" 2>/dev/null
ls -la "$ANDROID_HOME/build-tools" 2>/dev/null
echo ""
