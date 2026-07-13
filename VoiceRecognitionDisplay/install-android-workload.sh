#!/bin/bash

echo "========================================"
echo "安装 Android 工作负载"
echo "========================================"
echo ""
echo "此脚本可能需要sudo权限"
echo ""

echo ""
echo "[1/3] 检查当前已安装的工作负载..."
dotnet workload list

echo ""
echo "[2/3] 安装 Android 工作负载..."
echo "这可能需要几分钟时间，请耐心等待..."
dotnet workload install android

echo ""
echo "[3/3] 验证安装..."
dotnet workload list

echo ""
echo "========================================"
echo "✅ 安装完成！"
echo "========================================"
echo ""
echo "现在可以运行 ./build-android.sh 来构建APK了"
echo ""
