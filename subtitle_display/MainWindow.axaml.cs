using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Threading;
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Websocket.Client;
using Newtonsoft.Json.Linq;

namespace SubtitleDisplay;

public partial class MainWindow : Window
{
    private WebsocketClient? _wsClient;
    private readonly List<SubtitleLine> _subtitleLines = new();
    private const int MaxCharsPerLine = 50; // 每行最大字符数
    
    public MainWindow()
    {
        InitializeComponent();
    }

    private async void OnConnectClick(object? sender, RoutedEventArgs e)
    {
        try
        {
            var url = WebSocketUrlTextBox.Text ?? "ws://localhost:10095/";
            
            if (_wsClient != null)
            {
                await DisconnectWebSocket();
            }

            _wsClient = new WebsocketClient(new Uri(url));
            
            _wsClient.ReconnectTimeout = TimeSpan.FromSeconds(30);
            _wsClient.MessageReceived.Subscribe(msg => OnMessageReceived(msg.Text));
            _wsClient.DisconnectionHappened.Subscribe(info => 
                Dispatcher.UIThread.Post(() => UpdateStatus($"连接断开: {info.Type}")));
            
            await _wsClient.Start();
            
            UpdateStatus("已连接");
            ConnectButton.IsEnabled = false;
            DisconnectButton.IsEnabled = true;
        }
        catch (Exception ex)
        {
            UpdateStatus($"连接失败: {ex.Message}");
        }
    }

    private async void OnDisconnectClick(object? sender, RoutedEventArgs e)
    {
        await DisconnectWebSocket();
    }

    private async Task DisconnectWebSocket()
    {
        if (_wsClient != null)
        {
            await _wsClient.Stop(System.Net.WebSockets.WebSocketCloseStatus.NormalClosure, "User disconnected");
            _wsClient.Dispose();
            _wsClient = null;
        }
        
        UpdateStatus("未连接");
        ConnectButton.IsEnabled = true;
        DisconnectButton.IsEnabled = false;
    }

    private void OnClearClick(object? sender, RoutedEventArgs e)
    {
        _subtitleLines.Clear();
        SubtitlePanel.Children.Clear();
    }

    private void OnMessageReceived(string message)
    {
        try
        {
            var json = JObject.Parse(message);
            
            // 解析消息 - 优先使用 speaker_name，其次使用 speaker
            var speaker = json["speaker_name"]?.ToString() 
                         ?? json["speaker"]?.ToString() 
                         ?? "说话人";
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

    private void AddSubtitle(string speaker, string text, bool isFinal)
    {
        // 查找当前说话人的最后一行
        SubtitleLine? currentLine = null;
        
        if (_subtitleLines.Count > 0)
        {
            var lastLine = _subtitleLines[^1];
            if (lastLine.Speaker == speaker && !lastLine.IsFinal)
            {
                currentLine = lastLine;
            }
        }

        if (currentLine == null)
        {
            // 创建新行
            currentLine = new SubtitleLine
            {
                Speaker = speaker,
                Content = text,
                IsFinal = isFinal
            };
            _subtitleLines.Add(currentLine);
            
            var linePanel = CreateSubtitleLinePanel(currentLine);
            SubtitlePanel.Children.Add(linePanel);
        }
        else
        {
            // 累加到现有行
            var newContent = currentLine.Content + text;
            
            // 检查是否超过每行最大字符数
            if (newContent.Length > MaxCharsPerLine)
            {
                // 标记当前行为完成
                currentLine.IsFinal = true;
                UpdateSubtitleLine(currentLine);
                
                // 创建新行
                var newLine = new SubtitleLine
                {
                    Speaker = speaker,
                    Content = text,
                    IsFinal = isFinal
                };
                _subtitleLines.Add(newLine);
                
                var linePanel = CreateSubtitleLinePanel(newLine);
                SubtitlePanel.Children.Add(linePanel);
            }
            else
            {
                // 更新现有行
                currentLine.Content = newContent;
                currentLine.IsFinal = isFinal;
                UpdateSubtitleLine(currentLine);
            }
        }

        // 自动滚动到底部
        SubtitleScrollViewer.ScrollToEnd();
    }

    private StackPanel CreateSubtitleLinePanel(SubtitleLine line)
    {
        var panel = new StackPanel
        {
            Orientation = Avalonia.Layout.Orientation.Horizontal,
            Tag = line
        };

        var speakerText = new TextBlock
        {
            Text = $"[{line.Speaker}]",
            Classes = { "speaker" }
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

    private void UpdateSubtitleLine(SubtitleLine line)
    {
        // 查找对应的UI元素并更新
        foreach (var child in SubtitlePanel.Children)
        {
            if (child is StackPanel panel && panel.Tag == line)
            {
                if (panel.Children.Count >= 2 && panel.Children[1] is TextBlock contentText)
                {
                    contentText.Text = line.Content;
                }
                break;
            }
        }
    }

    private void UpdateStatus(string status)
    {
        StatusTextBlock.Text = status;
    }

    protected override async void OnClosing(WindowClosingEventArgs e)
    {
        await DisconnectWebSocket();
        base.OnClosing(e);
    }
}

public class SubtitleLine
{
    public string Speaker { get; set; } = "";
    public string Content { get; set; } = "";
    public bool IsFinal { get; set; }
}
