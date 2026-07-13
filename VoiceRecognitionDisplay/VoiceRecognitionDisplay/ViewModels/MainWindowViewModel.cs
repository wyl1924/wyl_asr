using System;
using System.Collections.Generic;
using System.Linq;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Avalonia;
using Avalonia.Media;
using VoiceRecognitionDisplay.Models;
using VoiceRecognitionDisplay.Services;
using System.Threading.Tasks;

namespace VoiceRecognitionDisplay.ViewModels;

public partial class MainWindowViewModel : ViewModelBase
{
    private const int MaxBufferSize = 1000; // 最大缓冲区大小（行数）
    
    private readonly WebSocketService _webSocketService;
    private readonly ConfigurationManager _configManager;
    private readonly List<string> _chineseTextBuffer = new();
    private readonly List<string> _englishTextBuffer = new();
    private readonly List<string> _translationBuffer = new();
    private readonly object _bufferLock = new();
    private string _currentSpeaker = ""; // 当前说话人
    private string _lastSpeaker = ""; // 上一个说话人
    private string _onlineText = ""; // 在线文本缓存（用于2pass模式）
    private string _onlineTranslation = ""; // 在线翻译缓存（用于2pass模式）
    private bool _shouldClearBeforeNextMessage = false; // 标记是否需要在下次消息前清空

    public Func<(double Width, double Height)?>? ScreenSizeProvider { get; set; }
    
    /// <summary>
    /// 从文本末尾移除指定字符数的内容（参考 asr.ts 的逻辑）
    /// 支持多行文本，按字符数精确计算需要移除的内容
    /// </summary>
    private string RemoveOnlineTextFromEnd(string text, int charsToRemove)
    {
        if (string.IsNullOrEmpty(text) || charsToRemove <= 0)
        {
            return text;
        }
        
        // 按行分割文本
        var lines = text.Split('\n').ToList();
        var newLines = new List<string>();
        
        Console.WriteLine($"📊 需要移除的字符数: {charsToRemove}");
        
        // 从后往前处理每一行
        for (int i = lines.Count - 1; i >= 0 && charsToRemove > 0; i--)
        {
            string line = lines[i];
            // 移除时间戳前缀（如果存在）来获取纯文本
            string lineText = System.Text.RegularExpressions.Regex.Replace(line, @"^\d{2}:\d{2}:\d{2}\s*", "");
            
            Console.WriteLine($"  处理第{i}行: \"{line}\" -> 纯文本: \"{lineText}\" (长度={lineText.Length})");
            
            if (charsToRemove >= lineText.Length)
            {
                // 整行都要移除
                Console.WriteLine($"    移除整行 ({lineText.Length}字符)");
                charsToRemove -= lineText.Length;
            }
            else
            {
                // 只移除部分内容
                string keepText = lineText.Substring(0, lineText.Length - charsToRemove);
                // 提取时间戳
                var timestampMatch = System.Text.RegularExpressions.Regex.Match(line, @"^\d{2}:\d{2}:\d{2}");
                Console.WriteLine($"    部分移除: 保留 \"{keepText}\" (移除{charsToRemove}字符)");
                if (timestampMatch.Success && !string.IsNullOrEmpty(keepText))
                {
                    newLines.Insert(0, $"{timestampMatch.Value} {keepText}");
                }
                else if (!string.IsNullOrEmpty(keepText))
                {
                    newLines.Insert(0, keepText);
                }
                charsToRemove = 0;
            }
            
            if (charsToRemove == 0)
            {
                // 保留剩余的行
                for (int j = 0; j < i; j++)
                {
                    newLines.Insert(0, lines[j]);
                }
                break;
            }
        }
        
        return string.Join("\n", newLines);
    }
    
    // 显示属性
    [ObservableProperty]
    private string _speakerName = "";
    
    [ObservableProperty]
    private string _speakerIcon = "";
    
    [ObservableProperty]
    private string _chineseText = "";
    
    [ObservableProperty]
    private string _englishText = "";
    
    [ObservableProperty]
    private bool _showEnglish = false;
    
    // 样式属性
    [ObservableProperty]
    private double _cornerRadius = 10;

    public CornerRadius WindowCornerRadius => new(CornerRadius);
    
    [ObservableProperty]
    private IBrush _backgroundColor = new SolidColorBrush(Color.FromArgb(191, 0, 0, 0)); // 75% opacity
    
    [ObservableProperty]
    private FontFamily _fontFamily = new FontFamily("SimSun");
    
    [ObservableProperty]
    private double _fontSize = 14;
    
    [ObservableProperty]
    private IBrush _fontColor = Brushes.White;
    
    [ObservableProperty]
    private FontWeight _fontWeight = FontWeight.Normal;
    
    [ObservableProperty]
    private FontStyle _fontStyle = FontStyle.Normal;
    
    [ObservableProperty]
    private int _maxDisplayLines = 2;
    
    [ObservableProperty]
    private double _windowWidth = 800; // 实际像素宽度
    
    [ObservableProperty]
    private double _windowHeight = 200; // 实际像素高度
    
    // 横向滚动属性
    [ObservableProperty]
    private string _scrollingText = "";

    [ObservableProperty]
    private string _translationText = "";

    [ObservableProperty]
    private string _recognitionMode = "2pass-online"; // "2pass-online" 或 "2pass-offline"
    
    [ObservableProperty]
    private int _scrollSpeed = 60; // 滚动速度 (px/s)
    
    public MainWindowViewModel(WebSocketService webSocketService, ConfigurationManager configManager)
    {
        _webSocketService = webSocketService;
        _configManager = configManager;
        
        // 订阅 WebSocket 消息
        _webSocketService.TranscriptionReceived += OnTranscriptionReceived;
        _webSocketService.SettingsUpdateReceived += OnSettingsUpdateReceived;
        
        // 加载设置
        var settings = _configManager.LoadSettings();
        ApplySettings(settings);
        
        // 添加测试数据（用于演示）
        SpeakerName = "某某名";
        ChineseText = "习近平总书记曾调了一个关键词——职责使命：\"中央企业要充分认识负的职责使命，更好服务党和国家工作大局，服务经济社会高质量发展，服务保障和改善民生，勇担社会责任，为中国式现代化建设贡献更大力量。\"";
    }
    
    [RelayCommand]
    private void Share()
    {
        Console.WriteLine("[MainWindowViewModel] Share command executed");
        // 触发事件，由 MainWindow 处理
        ShareRequested?.Invoke(this, EventArgs.Empty);
    }
    
    [RelayCommand]
    private void OpenSettings()
    {
        Console.WriteLine("[MainWindowViewModel] OpenSettings command executed");
        // 触发事件，由 MainWindow 处理
        SettingsRequested?.Invoke(this, EventArgs.Empty);
    }
    
    [RelayCommand]
    private void Close()
    {
        Console.WriteLine("[MainWindowViewModel] Close command executed");
        // 触发事件，由 MainWindow 处理
        CloseRequested?.Invoke(this, EventArgs.Empty);
    }

    partial void OnCornerRadiusChanged(double value)
    {
        OnPropertyChanged(nameof(WindowCornerRadius));
    }
    
    private Avalonia.Controls.Window? GetWindow()
    {
        // 尝试从应用程序获取主窗口
        if (Avalonia.Application.Current?.ApplicationLifetime is Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop)
        {
            return desktop.MainWindow;
        }
        return null;
    }

    private (double Width, double Height)? GetScreenSize()
    {
        var providedSize = ScreenSizeProvider?.Invoke();
        if (providedSize is { } provided && provided.Width > 0 && provided.Height > 0)
        {
            return provided;
        }

        var window = GetWindow();
        if (window?.Screens?.Primary != null)
        {
            return (window.Screens.Primary.WorkingArea.Width, window.Screens.Primary.WorkingArea.Height);
        }

        var app = Avalonia.Application.Current;
        if (app?.ApplicationLifetime is Avalonia.Controls.ApplicationLifetimes.ISingleViewApplicationLifetime singleView)
        {
            var topLevel = Avalonia.Controls.TopLevel.GetTopLevel(singleView.MainView);
            if (topLevel?.Screens?.All != null && topLevel.Screens.All.Count > 0)
            {
                var primaryScreen = topLevel.Screens.All[0];
                return (primaryScreen.Bounds.Width, primaryScreen.Bounds.Height);
            }
        }

        return null;
    }
    
    public event EventHandler? ShareRequested;
    public event EventHandler? SettingsRequested;
    public event EventHandler? CloseRequested;
    
    public void OnTranscriptionReceived(object? sender, TranscriptionMessage message)
    {
        try
        {
            // 提取信息（使用标准格式）
            string speakerName = message.Speaker?.Name ?? message.SpeakerName ?? "说话人1";
            string chineseText = message.Content?.Chinese ?? message.Text ?? "";
            string englishText = message.Content?.English ?? "";
            string translation = message.Translation ?? "";
            string messageType = message.Type ?? message.Mode ?? "";

            Console.WriteLine($"🔍 [调试] message.Translation 原始值: '{message.Translation}'");
            Console.WriteLine($"🔍 [调试] translation 提取后: '{translation}'");
            Console.WriteLine($"🔍 [调试] translation 是否为空: {string.IsNullOrEmpty(translation)}");

            // 如果没有文本内容，跳过
            if (string.IsNullOrEmpty(chineseText))
            {
                Console.WriteLine("收到消息但中文文本为空，跳过");
                return;
            }

            Console.WriteLine($"收到转录消息 - 说话人: {speakerName}, 文本: {chineseText}, 翻译: '{translation}', 模式: {messageType}");

            // 检查是否在测试环境中（没有 UI 线程）
            if (Avalonia.Threading.Dispatcher.UIThread == null)
            {
                // 测试环境，直接调用
                ProcessTranscriptionMessage(speakerName, chineseText, englishText, translation, messageType);
            }
            else
            {
                // 确保在 UI 线程上更新
                Avalonia.Threading.Dispatcher.UIThread.Post(() =>
                {
                    ProcessTranscriptionMessage(speakerName, chineseText, englishText, translation, messageType);
                });
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"处理转录消息失败: {ex.Message}");
            Console.WriteLine($"堆栈跟踪: {ex.StackTrace}");
        }
    }
    
    /// <summary>
    /// 规范化说话人名称：将空字符串、"未知说话人"、"说话人1"等都视为同一个未知说话人
    /// </summary>
    private string NormalizeSpeakerName(string speakerName)
    {
        if (string.IsNullOrEmpty(speakerName) || 
            speakerName == "未知说话人" || 
            speakerName == "说话人1")
        {
            return "UNKNOWN_SPEAKER"; // 使用统一的内部标识
        }
        return speakerName;
    }
    
    private void ProcessTranscriptionMessage(string speakerName, string chineseText, string englishText, string translation, string messageType)
    {
        try
        {
            // 规范化说话人名称（用于内部比较）
            string normalizedSpeaker = NormalizeSpeakerName(speakerName);
            Console.WriteLine($"[ProcessTranscriptionMessage] 原始说话人: '{speakerName}', 规范化后: '{normalizedSpeaker}', 模式: '{messageType}'");
            
            // 更新说话人信息（显示原始名称）
            SpeakerName = speakerName;
            SpeakerIcon = "👤";
            
            // 更新识别模式
            if (!string.IsNullOrEmpty(messageType))
            {
                RecognitionMode = messageType.Contains("offline") ? "2pass-offline" : "2pass-online";
            }
            
            // 如果是2pass-online模式且没有说话人信息，使用最近的说话人
            if (messageType == "2pass-online" && string.IsNullOrEmpty(speakerName) && !string.IsNullOrEmpty(_lastSpeaker))
            {
                speakerName = _lastSpeaker;
                normalizedSpeaker = NormalizeSpeakerName(speakerName);
                Console.WriteLine($"[2pass-online] 使用上一个说话人: '{speakerName}'");
            }
            
            // 处理2pass-online模式：累积在线文本
            if (messageType == "2pass-online")
            {
                _onlineText += chineseText;
                _onlineTranslation += translation;
                Console.WriteLine($"[2pass-online] 累积在线文本: '{_onlineText}'");
                Console.WriteLine($"[2pass-online] 累积在线翻译: '{_onlineTranslation}'");
            }
            
            bool isFirstMessage = false;
            
            // 添加文本到缓冲区（线程安全）
            lock (_bufferLock)
            {
                Console.WriteLine($"[ProcessTranscriptionMessage] 当前缓冲区大小: {_chineseTextBuffer.Count}");
                Console.WriteLine($"[ProcessTranscriptionMessage] _shouldClearBeforeNextMessage: {_shouldClearBeforeNextMessage}");
                Console.WriteLine($"[ProcessTranscriptionMessage] _currentSpeaker: '{_currentSpeaker}'");
                
                // 检查是否需要在添加新消息前清空
                if (_shouldClearBeforeNextMessage)
                {
                    _chineseTextBuffer.Clear();
                    _englishTextBuffer.Clear();
                    _translationBuffer.Clear();
                    _shouldClearBeforeNextMessage = false;
                    isFirstMessage = true;
                    Console.WriteLine($"[行数超限] 清空缓冲区后添加新消息");
                }
                
                // 如果有说话人信息
                if (!string.IsNullOrEmpty(speakerName))
                {
                    _currentSpeaker = speakerName;
                    
                    // 检查是否是新的说话人（使用规范化后的名称比较）
                    bool isSpeakerChanged = false;
                    if (!string.IsNullOrEmpty(_lastSpeaker))
                    {
                        string normalizedLast = NormalizeSpeakerName(_lastSpeaker);
                        Console.WriteLine($"[ProcessTranscriptionMessage] 上一个说话人规范化: '{normalizedLast}', 新说话人规范化: '{normalizedSpeaker}'");
                        if (normalizedLast != normalizedSpeaker)
                        {
                            isSpeakerChanged = true;
                            Console.WriteLine($"[ProcessTranscriptionMessage] 检测到说话人切换");
                        }
                    }
                    
                    // 如果说话人与最近的不一致，或者是第一个2pass-offline输出
                    if (isSpeakerChanged || (messageType == "2pass-offline" && string.IsNullOrEmpty(_lastSpeaker)))
                    {
                        // 处理标点符号：如果新说话人的文本以标点符号开头，将标点符号移到上一个说话人末尾
                        string processedText = chineseText;
                        
                        if (!string.IsNullOrEmpty(chineseText) && _chineseTextBuffer.Count > 0)
                        {
                            char firstChar = chineseText[0];
                            string punctuationChars = "，。！？；：、,.!?;:";
                            
                            if (punctuationChars.Contains(firstChar))
                            {
                                // 将开头的标点符号添加到上一个说话人的文本末尾
                                int lastIndex = _chineseTextBuffer.Count - 1;
                                _chineseTextBuffer[lastIndex] += firstChar;
                                // 从当前文本中移除开头的标点符号
                                processedText = chineseText.Substring(1).Trim();
                                Console.WriteLine($"移动标点符号 '{firstChar}' 到上一个说话人");
                            }
                        }
                        
                        // 删除上一个说话人段落中的onlineText内容（仅在2pass-offline时）
                        if (messageType == "2pass-offline" && _chineseTextBuffer.Count > 0 && !string.IsNullOrEmpty(_onlineText))
                        {
                            int lastIndex = _chineseTextBuffer.Count - 1;
                            string previousText = _chineseTextBuffer[lastIndex];
                            Console.WriteLine($"🔍 上一个说话人段落: '{previousText}'");
                            Console.WriteLine($"🔍 需要移除的在线文本: '{_onlineText}'");

                            // 从末尾移除在线文本（按字符数精确计算）
                            string newText = RemoveOnlineTextFromEnd(previousText, _onlineText.Length);
                            _chineseTextBuffer[lastIndex] = newText;
                            Console.WriteLine($"✂️ 新说话人：从末尾移除在线文本: '{_onlineText}'");
                            Console.WriteLine($"📄 移除后的段落文本: '{newText}'");

                            // 同时移除翻译缓冲区中的在线翻译
                            if (_translationBuffer.Count > 0 && !string.IsNullOrEmpty(_onlineTranslation))
                            {
                                string previousTranslation = _translationBuffer[lastIndex];
                                string newTranslation = RemoveOnlineTextFromEnd(previousTranslation, _onlineTranslation.Length);
                                _translationBuffer[lastIndex] = newTranslation;
                                Console.WriteLine($"✂️ 新说话人：从末尾移除在线翻译: '{_onlineTranslation}'");
                            }
                        }

                        // 创建新的说话人段落
                        if (!string.IsNullOrEmpty(processedText))
                        {
                            _chineseTextBuffer.Add(processedText);
                            _translationBuffer.Add(translation);
                        }

                        _lastSpeaker = speakerName;
                        _onlineText = ""; // 只在创建新说话人段落时清空
                        _onlineTranslation = "";
                        isFirstMessage = true;
                        Console.WriteLine($"[新说话人] 创建新段落: '{processedText}'");
                    }
                    else
                    {
                        // 同一说话人
                        Console.WriteLine($"说话人一致，追加文本");

                        if (_chineseTextBuffer.Count > 0)
                        {
                            int lastIndex = _chineseTextBuffer.Count - 1;

                            // 如果是离线模式且有onlineText内容，需要先移除在线文本，再追加离线文本
                            if (messageType == "2pass-offline" && !string.IsNullOrEmpty(_onlineText))
                            {
                                string currentText = _chineseTextBuffer[lastIndex];
                                Console.WriteLine($"🔍 同一说话人-离线模式，当前段落文本: '{currentText}'");
                                Console.WriteLine($"🔍 同一说话人-需要移除的在线文本: '{_onlineText}'");

                                // 从末尾移除在线文本（按字符数精确计算）
                                string newText = RemoveOnlineTextFromEnd(currentText, _onlineText.Length);
                                _chineseTextBuffer[lastIndex] = newText;
                                Console.WriteLine($"✂️ 同一说话人：从末尾移除在线文本: '{_onlineText}'");
                                Console.WriteLine($"📄 移除后的段落文本: '{newText}'");

                                // 同时移除翻译缓冲区中的在线翻译
                                if (_translationBuffer.Count > 0 && !string.IsNullOrEmpty(_onlineTranslation))
                                {
                                    string currentTranslation = _translationBuffer[lastIndex];
                                    string newTranslation = RemoveOnlineTextFromEnd(currentTranslation, _onlineTranslation.Length);
                                    _translationBuffer[lastIndex] = newTranslation;
                                    Console.WriteLine($"✂️ 同一说话人：从末尾移除在线翻译: '{_onlineTranslation}'");
                                }

                                // 清空online缓存
                                _onlineText = "";
                                _onlineTranslation = "";
                            }

                            // 追加新文本（所有模式都追加）
                            if (messageType == "2pass-online" || messageType == "2pass-offline")
                            {
                                // 2pass模式：追加文本
                                _chineseTextBuffer[lastIndex] += chineseText;
                                if (_translationBuffer.Count > lastIndex)
                                {
                                    _translationBuffer[lastIndex] += translation;
                                }
                                Console.WriteLine($"📝 追加文本: '{chineseText}'");
                            }
                            else
                            {
                                // 其他情况：直接追加
                                _chineseTextBuffer[lastIndex] += chineseText;
                                if (_translationBuffer.Count > lastIndex)
                                {
                                    _translationBuffer[lastIndex] += translation;
                                }
                            }

                            Console.WriteLine($"📝 同一说话人，更新文本");
                        }
                        else
                        {
                            // 缓冲区为空，这是第一条消息
                            if (!string.IsNullOrEmpty(chineseText))
                            {
                                _chineseTextBuffer.Add(chineseText);
                                _translationBuffer.Add(translation);
                                Console.WriteLine($"📝 缓冲区为空，添加第一条消息: '{chineseText}'");
                            }
                        }
                    }
                }
                else if (messageType == "2pass-offline" && string.IsNullOrEmpty(_lastSpeaker))
                {
                    // 第一个2pass-offline输出且没有说话人信息，创建空说话人段落
                    if (!string.IsNullOrEmpty(chineseText))
                    {
                        _chineseTextBuffer.Add(chineseText);
                        _translationBuffer.Add(translation);
                    }
                    _onlineText = ""; // 创建新段落时清空
                    _onlineTranslation = "";
                    isFirstMessage = true;
                }

                // 处理英文文本
                if (!string.IsNullOrEmpty(englishText))
                {
                    _englishTextBuffer.Add(englishText);
                }

                // 检查缓冲区溢出（最大缓冲区大小）
                if (_chineseTextBuffer.Count > MaxBufferSize)
                {
                    _chineseTextBuffer.Clear();
                    _englishTextBuffer.Clear();
                    _translationBuffer.Clear();
                    _shouldClearBeforeNextMessage = false; // 重置标记
                }
            }
            
            // 更新显示文本
            ScrollToLatest();
            
            Console.WriteLine($"UI 已更新 - ScrollingText: {ScrollingText}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"处理消息失败: {ex.Message}");
            Console.WriteLine($"堆栈跟踪: {ex.StackTrace}");
        }
    }
    
    /// <summary>
    /// 处理从 WebSocket 接收到的设置更新
    /// </summary>
    private void OnSettingsUpdateReceived(object? sender, SettingsModel settings)
    {
        Console.WriteLine($"收到设置更新 - WindowWidth: {settings.WindowWidth}%, BackgroundColor: {settings.BackgroundColor}");
        
        // 在 UI 线程上应用设置
        Avalonia.Threading.Dispatcher.UIThread.Post(() =>
        {
            ApplySettings(settings);
        });
    }
    
    public void ApplySettings(SettingsModel settings)
    {
        Console.WriteLine($"=== ApplySettings START ===");
        Console.WriteLine($"BackgroundColor from settings: {settings.BackgroundColor}");
        Console.WriteLine($"BackgroundOpacity from settings: {settings.BackgroundOpacity}");
        Console.WriteLine($"WebSocketUrl from settings: {settings.WebSocketUrl}");

        // 更新 WebSocket 连接地址
        if (!string.IsNullOrEmpty(settings.WebSocketUrl) && _webSocketService.ServerUrl != settings.WebSocketUrl)
        {
            Console.WriteLine($"Updating WebSocket URL from '{_webSocketService.ServerUrl}' to '{settings.WebSocketUrl}'");
            _webSocketService.ServerUrl = settings.WebSocketUrl;
            
            // 如果当前已连接，需要重新连接以使用新地址
            if (_webSocketService.IsConnected)
            {
                Console.WriteLine("WebSocket is connected, reconnecting with new URL...");
                _ = Task.Run(async () =>
                {
                    try
                    {
                        await _webSocketService.DisconnectAsync();
                        await Task.Delay(500); // 等待断开完成
                        await _webSocketService.ConnectAsync();
                        Console.WriteLine("WebSocket reconnected successfully");
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"Failed to reconnect WebSocket: {ex.Message}");
                    }
                });
            }
        }

        // 确保在 UI 线程上执行
        Avalonia.Threading.Dispatcher.UIThread.Post(() =>
        {
            // 应用窗口设置 - 计算屏幕宽度的百分比
            var screenSize = GetScreenSize();
            double screenWidth;
            double screenHeight;

            if (screenSize is { } resolvedScreenSize)
            {
                screenWidth = resolvedScreenSize.Width;
                screenHeight = resolvedScreenSize.Height;
                Console.WriteLine($"[Screen] Screen size: {screenWidth}x{screenHeight}");
            }
            else
            {
                screenWidth = 1920;
                screenHeight = 1080;
                Console.WriteLine($"[Fallback] Using default screen size: {screenWidth}x{screenHeight}");
            }

            WindowWidth = screenWidth * settings.WindowWidth / 100.0;
            WindowHeight = screenHeight * settings.WindowHeight / 100.0;
            Console.WriteLine($"WindowWidth set to: {WindowWidth} (screen: {screenWidth}, percentage: {settings.WindowWidth}%)");
            Console.WriteLine($"WindowHeight set to: {WindowHeight} (screen: {screenHeight}, percentage: {settings.WindowHeight}%)");

            CornerRadius = settings.CornerRadius;
            Console.WriteLine($"CornerRadius set to: {CornerRadius}");
            OnPropertyChanged(nameof(CornerRadius)); // 强制触发属性变更通知

            // 应用背景色 - 强制创建新的 Brush 对象
            var bgColor = ParseHexColor(settings.BackgroundColor);
            Console.WriteLine($"Parsed background color: R={bgColor.R}, G={bgColor.G}, B={bgColor.B}, A={bgColor.A}");
            var opacity = (byte)(settings.BackgroundOpacity * 255 / 100);
            Console.WriteLine($"Calculated opacity byte: {opacity}");

            var newBackgroundColor = new SolidColorBrush(Color.FromArgb(opacity, bgColor.R, bgColor.G, bgColor.B));
            Console.WriteLine($"Created new brush with color: {newBackgroundColor.Color}");

            // 强制更新属性
            BackgroundColor = newBackgroundColor;
            Console.WriteLine($"BackgroundColor property updated");

            // 应用字体设置
            FontFamily = new FontFamily(settings.FontFamily);
            FontSize = settings.FontSize;
            Console.WriteLine($"Font: {settings.FontFamily}, Size: {FontSize}");

            // 处理字体颜色（支持"默认"值）
            if (settings.FontColor == "默认")
            {
                FontColor = Brushes.White;
                Console.WriteLine($"FontColor set to default (White)");
            }
            else
            {
                var fontColor = ParseHexColor(settings.FontColor);
                FontColor = new SolidColorBrush(fontColor);
                Console.WriteLine($"FontColor set to: {fontColor}");
            }

            FontWeight = settings.IsBold ? FontWeight.Bold : FontWeight.Normal;
            FontStyle = settings.IsItalic ? FontStyle.Italic : FontStyle.Normal;
            Console.WriteLine($"FontWeight: {FontWeight}, FontStyle: {FontStyle}");

            // 应用显示设置
            ShowEnglish = settings.ShowEnglish;
            MaxDisplayLines = settings.MaxDisplayLines;
            Console.WriteLine($"ShowEnglish: {ShowEnglish}, MaxDisplayLines: {MaxDisplayLines}");

            // 应用滚动设置
            ScrollSpeed = settings.ScrollSpeed;
            Console.WriteLine($"ScrollSpeed: {ScrollSpeed}");

            // 更新显示
            ScrollToLatest();

            Console.WriteLine($"=== ApplySettings END ===");
        });
    }
    
    public void ScrollToLatest()
    {
        try
        {
            lock (_bufferLock)
            {
                // 将所有文本片段连接成一个字符串（用空格分隔）
                var fullText = string.Join(" ", _chineseTextBuffer);

                Console.WriteLine($"[ScrollToLatest] 完整文本: '{fullText}'");
                Console.WriteLine($"[ScrollToLatest] 文本片段数: {_chineseTextBuffer.Count}");

                // 更新滚动文本
                ScrollingText = fullText;

                // 更新翻译文本
                TranslationText = string.Join(" ", _translationBuffer);
                Console.WriteLine($"🔍 [调试] _translationBuffer 内容: [{string.Join(", ", _translationBuffer.Select(t => $"'{t}'"))}]");
                Console.WriteLine($"🔍 [调试] TranslationText 更新为: '{TranslationText}'");
                Console.WriteLine($"🔍 [调试] TranslationText 长度: {TranslationText.Length}");

                // 更新传统显示文本（用换行符分隔）
                ChineseText = string.Join("\n", _chineseTextBuffer);

                if (ShowEnglish)
                {
                    EnglishText = string.Join("\n", _englishTextBuffer);
                }
                else
                {
                    EnglishText = "";
                }

                Console.WriteLine($"[ScrollToLatest] ScrollingText 属性值: '{ScrollingText}'");
                Console.WriteLine($"[ScrollToLatest] TranslationText 属性值: '{TranslationText}'");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"更新显示文本失败: {ex.Message}");
        }
    }
    
    private Color ParseHexColor(string hex)
    {
        try
        {
            hex = hex.TrimStart('#');
            if (hex.Length == 6)
            {
                return Color.FromRgb(
                    Convert.ToByte(hex.Substring(0, 2), 16),
                    Convert.ToByte(hex.Substring(2, 2), 16),
                    Convert.ToByte(hex.Substring(4, 2), 16)
                );
            }
        }
        catch
        {
            // 返回默认颜色
        }
        
        return Colors.Black;
    }
    
    public SettingsModel ToSettingsModel()
    {
        // 计算窗口宽度和高度百分比
        int widthPercentage = 80; // 默认值
        int heightPercentage = 30; // 默认值
        var screenSize = GetScreenSize();
        if (screenSize is { } resolvedScreenSize && resolvedScreenSize.Width > 0 && resolvedScreenSize.Height > 0)
        {
            var screenWidth = resolvedScreenSize.Width;
            var screenHeight = resolvedScreenSize.Height;
            widthPercentage = (int)(WindowWidth * 100 / screenWidth);
            heightPercentage = (int)(WindowHeight * 100 / screenHeight);
        }
        
        // 安全地从 IBrush 提取颜色（支持 SolidColorBrush 和 ImmutableSolidColorBrush）
        Color bgColor = Colors.Black;
        if (BackgroundColor is ISolidColorBrush solidBgBrush)
        {
            bgColor = solidBgBrush.Color;
        }
        
        Color fgColor = Colors.White;
        if (FontColor is ISolidColorBrush solidFgBrush)
        {
            fgColor = solidFgBrush.Color;
        }
        
        return new SettingsModel
        {
            WindowWidth = widthPercentage,
            WindowHeight = heightPercentage,
            CornerRadius = (int)CornerRadius,
            BackgroundColor = ColorToHex(bgColor),
            BackgroundOpacity = (int)(bgColor.A * 100 / 255),
            FontFamily = FontFamily.Name,
            FontSize = (int)FontSize,
            FontColor = ColorToHex(fgColor),
            IsBold = FontWeight == FontWeight.Bold,
            IsItalic = FontStyle == FontStyle.Italic,
            ShowEnglish = ShowEnglish,
            MaxDisplayLines = MaxDisplayLines,
            ScrollSpeed = ScrollSpeed,
            WebSocketUrl = _webSocketService.ServerUrl
        };
    }
    
    private string ColorToHex(Color color)
    {
        return $"#{color.R:X2}{color.G:X2}{color.B:X2}";
    }
    
    public string GetCurrentContent()
    {
        return $"说话人: {SpeakerName}\n\n中文:\n{ChineseText}\n\n英文:\n{EnglishText}";
    }
    
    public void ClearBuffer()
    {
        // 设置标记，在下次接收消息时清空
        _shouldClearBeforeNextMessage = true;
        Console.WriteLine("[ClearBuffer] 设置清空标记（下次消息时清空）");
    }
}
