#!/bin/bash

echo "========================================"
echo "macOS Android SDK 安装脚本"
echo "========================================"
echo ""

# 检查是否已安装
if [ -d "$HOME/Library/Android/sdk" ]; then
    echo "✅ Android SDK 已安装在: $HOME/Library/Android/sdk"
    export ANDROID_HOME=$HOME/Library/Android/sdk
    export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools
    
    echo ""
    echo "设置环境变量..."
    echo "export ANDROID_HOME=$HOME/Library/Android/sdk" >> ~/.zshrc
    echo "export PATH=\$PATH:\$ANDROID_HOME/cmdline-tools/latest/bin" >> ~/.zshrc
    echo "export PATH=\$PATH:\$ANDROID_HOME/platform-tools" >> ~/.zshrc
    
    echo ""
    echo "✅ 环境变量已设置"
    echo ""
    echo "请运行以下命令使环境变量生效:"
    echo "source ~/.zshrc"
    echo ""
    echo "然后重新运行构建命令"
    exit 0
fi

echo "Android SDK 未找到，开始安装..."
echo ""

# 创建目录
echo "[1/5] 创建 Android SDK 目录..."
mkdir -p ~/Library/Android/sdk
mkdir -p ~/Downloads/android-sdk

# 下载 Command Line Tools
echo ""
echo "[2/5] 下载 Android Command Line Tools..."
cd ~/Downloads/android-sdk

if [ ! -f "commandlinetools-mac-11076708_latest.zip" ]; then
    echo "正在下载... (约 150MB)"
    curl -L -o commandlinetools-mac-11076708_latest.zip \
        https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip
else
    echo "文件已存在，跳过下载"
fi

# 解压
echo ""
echo "[3/5] 解压文件..."
unzip -q commandlinetools-mac-11076708_latest.zip

# 移动到正确位置
echo ""
echo "[4/5] 安装到 ~/Library/Android/sdk..."
mkdir -p ~/Library/Android/sdk/cmdline-tools
mv cmdline-tools ~/Library/Android/sdk/cmdline-tools/latest

# 设置环境变量
echo ""
echo "[5/5] 配置环境变量..."
export ANDROID_HOME=$HOME/Library/Android/sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools

# 添加到 .zshrc
if ! grep -q "ANDROID_HOME" ~/.zshrc; then
    echo "" >> ~/.zshrc
    echo "# Android SDK" >> ~/.zshrc
    echo "export ANDROID_HOME=\$HOME/Library/Android/sdk" >> ~/.zshrc
    echo "export PATH=\$PATH:\$ANDROID_HOME/cmdline-tools/latest/bin" >> ~/.zshrc
    echo "export PATH=\$PATH:\$ANDROID_HOME/platform-tools" >> ~/.zshrc
fi

# 接受许可并安装组件
echo ""
echo "安装 Android SDK 组件..."
yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses
$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"

echo ""
echo "========================================"
echo "✅ Android SDK 安装完成！"
echo "========================================"
echo ""
echo "SDK 位置: $ANDROID_HOME"
echo ""
echo "⚠️  重要: 请运行以下命令使环境变量生效:"
echo ""
echo "    source ~/.zshrc"
echo ""
echo "然后重新运行构建命令:"
echo ""
echo "    cd VoiceRecognitionDisplay.Android"
echo "    dotnet build -c Release -f net8.0-android34.0"
echo ""
