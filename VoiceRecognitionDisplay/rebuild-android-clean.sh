#!/bin/bash

# Android 完全重新编译脚本
# 用于确保所有修改都生效

PACKAGE_NAME="com.smartmeeting.display"
INSTALL_OUTPUT_LOG="android_install_output.log"
INSTALL_LOGCAT_LOG="android_install_logcat.txt"

echo "=========================================="
echo "Android 应用完全重新编译"
echo "=========================================="

# 1. 清理所有编译缓存
echo ""
echo "步骤 1: 清理编译缓存..."
rm -rf VoiceRecognitionDisplay.Android/bin
rm -rf VoiceRecognitionDisplay.Android/obj
rm -rf VoiceRecognitionDisplay/bin
rm -rf VoiceRecognitionDisplay/obj
echo "✓ 缓存已清理"

# 2. 重新编译
echo ""
echo "步骤 2: 重新编译 Android 应用..."
dotnet build VoiceRecognitionDisplay.Android/VoiceRecognitionDisplay.Android.csproj -c Release

if [ $? -ne 0 ]; then
    echo "✗ 编译失败！"
    exit 1
fi

echo "✓ 编译成功"

# 3. 查找生成的 APK
echo ""
echo "步骤 3: 查找生成的 APK..."
APK_PATH=$(find VoiceRecognitionDisplay.Android/bin/Release -name "*.apk" | head -n 1)

if [ -z "$APK_PATH" ]; then
    echo "✗ 未找到 APK 文件"
    exit 1
fi

echo "✓ 找到 APK: $APK_PATH"

# 4. 检查设备连接
echo ""
echo "步骤 4: 检查 Android 设备..."
adb devices

# 5. 卸载旧应用（如果存在）
echo ""
echo "步骤 5: 卸载旧应用..."
adb uninstall "$PACKAGE_NAME" 2>/dev/null || echo "  (旧应用不存在，跳过)"

# 6. 安装新应用
echo ""
echo "步骤 6: 安装新应用..."
adb logcat -c >/dev/null 2>&1 || true
adb install "$APK_PATH" > "$INSTALL_OUTPUT_LOG" 2>&1

if [ $? -ne 0 ]; then
    echo "✗ 安装失败！"
    echo ""
    echo "adb install 输出："
    cat "$INSTALL_OUTPUT_LOG"
    adb logcat -d > "$INSTALL_LOGCAT_LOG" 2>/dev/null || true
    echo ""
    echo "安装日志已保存到:"
    echo "  - $INSTALL_OUTPUT_LOG"
    echo "  - $INSTALL_LOGCAT_LOG"
    echo ""
    echo "如需更完整诊断，可运行:"
    echo "  ./diagnose-android-install.sh \"$APK_PATH\""
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ 安装成功！"
echo "=========================================="
echo ""
echo "现在可以在设备上启动'智能会议'应用了"
echo ""
echo "预期效果："
echo "  - 字幕条只显示在屏幕底部（高度约 240dp）"
echo "  - 上方区域透明且可穿透"
echo "  - 点击字幕条外部不会激活应用"
echo ""
