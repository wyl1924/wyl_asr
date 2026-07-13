#!/bin/bash
# 测试设置保存和加载流程

echo "=== 测试设置保存和加载流程 ==="
echo ""

# 查找设置文件位置
SETTINGS_DIR="$HOME/Library/Application Support/VoiceRecognitionDisplay"
SETTINGS_FILE="$SETTINGS_DIR/settings.json"

echo "设置文件位置: $SETTINGS_FILE"
echo ""

# 检查设置文件是否存在
if [ -f "$SETTINGS_FILE" ]; then
    echo "当前设置内容:"
    cat "$SETTINGS_FILE"
    echo ""
else
    echo "设置文件不存在"
    echo ""
fi

echo "现在启动应用程序..."
echo "请执行以下操作:"
echo "1. 点击设置按钮（⚙️）"
echo "2. 修改背景色（例如改为 #FF0000 红色）"
echo "3. 点击'保存设置'按钮"
echo "4. 观察主窗口背景色是否变化"
echo "5. 关闭应用程序"
echo ""
echo "按 Enter 键启动应用..."
read

cd VoiceRecognitionDisplay.Desktop
dotnet run

echo ""
echo "应用程序已关闭"
echo ""

# 再次检查设置文件
if [ -f "$SETTINGS_FILE" ]; then
    echo "保存后的设置内容:"
    cat "$SETTINGS_FILE"
    echo ""
else
    echo "设置文件仍然不存在"
fi
