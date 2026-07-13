#!/bin/bash
# Linux 构建脚本

echo "正在构建 Linux 版本..."

cd VoiceRecognitionDisplay.Desktop

# 清理之前的构建
dotnet clean

# 构建 Linux 可执行文件
dotnet publish -c Release -r linux-x64 --self-contained true -p:PublishSingleFile=true

echo ""
echo "构建完成！"
echo "输出目录: VoiceRecognitionDisplay.Desktop/bin/Release/net8.0/linux-x64/publish/"
echo ""
