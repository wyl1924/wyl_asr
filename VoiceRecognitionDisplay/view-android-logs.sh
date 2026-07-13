#!/bin/bash

# Android 日志查看脚本
# 用于查看应用的运行日志，诊断窗口设置问题

echo "=========================================="
echo "查看 Android 应用日志"
echo "=========================================="
echo ""
echo "提示：按 Ctrl+C 停止查看日志"
echo ""

# 清除旧日志
adb logcat -c

# 启动应用
echo "正在启动应用..."
adb shell am start -n com.smartmeeting.display/.MainActivity

# 等待应用启动
sleep 2

echo ""
echo "=========================================="
echo "应用日志输出："
echo "=========================================="
echo ""

# 查看日志，过滤关键信息
adb logcat | grep -E "(MainActivity|窗口属性|屏幕密度|目标高度|Width|Height|Gravity|Flags|NotFocusable)"
