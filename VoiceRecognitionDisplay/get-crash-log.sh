#!/bin/bash

PACKAGE_NAME="com.smartmeeting.display"
CURRENT_LOG_DIR="/sdcard/Android/data/$PACKAGE_NAME/files/Logs"
LEGACY_LOG_DIR_ONE="/sdcard/Android/data/com.voicerecognition.display/files/Logs"
LEGACY_LOG_DIR_TWO="/sdcard/Android/data/com.voicerecognitiondisplay/files/Logs"

pull_first_match() {
    local target_file="$1"
    shift

    for candidate in "$@"; do
        adb pull "$candidate" "./$target_file" 2>/dev/null && return 0
    done

    return 1
}

echo "========================================"
echo "获取 Android 崩溃日志"
echo "========================================"
echo ""

# 检查设备连接
echo "[1/4] 检查设备连接..."
adb devices

echo ""
echo "[2/4] 获取系统崩溃日志..."
adb logcat -d | grep -A 50 "AndroidRuntime\|FATAL\|智能会议\|VoiceRecognitionDisplay\|SmartMeeting" > crash_log_system.txt

echo ""
echo "[3/4] 获取设备日志文件..."
pull_first_match "app_init.log" \
    "$CURRENT_LOG_DIR/app_init.log" \
    "$LEGACY_LOG_DIR_ONE/app_init.log" \
    "$LEGACY_LOG_DIR_TWO/app_init.log" \
    "/sdcard/VoiceRecognitionDisplay/app_init.log"

pull_first_match "window_debug.log" \
    "$CURRENT_LOG_DIR/window_debug.log" \
    "$LEGACY_LOG_DIR_ONE/window_debug.log" \
    "$LEGACY_LOG_DIR_TWO/window_debug.log"

pull_first_match "crash_log_device.log" \
    "$CURRENT_LOG_DIR/crash.log" \
    "$LEGACY_LOG_DIR_ONE/crash.log" \
    "$LEGACY_LOG_DIR_TWO/crash.log"

echo ""
echo "[4/4] 获取完整 logcat..."
adb logcat -d > logcat_full.txt

echo ""
echo "========================================"
echo "日志已保存到:"
echo "  - app_init.log (应用初始化日志) ⭐ 最重要"
echo "  - crash_log_system.txt (系统崩溃日志)"
echo "  - window_debug.log (窗口调试日志)"
echo "  - crash_log_device.log (应用崩溃日志)"
echo "  - logcat_full.txt (完整系统日志)"
echo "========================================"
echo ""
echo "查看日志:"
echo "  cat app_init.log"
echo "  cat crash_log_system.txt"
echo "  cat window_debug.log"
echo ""
echo "如果设备未连接电脑，可以直接从设备查看:"
echo "  $CURRENT_LOG_DIR/app_init.log"
echo ""
