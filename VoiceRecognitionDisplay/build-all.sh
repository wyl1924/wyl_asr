#!/bin/bash
# 构建所有平台版本

echo "========================================="
echo "构建所有平台版本"
echo "========================================="
echo ""

cd VoiceRecognitionDisplay.Desktop

# 清理
echo "清理之前的构建..."
dotnet clean
echo ""

# Windows
echo "构建 Windows 版本..."
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
echo "✓ Windows 构建完成"
echo ""

# macOS
echo "构建 macOS 版本..."
dotnet publish -c Release -r osx-x64 --self-contained true -p:PublishSingleFile=true
echo "✓ macOS 构建完成"
echo ""

# Linux
echo "构建 Linux 版本..."
dotnet publish -c Release -r linux-x64 --self-contained true -p:PublishSingleFile=true
echo "✓ Linux 构建完成"
echo ""

echo "========================================="
echo "所有平台构建完成！"
echo "========================================="
echo ""
echo "输出目录:"
echo "  Windows: VoiceRecognitionDisplay.Desktop/bin/Release/net8.0/win-x64/publish/"
echo "  macOS:   VoiceRecognitionDisplay.Desktop/bin/Release/net8.0/osx-x64/publish/"
echo "  Linux:   VoiceRecognitionDisplay.Desktop/bin/Release/net8.0/linux-x64/publish/"
echo ""
