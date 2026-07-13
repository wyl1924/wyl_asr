#!/bin/bash

# 安卓窗口宽度修复测试脚本

echo "=== 安卓窗口宽度修复测试 ==="
echo ""

# 1. 编译应用
echo "步骤 1: 编译安卓应用..."
./build-android.sh
if [ $? -ne 0 ]; then
    echo "❌ 编译失败"
    exit 1
fi
echo "✅ 编译成功"
echo ""

# 2. 检查 APK 是否存在
APK_PATH="VoiceRecognitionDisplay.Android/bin/Release/net8.0-android34.0/com.smartmeeting.display-Signed.apk"
if [ ! -f "$APK_PATH" ]; then
    echo "❌ APK 文件不存在: $APK_PATH"
    exit 1
fi
echo "✅ APK 文件存在"
echo ""

# 3. 检查设备连接
echo "步骤 2: 检查设备连接..."
adb devices | grep -v "List of devices" | grep "device$" > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ 没有连接的安卓设备"
    echo "请连接设备后重试"
    exit 1
fi
echo "✅ 设备已连接"
echo ""

# 4. 安装应用
echo "步骤 3: 安装应用到设备..."
adb install -r "$APK_PATH"
if [ $? -ne 0 ]; then
    echo "❌ 安装失败"
    exit 1
fi
echo "✅ 安装成功"
echo ""

# 5. 启动应用
echo "步骤 4: 启动应用..."
adb shell am start -n com.smartmeeting.display/.MainActivity
sleep 2
echo "✅ 应用已启动"
echo ""

# 6. 查看日志
echo "步骤 5: 查看窗口宽度日志..."
echo "按 Ctrl+C 停止日志查看"
echo ""
adb logcat -c  # 清空日志
adb logcat | grep -E "WindowWidth|MainView|ApplySettings"
