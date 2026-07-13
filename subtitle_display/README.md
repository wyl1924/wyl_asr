# 实时字幕滚动显示 (Avalonia)

基于 Avalonia 框架开发的实时字幕滚动显示应用程序，用于显示 ASR 识别结果。

## 功能特点

- ✨ **说话人头部固定显示**: 每行字幕开头显示说话人标识
- 📝 **智能内容累加**: 同一说话人的内容会累加到当前行
- 🔄 **自动换行**: 当内容超过每行最大字符数时自动创建新行
- 🎨 **现代化 UI**: 使用 Fluent 设计风格
- 🔌 **WebSocket 连接**: 实时接收 ASR 服务器的识别结果
- 🖥️ **置顶显示**: 窗口始终置顶，方便观看

## 字幕显示逻辑

1. **说话人标识**: 每行开头显示 `[说话人]` 标识，使用蓝色粗体
2. **内容累加**: 
   - 如果当前行未满（< 50 字符），新内容会追加到当前行
   - 如果当前行已满，会创建新行显示 `[说话人] + 新内容`
3. **自动滚动**: 新内容添加时自动滚动到底部

## 系统要求

- .NET 8.0 SDK 或更高版本
- Windows / macOS / Linux

## 安装依赖

确保已安装 .NET 8.0 SDK:

```bash
# 检查 .NET 版本
dotnet --version
```

## 构建和运行

```bash
# 进入项目目录
cd subtitle_display

# 还原依赖
dotnet restore

# 运行应用
dotnet run
```

## 发布应用

### Windows 单文件发布

```bash
dotnet publish -c Release -r win-x64 --self-contained -p:PublishSingleFile=true
```

### macOS 单文件发布

```bash
dotnet publish -c Release -r osx-x64 --self-contained -p:PublishSingleFile=true
```

### Linux 单文件发布

```bash
dotnet publish -c Release -r linux-x64 --self-contained -p:PublishSingleFile=true
```

发布后的可执行文件位于 `bin/Release/net8.0/{runtime}/publish/` 目录。

## 使用说明

1. **启动应用**: 运行 `dotnet run` 或双击发布后的可执行文件
2. **配置 WebSocket 端点**: 默认 WebSocket 端点: `ws://localhost:10095`
3. **连接服务器**: 点击"连接"按钮连接到 ASR WebSocket 服务器
4. **查看字幕**: 字幕会实时显示在窗口中
5. **清空字幕**: 点击"清空"按钮清除所有字幕
6. **断开连接**: 点击"断开"按钮断开 WebSocket 连接

## WebSocket 消息格式

应用接收的 WebSocket 消息应为 JSON 格式:

```json
{
  "speaker_name": "说话人1",
  "text": "识别的文本内容",
  "is_final": true,
  "mode": "2pass-offline"
}
```

### 字段说明

- `speaker_name`: 说话人标识（字符串），也兼容 `speaker` 字段
- `text`: 识别的文本内容（字符串）
- `is_final`: 是否为最终结果（布尔值）
  - `false`: 临时结果，会继续累加
  - `true`: 最终结果，后续新内容会创建新行

## 配置选项

### 修改每行最大字符数

在 `MainWindow.axaml.cs` 中修改常量:

```csharp
private const int MaxCharsPerLine = 50; // 修改为你想要的值
```

### 修改字体大小

在 `MainWindow.axaml` 中修改样式:

```xml
<Style Selector="TextBlock.speaker">
    <Setter Property="FontSize" Value="32"/> <!-- 说话人字体大小 -->
</Style>
<Style Selector="TextBlock.content">
    <Setter Property="FontSize" Value="32"/> <!-- 内容字体大小 -->
</Style>
```

### 修改窗口大小

在 `MainWindow.axaml` 中修改窗口属性:

```xml
<Window Width="1200" Height="200" ...>
```

## 与 ASR 服务器集成

确保你的 ASR 服务器在 WebSocket 消息中包含以下信息:

```python
# Python 示例
import json

message = {
    "speaker_name": "Speaker1",  # 说话人标识
    "text": "识别的文本",         # 文本内容
    "is_final": False            # 是否最终结果
}

await websocket.send(json.dumps(message))
```

**注意**: 本项目的 ASR 系统已经自动发送正确格式的消息，无需额外配置。只需启动 ASR 服务器时启用说话人识别功能即可。

## 故障排除

### 无法连接到 WebSocket

- 检查 WebSocket URL 是否正确
- 确认 ASR 服务器正在运行
- 检查防火墙设置

### 字幕不显示

- 检查 WebSocket 消息格式是否正确
- 查看状态栏的错误信息
- 确认消息中包含 `speaker_name` (或 `speaker`) 和 `text` 字段
- 确认 ASR 服务器已启用说话人识别功能

### 应用无法启动

- 确认已安装 .NET 8.0 SDK
- 运行 `dotnet restore` 重新安装依赖
- 检查是否有端口冲突

## 技术栈

- **UI 框架**: Avalonia 11.0.10
- **WebSocket 客户端**: Websocket.Client 5.1.1
- **JSON 解析**: Newtonsoft.Json 13.0.3
- **目标框架**: .NET 8.0

## 许可证

与主项目保持一致

## 贡献

欢迎提交 Issue 和 Pull Request！
