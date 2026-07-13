# 快速开始指南

5 分钟快速启动滚动字幕显示应用。

## 前置要求

- ✅ .NET 8.0 SDK ([下载地址](https://dotnet.microsoft.com/download/dotnet/8.0))
- ✅ ASR 服务器正在运行

## 步骤 1: 检查 .NET 环境

```bash
dotnet --version
```

应该显示 8.0.x 或更高版本。

## 步骤 2: 启动 ASR 服务器（如果还未启动）

```bash
# 进入 ASR 项目根目录
cd ..

# 启动服务器（启用说话人识别）
python main.py --enable-speaker-verification

# 或使用启动脚本
# Windows: start_with_serial.bat
# Linux/Mac: ./start_with_serial.sh
```

等待服务器启动完成，看到类似输出：

```
🚀 WebSocket服务器启动在 ws://0.0.0.0:10095
```

## 步骤 3: 启动字幕应用

### Windows

双击运行 `run.bat`，或在命令行中：

```bash
cd subtitle_display
dotnet run
```

### Linux / macOS

```bash
cd subtitle_display
chmod +x run.sh
./run.sh
```

## 步骤 4: 连接到 ASR 服务器

1. 字幕应用窗口会自动打开
2. 确认 WebSocket URL 为 `ws://localhost:10095/`
3. 点击 **"连接"** 按钮
4. 状态栏显示 **"已连接"**

## 步骤 5: 开始使用

1. 打开浏览器访问 ASR Web 界面: http://localhost:10095
2. 点击 **"开始录音"** 按钮
3. 对着麦克风说话
4. 观察字幕应用窗口，实时字幕会自动显示

## 字幕显示效果

```
[张三] 大家好，今天我们来讨论一下人工智能的发展趋势。
[李四] 我认为人工智能在未来会有更广泛的应用。
[张三] 是的，特别是在医疗和教育领域。
```

## 常用操作

| 操作 | 说明 |
|------|------|
| **连接** | 连接到 ASR WebSocket 服务器 |
| **断开** | 断开 WebSocket 连接 |
| **清空** | 清除所有字幕内容 |
| **拖动窗口** | 可以移动到屏幕任意位置 |
| **调整窗口大小** | 拖动窗口边缘调整大小 |

## 快速配置

### 修改 WebSocket 地址

如果 ASR 服务器运行在其他地址：

```
ws://192.168.1.100:10095/  # 局域网其他机器
ws://example.com:10095/    # 远程服务器
```

### 修改字体大小

编辑 `MainWindow.axaml`，找到：

```xml
<Style Selector="TextBlock.speaker">
    <Setter Property="FontSize" Value="32"/>  <!-- 修改这里 -->
</Style>
```

### 修改每行字符数

编辑 `MainWindow.axaml.cs`，找到：

```csharp
private const int MaxCharsPerLine = 50;  // 修改这里
```

## 发布独立应用（可选）

如果想要创建独立的可执行文件：

### Windows

```bash
build.bat
```

可执行文件位于: `bin\Release\net8.0\win-x64\publish\SubtitleDisplay.exe`

### Linux / macOS

```bash
chmod +x build.sh
./build.sh
```

可执行文件位于: `bin/Release/net8.0/{platform}/publish/SubtitleDisplay`

## 故障排除

### ❌ 连接失败

**原因**: ASR 服务器未启动或地址错误

**解决**:
1. 确认 ASR 服务器正在运行
2. 检查 WebSocket URL 是否正确
3. 检查防火墙设置

### ❌ 字幕不显示

**原因**: ASR 服务器未启用说话人识别

**解决**:
```bash
# 重新启动 ASR 服务器，添加参数
python main.py --enable-speaker-verification
```

### ❌ 字幕显示乱码

**原因**: 编码问题

**解决**: 确保 ASR 服务器发送 UTF-8 编码的消息

### ❌ 应用无法启动

**原因**: .NET SDK 未安装或版本过低

**解决**:
```bash
# 检查版本
dotnet --version

# 如果版本低于 8.0，请下载安装最新版本
# https://dotnet.microsoft.com/download/dotnet/8.0
```

## 高级用法

### 多显示器设置

1. 将字幕窗口拖动到第二个显示器
2. 窗口会保持置顶显示
3. 适合演讲、直播等场景

### OBS 集成

1. 在 OBS 中添加 **"窗口捕获"** 源
2. 选择 **"实时字幕显示"** 窗口
3. 调整位置和大小
4. 可以添加色度键去除背景

### 远程使用

如果 ASR 服务器在远程机器上：

1. 确保远程服务器的 10095 端口可访问
2. 修改 WebSocket URL 为远程地址
3. 点击连接

## 下一步

- 📖 查看完整文档: [README.md](README.md)
- 🔧 集成指南: [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
- 💡 自定义样式和功能
- 🚀 发布独立应用分享给他人

## 需要帮助？

- 查看 [README.md](README.md) 了解详细功能
- 查看 [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) 了解集成细节
- 提交 Issue 到 GitHub
- 查看 ASR 系统文档: `../docs/`

---

**提示**: 窗口默认置顶显示，方便在使用其他应用时查看字幕。如需取消置顶，可以修改 `MainWindow.axaml` 中的 `Topmost="True"` 为 `Topmost="False"`。
