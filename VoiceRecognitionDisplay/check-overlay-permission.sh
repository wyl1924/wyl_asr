#!/bin/bash

echo "========================================"
echo "Android 悬浮窗权限检查工具"
echo "========================================"
echo ""

PACKAGE_NAME="com.smartmeeting.display"

# 检查设备连接
echo "[1/5] 检查设备连接..."
DEVICE_COUNT=$(adb devices | grep -v "List" | grep "device" | wc -l)

if [ $DEVICE_COUNT -eq 0 ]; then
    echo "❌ 未找到连接的 Android 设备"
    exit 1
fi

echo "✅ 找到 $DEVICE_COUNT 个设备"
echo ""

# 检查应用是否安装
echo "[2/5] 检查应用安装状态..."
IS_INSTALLED=$(adb shell pm list packages | grep $PACKAGE_NAME)

if [ -z "$IS_INSTALLED" ]; then
    echo "❌ 应用未安装"
    echo ""
    echo "请先安装应用："
    echo "  ./build-android-overlay.sh"
    exit 1
fi

echo "✅ 应用已安装"
echo ""

# 检查悬浮窗权限
echo "[3/5] 检查悬浮窗权限..."
PERMISSION=$(adb shell dumpsys package $PACKAGE_NAME | grep "SYSTEM_ALERT_WINDOW" | grep "granted=true")

if [ -z "$PERMISSION" ]; then
    echo "❌ 悬浮窗权限未授予"
    echo ""
    echo "请按以下步骤授予权限："
    echo "1. 启动应用"
    echo "2. 点击'去设置'按钮"
    echo "3. 打开'显示在其他应用上层'开关"
    echo "4. 返回应用"
    echo ""
    echo "或者手动设置："
    echo "  设置 → 应用 → 智能会议 → 权限 → 显示悬浮窗"
    echo ""
    
    # 尝试打开权限设置页面
    read -p "是否现在打开权限设置页面？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        adb shell am start -a android.settings.action.MANAGE_OVERLAY_PERMISSION -d "package:$PACKAGE_NAME"
        echo ""
        echo "请在设备上授予权限，然后按回车继续..."
        read
        
        # 重新检查
        PERMISSION=$(adb shell dumpsys package $PACKAGE_NAME | grep "SYSTEM_ALERT_WINDOW" | grep "granted=true")
        if [ -z "$PERMISSION" ]; then
            echo "❌ 权限仍未授予"
            exit 1
        fi
    else
        exit 1
    fi
fi

echo "✅ 悬浮窗权限已授予"
echo ""

# 检查服务状态
echo "[4/5] 检查服务运行状态..."
SERVICE_STATUS=$(adb shell dumpsys activity services | grep "OverlayService")

if [ -z "$SERVICE_STATUS" ]; then
    echo "⚠️  OverlayService 未运行"
    echo ""
    echo "尝试启动应用..."
    adb shell am start -n $PACKAGE_NAME/.MainActivity
    sleep 3
    
    SERVICE_STATUS=$(adb shell dumpsys activity services | grep "OverlayService")
    if [ -z "$SERVICE_STATUS" ]; then
        echo "❌ 服务启动失败"
        echo ""
        echo "查看错误日志："
        adb logcat -d | grep -E "(OverlayService|MainActivity|ERROR)" | tail -20
        exit 1
    fi
fi

echo "✅ OverlayService 正在运行"
echo ""

# 检查悬浮窗是否显示
echo "[5/5] 检查悬浮窗显示状态..."
WINDOW_INFO=$(adb shell dumpsys window windows | grep "smartmeeting")

if [ -z "$WINDOW_INFO" ]; then
    echo "⚠️  未检测到悬浮窗"
    echo ""
    echo "可能的原因："
    echo "1. 悬浮窗创建失败"
    echo "2. 悬浮窗被系统限制"
    echo "3. 悬浮窗已隐藏"
    echo ""
    echo "查看详细日志："
    adb logcat -d | grep -E "OverlayService" | tail -30
else
    echo "✅ 悬浮窗已显示"
    echo ""
    echo "悬浮窗信息："
    echo "$WINDOW_INFO"
fi

echo ""
echo "========================================"
echo "检查完成！"
echo "========================================"
echo ""

# 显示实时日志选项
read -p "是否查看实时日志？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "显示实时日志 (Ctrl+C 退出)..."
    echo ""
    adb logcat -c
    adb logcat | grep -E "(OverlayService|MainActivity)"
fi
