#!/bin/bash

echo "========================================"
echo "Android 悬浮窗版本测试脚本"
echo "========================================"
echo ""

# 检查设备连接
echo "[1/4] 检查设备连接..."
DEVICE_COUNT=$(adb devices | grep -v "List" | grep "device" | wc -l)

if [ $DEVICE_COUNT -eq 0 ]; then
    echo "❌ 未找到连接的 Android 设备"
    echo ""
    echo "请确保："
    echo "1. 设备已通过 USB 连接"
    echo "2. 已开启 USB 调试"
    echo "3. 已授权此计算机"
    exit 1
fi

echo "✅ 找到 $DEVICE_COUNT 个设备"
adb devices -l

# 检查应用是否已安装
echo ""
echo "[2/4] 检查应用状态..."
PACKAGE_NAME="com.smartmeeting.display"
IS_INSTALLED=$(adb shell pm list packages | grep $PACKAGE_NAME)

if [ -z "$IS_INSTALLED" ]; then
    echo "⚠️  应用未安装"
else
    echo "✅ 应用已安装"
    
    # 检查悬浮窗权限
    PERMISSION=$(adb shell dumpsys package $PACKAGE_NAME | grep "SYSTEM_ALERT_WINDOW" | grep "granted=true")
    if [ -z "$PERMISSION" ]; then
        echo "⚠️  悬浮窗权限未授予"
    else
        echo "✅ 悬浮窗权限已授予"
    fi
fi

# 启动应用
echo ""
echo "[3/4] 启动应用..."
adb shell am start -n $PACKAGE_NAME/.MainActivity

sleep 2

# 检查服务状态
echo ""
echo "[4/4] 检查服务状态..."
SERVICE_STATUS=$(adb shell dumpsys activity services | grep "OverlayService")

if [ -z "$SERVICE_STATUS" ]; then
    echo "⚠️  OverlayService 未运行"
else
    echo "✅ OverlayService 正在运行"
fi

# 显示实时日志
echo ""
echo "========================================"
echo "实时日志 (Ctrl+C 退出)"
echo "========================================"
echo ""

adb logcat -c  # 清空日志
adb logcat | grep -E "(OverlayService|MainActivity|VoiceRecognition)"
