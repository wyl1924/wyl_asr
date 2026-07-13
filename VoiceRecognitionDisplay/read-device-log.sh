#!/bin/bash

# 从 Android 设备读取日志文件

PACKAGE_NAME="com.smartmeeting.display"
LOG_PATH="/sdcard/Android/data/$PACKAGE_NAME/files/Logs/window_debug.log"
LEGACY_LOG_PATH_ONE="/sdcard/Android/data/com.voicerecognitiondisplay/files/Logs/window_debug.log"
LEGACY_LOG_PATH_TWO="/sdcard/Android/data/com.voicerecognition.display/files/Logs/window_debug.log"

echo "=========================================="
echo "从 Android 设备读取窗口调试日志"
echo "=========================================="
echo ""

echo "正在读取日志文件: $LOG_PATH"
echo ""

# 读取日志文件
adb shell cat "$LOG_PATH" 2>/dev/null ||
adb shell cat "$LEGACY_LOG_PATH_ONE" 2>/dev/null ||
adb shell cat "$LEGACY_LOG_PATH_TWO" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "错误：无法读取日志文件"
    echo ""
    echo "可能的原因："
    echo "1. 应用未运行过"
    echo "2. 日志文件路径不正确"
    echo "3. 没有读取权限"
    echo ""
    echo "尝试查找日志文件..."
    adb shell find /sdcard -name "window_debug.log" 2>/dev/null
fi

echo ""
echo "=========================================="
echo "如果看到日志内容，请检查："
echo "  - 屏幕密度是多少"
echo "  - 目标高度是多少"
echo "  - 窗口属性是否正确设置"
echo "  - NotFocusable 是否为 True"
echo "=========================================="
