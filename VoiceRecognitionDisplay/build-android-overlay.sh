#!/bin/bash

echo "========================================"
echo "Android 悬浮窗版本构建脚本"
echo "========================================"
echo ""

# 检查是否有 Android 设备连接
echo "[1/5] 检查 Android 设备..."
adb devices -l

if [ $? -ne 0 ]; then
    echo "❌ 未找到 adb 命令，请确保 Android SDK 已安装"
    exit 1
fi

echo ""
echo "[2/5] 清理旧的构建..."
cd VoiceRecognitionDisplay.Android
dotnet clean

echo ""
echo "[3/5] 恢复依赖..."
dotnet restore

echo ""
echo "[4/5] 构建 APK (Debug)..."
dotnet build -c Debug -f net8.0-android

if [ $? -ne 0 ]; then
    echo "❌ 构建失败"
    exit 1
fi

echo ""
echo "[5/5] 安装到设备..."
APK_PATH=$(find bin/Debug/net8.0-android -name "*.apk" | head -n 1)

if [ -z "$APK_PATH" ]; then
    echo "❌ 未找到 APK 文件"
    exit 1
fi

echo "APK 路径: $APK_PATH"
adb install -r "$APK_PATH"

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "✅ 构建和安装成功！"
    echo "========================================"
    echo ""
    echo "下一步："
    echo "1. 在设备上打开应用"
    echo "2. 授予悬浮窗权限"
    echo "3. 应用会自动隐藏，悬浮窗会显示在底部"
    echo ""
    echo "查看日志："
    echo "  adb logcat | grep -E '(OverlayService|MainActivity)'"
    echo ""
    echo "查看应用日志文件："
    echo "  adb shell cat /sdcard/Android/data/com.smartmeeting.display/files/Logs/window_debug.log"
    echo ""
else
    echo "❌ 安装失败"
    echo "可运行 ./diagnose-android-install.sh \"$APK_PATH\" 查看详细安装日志"
    exit 1
fi
