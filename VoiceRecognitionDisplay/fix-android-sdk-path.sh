#!/bin/bash

echo "========================================"
echo "修复 Android SDK 路径配置"
echo "========================================"
echo ""

# 检查 ANDROID_HOME
if [ -z "$ANDROID_HOME" ]; then
    echo "❌ ANDROID_HOME 未设置"
    echo ""
    echo "请在 ~/.zshrc 或 ~/.bash_profile 中添加："
    echo "export ANDROID_HOME=\$HOME/Library/Android/sdk"
    echo "export PATH=\$PATH:\$ANDROID_HOME/platform-tools:\$ANDROID_HOME/tools"
    exit 1
fi

echo "✅ ANDROID_HOME: $ANDROID_HOME"

# 检查 android.jar 是否存在
ANDROID_JAR="$ANDROID_HOME/platforms/android-34/android.jar"
if [ ! -f "$ANDROID_JAR" ]; then
    echo "❌ android.jar 不存在: $ANDROID_JAR"
    echo ""
    echo "请安装 Android SDK Platform 34:"
    echo "  sdkmanager \"platforms;android-34\""
    exit 1
fi

echo "✅ android.jar 存在: $ANDROID_JAR"

# 检查 .NET SDK
echo ""
echo "检查 .NET SDK..."
dotnet --version

if [ $? -ne 0 ]; then
    echo "❌ .NET SDK 未安装"
    exit 1
fi

echo "✅ .NET SDK 已安装"

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ANDROID_PROJECT_DIR="$SCRIPT_DIR/VoiceRecognitionDisplay.Android"

# 清理构建缓存
echo ""
echo "清理构建缓存..."

if [ ! -d "$ANDROID_PROJECT_DIR" ]; then
    echo "❌ Android 项目目录不存在: $ANDROID_PROJECT_DIR"
    exit 1
fi

# 清理 bin 和 obj
rm -rf "$ANDROID_PROJECT_DIR/bin" "$ANDROID_PROJECT_DIR/obj"

# 清理 NuGet 缓存
dotnet nuget locals all --clear

echo "✅ 缓存已清理"

# 恢复依赖
echo ""
echo "恢复依赖..."
dotnet restore "$ANDROID_PROJECT_DIR"

if [ $? -ne 0 ]; then
    echo "❌ 恢复依赖失败"
    exit 1
fi

echo "✅ 依赖恢复成功"

echo ""
echo "========================================"
echo "修复完成！"
echo "========================================"
echo ""
echo "现在可以尝试构建："
echo "  cd $ANDROID_PROJECT_DIR"
echo "  dotnet build -c Debug -f net8.0-android"
echo ""
