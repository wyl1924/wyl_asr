#!/bin/bash

# 从 Android 设备拉取日志文件

PACKAGE_NAME="com.smartmeeting.display"
DEVICE_LOG_PATH="/sdcard/Android/data/$PACKAGE_NAME/files/Logs/window_debug.log"
LEGACY_LOG_PATH_ONE="/sdcard/Android/data/com.voicerecognitiondisplay/files/Logs/window_debug.log"
LEGACY_LOG_PATH_TWO="/sdcard/Android/data/com.voicerecognition.display/files/Logs/window_debug.log"

echo "=========================================="
echo "从 Android 设备拉取日志文件"
echo "=========================================="
echo ""

# 本地保存路径
LOCAL_LOG_PATH="./android_window_debug.log"

echo "正在拉取日志文件..."
echo "设备路径: $DEVICE_LOG_PATH"
echo "本地路径: $LOCAL_LOG_PATH"
echo ""

# 拉取日志文件
adb pull "$DEVICE_LOG_PATH" "$LOCAL_LOG_PATH" 2>/dev/null ||
adb pull "$LEGACY_LOG_PATH_ONE" "$LOCAL_LOG_PATH" 2>/dev/null ||
adb pull "$LEGACY_LOG_PATH_TWO" "$LOCAL_LOG_PATH" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✓ 日志文件拉取成功！"
    echo ""
    echo "=========================================="
    echo "日志内容："
    echo "=========================================="
    cat "$LOCAL_LOG_PATH"
    echo ""
    echo "=========================================="
    echo "日志文件已保存到: $LOCAL_LOG_PATH"
    echo "=========================================="
else
    echo "✗ 拉取失败！"
    echo ""
    echo "可能的原因："
    echo "1. 设备未连接"
    echo "2. 应用未运行（日志文件未创建）"
    echo "3. 权限问题"
    echo ""
    echo "请尝试："
    echo "1. 检查设备连接: adb devices"
    echo "2. 启动应用后再拉取日志"
    echo "3. 使用 adb shell 手动查看:"
    echo "   adb shell cat $DEVICE_LOG_PATH"
fi
