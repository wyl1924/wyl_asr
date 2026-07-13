#!/bin/bash
# 运行 macOS 客户端

echo "🚀 启动 macOS 语音识别显示客户端..."
echo ""

cd "$(dirname "$0")/VoiceRecognitionDisplay.Desktop"

# 检查 .NET SDK
if ! command -v dotnet &> /dev/null; then
    echo "❌ 错误: 未找到 dotnet 命令"
    echo "请先安装 .NET SDK: https://dotnet.microsoft.com/download"
    exit 1
fi

echo "✅ .NET SDK 版本:"
dotnet --version
echo ""

echo "📦 正在启动应用..."
dotnet run

