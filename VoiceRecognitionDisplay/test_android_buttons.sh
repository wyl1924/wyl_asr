#!/bin/bash

# 安卓按钮功能测试脚本

echo "=== 安卓按钮功能测试 ==="
echo ""

# 检查设备连接
echo "检查设备连接..."
adb devices | grep -v "List of devices" | grep "device$" > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ 没有连接的安卓设备"
    exit 1
fi
echo "✅ 设备已连接"
echo ""

# 清空日志
echo "清空日志..."
adb logcat -c
echo ""

# 启动应用
echo "启动应用..."
adb shell am start -n com.smartmeeting.display/.MainActivity
sleep 3
echo ""

echo "=== 测试说明 ==="
echo "请在设备上依次点击以下按钮："
echo "1. 分享按钮（左侧第一个）"
echo "2. 设置按钮（中间）"
echo "3. 关闭按钮（右侧）"
echo ""
echo "查看日志输出以确认按钮点击事件..."
echo "按 Ctrl+C 停止日志查看"
echo ""

# 实时查看日志
adb logcat | grep -E "MainWindowViewModel|MainView|Share|Settings|Close|Command"
