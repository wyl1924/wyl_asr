# ASR 系统集成指南

本文档说明如何将滚动字幕应用与 ASR 系统集成。

## WebSocket 消息格式

ASR 系统通过 WebSocket 发送识别结果，字幕应用接收并显示这些结果。

### 标准消息格式

```json
{
  "mode": "2pass-offline",
  "text": "识别的文本内容",
  "wav_name": "microphone",
  "is_final": true,
  "speaker_name": "张三",
  "speaker_type": "registered",
  "speaker_confidence": 0.95,
  "timestamp": [[0, 1000], [1000, 2000]],
  "time_range": "00:00:00 - 00:00:02"
}
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `text` | string | ✅ | 识别的文本内容 |
| `speaker_name` | string | ⚠️ | 说话人名称（如果启用说话人识别） |
| `is_final` | boolean | ⚠️ | 是否为最终结果 |
| `mode` | string | ❌ | 识别模式 |
| `speaker_type` | string | ❌ | 说话人类型（registered/unknown） |
| `speaker_confidence` | number | ❌ | 说话人识别置信度 |
| `timestamp` | array | ❌ | 时间戳信息 |

### 字幕应用的处理逻辑

1. **接收消息**: 从 WebSocket 接收 JSON 消息
2. **解析字段**:
   - `speaker_name`: 说话人标识（如果没有则使用默认值 "说话人"）
   - `text`: 显示的文本内容
   - `is_final`: 是否为最终结果
3. **显示规则**:
   - 如果当前行的说话人相同且未满（< 50 字符），追加文本
   - 如果当前行已满或说话人不同，创建新行

## ASR 系统配置

### 启用说话人识别

要在字幕中显示说话人信息，需要在 ASR 服务器启动时启用说话人识别功能：

```bash
# 启用说话人验证
python main.py --enable-speaker-verification

# 或启用说话人分离
python main.py --enable-speaker-diarization

# 或启用串口功能（自动启用说话人识别）
python main.py --enable-serial
```

### WebSocket 端点

默认 WebSocket 端点: `ws://localhost:10095/`

可以通过以下参数修改：

```bash
python main.py --host 0.0.0.0 --port 10095
```

## 字幕应用配置

### 修改 WebSocket URL

在字幕应用界面中修改 WebSocket URL，或在代码中修改默认值：

```xml
<!-- MainWindow.axaml -->
<TextBox Name="WebSocketUrlTextBox" 
         Text="ws://localhost:10095/" 
         Width="300"/>
```

### 修改每行最大字符数

在 `MainWindow.axaml.cs` 中修改：

```csharp
private const int MaxCharsPerLine = 50; // 修改为你想要的值
```

## 测试集成

### 1. 启动 ASR 服务器

```bash
cd wyl_asr
python main.py --enable-speaker-verification
```

### 2. 启动字幕应用

```bash
cd subtitle_display
dotnet run
```

### 3. 连接并测试

1. 在字幕应用中点击"连接"按钮
2. 打开 ASR Web 界面 (http://localhost:10095)
3. 开始录音并说话
4. 观察字幕应用是否正确显示识别结果

## 自定义消息格式

如果你的 ASR 系统使用不同的消息格式，可以修改 `MainWindow.axaml.cs` 中的解析逻辑：

```csharp
private void OnMessageReceived(string message)
{
    try
    {
        var json = JObject.Parse(message);
        
        // 修改这里以适配你的消息格式
        var speaker = json["speaker"]?.ToString() ?? "说话人";
        var text = json["text"]?.ToString() ?? "";
        var isFinal = json["is_final"]?.ToObject<bool>() ?? false;
        
        if (string.IsNullOrWhiteSpace(text))
            return;

        Dispatcher.UIThread.Post(() => AddSubtitle(speaker, text, isFinal));
    }
    catch (Exception ex)
    {
        Dispatcher.UIThread.Post(() => UpdateStatus($"解析消息失败: {ex.Message}"));
    }
}
```

## 常见问题

### Q: 字幕不显示说话人名称

**A**: 检查以下几点：
1. ASR 服务器是否启用了说话人识别功能
2. WebSocket 消息中是否包含 `speaker_name` 字段
3. 查看字幕应用的状态栏是否有错误信息

### Q: 字幕显示延迟

**A**: 这是正常现象，因为：
- 在线 ASR 结果（`is_final: false`）会实时显示
- 离线 ASR 结果（`is_final: true`）需要等待音频处理完成
- 可以通过调整 ASR 服务器的 `offline_interval_ms` 参数来控制延迟

### Q: 字幕换行太频繁

**A**: 增加 `MaxCharsPerLine` 的值：

```csharp
private const int MaxCharsPerLine = 80; // 增加到 80 字符
```

### Q: 如何区分不同说话人

**A**: 字幕应用已经通过颜色区分：
- 说话人标识使用蓝色粗体
- 可以在 `MainWindow.axaml` 中修改样式

## 扩展功能

### 添加说话人颜色区分

修改 `MainWindow.axaml.cs` 中的 `CreateSubtitleLinePanel` 方法：

```csharp
private StackPanel CreateSubtitleLinePanel(SubtitleLine line)
{
    var panel = new StackPanel
    {
        Orientation = Avalonia.Layout.Orientation.Horizontal,
        Tag = line
    };

    // 根据说话人分配颜色
    var speakerColor = GetSpeakerColor(line.Speaker);
    
    var speakerText = new TextBlock
    {
        Text = $"[{line.Speaker}]",
        Classes = { "speaker" },
        Foreground = new SolidColorBrush(speakerColor)
    };

    var contentText = new TextBlock
    {
        Text = line.Content,
        Classes = { "content" }
    };

    panel.Children.Add(speakerText);
    panel.Children.Add(contentText);

    return panel;
}

private Color GetSpeakerColor(string speaker)
{
    // 根据说话人名称生成固定颜色
    var hash = speaker.GetHashCode();
    var colors = new[] {
        Color.FromRgb(33, 150, 243),  // 蓝色
        Color.FromRgb(76, 175, 80),   // 绿色
        Color.FromRgb(255, 152, 0),   // 橙色
        Color.FromRgb(156, 39, 176),  // 紫色
        Color.FromRgb(244, 67, 54),   // 红色
    };
    return colors[Math.Abs(hash) % colors.Length];
}
```

### 添加字幕导出功能

在 `MainWindow.axaml` 中添加导出按钮：

```xml
<Button Name="ExportButton" 
        Content="导出" 
        Click="OnExportClick"
        Width="80"/>
```

在 `MainWindow.axaml.cs` 中实现导出：

```csharp
private async void OnExportClick(object? sender, RoutedEventArgs e)
{
    var dialog = new SaveFileDialog
    {
        Title = "导出字幕",
        Filters = new List<FileDialogFilter>
        {
            new FileDialogFilter { Name = "文本文件", Extensions = { "txt" } },
            new FileDialogFilter { Name = "SRT字幕", Extensions = { "srt" } }
        }
    };

    var result = await dialog.ShowAsync(this);
    if (result != null)
    {
        var content = string.Join("\n", _subtitleLines.Select(
            line => $"[{line.Speaker}] {line.Content}"));
        await File.WriteAllTextAsync(result, content);
        UpdateStatus($"已导出到: {result}");
    }
}
```

## 技术支持

如有问题，请查看：
- ASR 系统文档: `../docs/`
- 字幕应用 README: `./README.md`
- 提交 Issue: GitHub Issues
