#!/bin/bash

echo "========================================"
echo "Android 开发环境诊断工具"
echo "========================================"
echo ""

# 1. 检查 .NET SDK
echo "[1/6] 检查 .NET SDK..."
if command -v dotnet &> /dev/null; then
    DOTNET_VERSION=$(dotnet --version)
    echo "✅ .NET SDK: $DOTNET_VERSION"
else
    echo "❌ 未安装 .NET SDK"
fi

echo ""

# 2. 检查 Android 工作负载
echo "[2/6] 检查 Android 工作负载..."
if dotnet workload list | grep -q "android"; then
    WORKLOAD_INFO=$(dotnet workload list | grep "android")
    echo "✅ Android 工作负载已安装"
    echo "   $WORKLOAD_INFO"
else
    echo "❌ Android 工作负载未安装"
    echo "   运行: ./install-android-workload.sh"
fi

echo ""

# 3. 检查环境变量
echo "[3/6] 检查环境变量..."
if [ -n "$ANDROID_HOME" ]; then
    echo "✅ ANDROID_HOME: $ANDROID_HOME"
else
    echo "⚠️  ANDROID_HOME 未设置"
fi

echo ""

# 4. 检查 Android SDK 位置
echo "[4/6] 检查 Android SDK..."
SDK_FOUND=false

if [ -d "$HOME/Library/Android/sdk" ]; then
    echo "✅ 找到 SDK: $HOME/Library/Android/sdk"
    SDK_PATH="$HOME/Library/Android/sdk"
    SDK_FOUND=true
elif [ -d "$HOME/Library/Developer/Xamarin/android-sdk-macosx" ]; then
    echo "✅ 找到 SDK: $HOME/Library/Developer/Xamarin/android-sdk-macosx"
    SDK_PATH="$HOME/Library/Developer/Xamarin/android-sdk-macosx"
    SDK_FOUND=true
else
    echo "❌ 未找到 Android SDK"
    echo ""
    echo "   常见位置:"
    echo "   - $HOME/Library/Android/sdk"
    echo "   - $HOME/Library/Developer/Xamarin/android-sdk-macosx"
fi

echo ""

# 5. 检查 SDK 组件
if [ "$SDK_FOUND" = true ]; then
    echo "[5/6] 检查 SDK 组件..."
    
    if [ -d "$SDK_PATH/platforms/android-34" ]; then
        echo "✅ Android Platform 34"
    else
        echo "❌ 缺少 Android Platform 34"
    fi
    
    if [ -d "$SDK_PATH/build-tools" ]; then
        BUILD_TOOLS=$(ls "$SDK_PATH/build-tools" 2>/dev/null | head -1)
        if [ -n "$BUILD_TOOLS" ]; then
            echo "✅ Build Tools: $BUILD_TOOLS"
        else
            echo "⚠️  Build Tools 目录为空"
        fi
    else
        echo "❌ 缺少 Build Tools"
    fi
    
    if [ -d "$SDK_PATH/platform-tools" ]; then
        echo "✅ Platform Tools"
    else
        echo "❌ 缺少 Platform Tools"
    fi
    
    if [ -d "$SDK_PATH/cmdline-tools" ]; then
        echo "✅ Command Line Tools"
    else
        echo "⚠️  缺少 Command Line Tools"
    fi
else
    echo "[5/6] 跳过 SDK 组件检查（未找到 SDK）"
fi

echo ""

# 6. 检查项目配置
echo "[6/6] 检查项目配置..."
if [ -f "VoiceRecognitionDisplay.Android/VoiceRecognitionDisplay.Android.csproj" ]; then
    echo "✅ 找到 Android 项目文件"
    
    TARGET_FRAMEWORK=$(grep -o "net8.0-android[0-9.]*" VoiceRecognitionDisplay.Android/VoiceRecognitionDisplay.Android.csproj | head -1)
    if [ -n "$TARGET_FRAMEWORK" ]; then
        echo "   目标框架: $TARGET_FRAMEWORK"
    fi
else
    echo "❌ 未找到 Android 项目文件"
fi

if [ -f "Directory.Build.props" ]; then
    echo "✅ 找到 Directory.Build.props"
else
    echo "⚠️  未找到 Directory.Build.props"
fi

echo ""
echo "========================================"
echo "诊断总结"
echo "========================================"
echo ""

# 生成建议
ISSUES=0

if ! command -v dotnet &> /dev/null; then
    echo "❌ 需要安装 .NET SDK"
    ISSUES=$((ISSUES + 1))
fi

if ! dotnet workload list | grep -q "android"; then
    echo "❌ 需要安装 Android 工作负载"
    echo "   运行: ./install-android-workload.sh"
    ISSUES=$((ISSUES + 1))
fi

if [ "$SDK_FOUND" = false ]; then
    echo "❌ 需要安装 Android SDK"
    echo "   推荐: 安装 Android Studio (https://developer.android.com/studio)"
    echo "   或运行: ./setup-android-sdk-macos.sh"
    ISSUES=$((ISSUES + 1))
fi

if [ -z "$ANDROID_HOME" ] && [ "$SDK_FOUND" = true ]; then
    echo "⚠️  需要设置 ANDROID_HOME 环境变量"
    echo "   运行: echo 'export ANDROID_HOME=$SDK_PATH' >> ~/.zshrc"
    echo "   然后: source ~/.zshrc"
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo "✅ 环境配置正常！"
    echo ""
    echo "可以开始构建:"
    echo "  ./build-android.sh"
else
    echo ""
    echo "发现 $ISSUES 个问题需要解决"
    echo ""
    echo "详细说明请查看: ANDROID_SDK_SETUP.md"
fi

echo ""
