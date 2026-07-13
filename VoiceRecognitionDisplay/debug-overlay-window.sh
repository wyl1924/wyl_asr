#!/bin/bash

echo "========================================"
echo "Android 悬浮窗调试工具"
echo "========================================"
echo ""

PACKAGE_NAME="com.smartmeeting.display"

# 清空日志
echo "清空日志缓存..."
adb logcat -c

echo ""
echo "启动应用并监控日志..."
echo "========================================"
echo ""

# 启动应用
adb shell am start -n $PACKAGE_NAME/.MainActivity

# 等待 2 秒
sleep 2

# 显示日志
echo ""
echo "=== MainActivity 日志 ==="
adb logcat -d | grep "MainActivity" | tail -20

echo ""
echo "=== OverlayService 日志 ==="
adb logcat -d | grep "OverlayService" | tail -20

echo ""
echo "=== 错误日志 ==="
adb logcat -d | grep -E "(ERROR|FATAL|Exception)" | tail -10

echo ""
echo "=== 权限状态 ==="
adb shell dumpsys package $PACKAGE_NAME | grep "SYSTEM_ALERT_WINDOW"

echo ""
echo "=== 服务状态 ==="
adb shell dumpsys activity services | grep -A 5 "OverlayService"

echo ""
echo "=== 窗口信息 ==="
adb shell dumpsys window windows | grep -A 10 "smartmeeting"

echo ""
echo "========================================"
echo "调试信息收集完成"
echo "========================================"
