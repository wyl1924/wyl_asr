#!/bin/bash

echo "========================================"
echo "修复并构建 Android APK"
echo "========================================"
echo ""

# 设置 ANDROID_HOME
if [ -z "$ANDROID_HOME" ]; then
    export ANDROID_HOME=$HOME/Library/Android/sdk
fi

echo "步骤 1: 安装 SDK 组件"
echo "----------------------------------------"
./install-sdk-components.sh

if [ $? -ne 0 ]; then
    echo "❌ SDK 组件安装失败"
    exit 1
fi

echo ""
echo "步骤 2: 清理并重新构建"
echo "----------------------------------------"

cd VoiceRecognitionDisplay.Android

# 完全清理
echo "清理旧文件..."
rm -rf obj bin
dotnet clean -v q

# 清理 NuGet 缓存
echo "清理 NuGet 缓存..."
dotnet nuget locals all --clear

# 恢复依赖（使用国内镜像）
echo ""
echo "恢复依赖（使用华为云镜像）..."
dotnet restore --configfile ../NuGet.Config

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 依赖恢复失败"
    echo ""
    echo "如果网络问题持续，可以尝试："
    echo "1. 使用 VPN"
    echo "2. 等待网络恢复后重试"
    echo "3. 使用其他 NuGet 镜像源"
    exit 1
fi

# 构建
echo ""
echo "构建 Release 版本..."
dotnet build -c Release -f net8.0-android34.0 \
    -p:AndroidSdkDirectory="$ANDROID_HOME" \
    -v minimal

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 构建失败"
    exit 1
fi

# 发布 APK
echo ""
echo "发布 APK..."
dotnet publish -c Release -f net8.0-android34.0 \
    -p:AndroidPackageFormat=apk \
    -p:AndroidSdkDirectory="$ANDROID_HOME" \
    -v minimal

echo ""
echo "========================================"
echo "✅ 完成！"
echo "========================================"
echo ""

APK_PATH=$(find bin/Release -name "*.apk" -type f 2>/dev/null | head -1)
if [ -n "$APK_PATH" ]; then
    echo "APK 位置: $APK_PATH"
    echo "APK 大小: $(du -h "$APK_PATH" | cut -f1)"
else
    echo "⚠️  未找到 APK 文件"
fi
echo ""
