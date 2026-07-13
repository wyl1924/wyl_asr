using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using VoiceRecognitionDisplay.Models;
using VoiceRecognitionDisplay.Services;

namespace VoiceRecognitionDisplay.ViewModels;

public partial class SettingsViewModel : ViewModelBase
{
    private readonly ConfigurationManager _configManager;

    public Func<string, Task<string?>>? FontColorPickerHandler { get; set; }
    public Func<string, Task<string?>>? BackgroundColorPickerHandler { get; set; }
    
    // 设置属性
    [ObservableProperty]
    private int _windowWidth = 80;
    
    [ObservableProperty]
    private int _cornerRadius = 10;
    
    [ObservableProperty]
    private string _backgroundColor = "#000000";
    
    [ObservableProperty]
    private Avalonia.Media.IBrush _backgroundColorBrush = new Avalonia.Media.SolidColorBrush(Avalonia.Media.Colors.Black);
    
    [ObservableProperty]
    private int _backgroundOpacity = 75;
    
    [ObservableProperty]
    private List<string> _availableFonts = new();
    
    [ObservableProperty]
    private string _selectedFont = "宋体";
    
    [ObservableProperty]
    private int _fontSize = 14;
    
    [ObservableProperty]
    private string _fontColor = "默认";
    
    [ObservableProperty]
    private Avalonia.Media.IBrush _fontColorBrush = new Avalonia.Media.SolidColorBrush(Avalonia.Media.Colors.White);
    
    [ObservableProperty]
    private bool _isBold = false;
    
    [ObservableProperty]
    private bool _isItalic = false;
    
    [ObservableProperty]
    private bool _showEnglish = false;
    
    [ObservableProperty]
    private int _maxDisplayLines = 2;
    
    [ObservableProperty]
    private string _webSocketUrl = "ws://192.168.2.169:10095/";
    
    // WebSocket 连接设置（分离的字段）
    [ObservableProperty]
    private bool _useSecureConnection = false;
    
    [ObservableProperty]
    private string _serverIp = "192.168.2.169";
    
    [ObservableProperty]
    private string _serverPort = "10095";
    
    // 验证错误属性
    [ObservableProperty]
    private string _windowWidthError = "";
    
    [ObservableProperty]
    private string _cornerRadiusError = "";
    
    [ObservableProperty]
    private string _fontSizeError = "";
    
    [ObservableProperty]
    private string _maxDisplayLinesError = "";
    
    [ObservableProperty]
    private string _webSocketUrlError = "";
    
    [ObservableProperty]
    private string _serverIpError = "";
    
    [ObservableProperty]
    private string _serverPortError = "";
    
    [ObservableProperty]
    private string _backgroundColorError = "";
    
    [ObservableProperty]
    private string _fontColorError = "";
    
    public SettingsViewModel(ConfigurationManager configManager)
    {
        _configManager = configManager;
        
        // 加载可用字体
        LoadAvailableFonts();
        
        // 监听 IP 和端口变化，自动更新 WebSocketUrl
        PropertyChanged += (s, e) =>
        {
            if (e.PropertyName == nameof(UseSecureConnection) || 
                e.PropertyName == nameof(ServerIp) || 
                e.PropertyName == nameof(ServerPort))
            {
                UpdateWebSocketUrl();
            }
        };
    }
    
    private void UpdateWebSocketUrl()
    {
        var protocol = UseSecureConnection ? "wss://" : "ws://";
        var ip = string.IsNullOrWhiteSpace(ServerIp) ? "192.168.2.169" : ServerIp.Trim();
        var port = string.IsNullOrWhiteSpace(ServerPort) ? "10095" : ServerPort.Trim();
        WebSocketUrl = $"{protocol}{ip}:{port}/";
    }
    
    partial void OnBackgroundColorChanged(string value)
    {
        try
        {
            var color = Avalonia.Media.Color.Parse(value);
            BackgroundColorBrush = new Avalonia.Media.SolidColorBrush(color);
        }
        catch
        {
            // 无效颜色，保持当前值
        }
    }
    
    partial void OnFontColorChanged(string value)
    {
        if (value == "默认")
        {
            FontColorBrush = new Avalonia.Media.SolidColorBrush(Avalonia.Media.Colors.White);
        }
        else
        {
            try
            {
                var color = Avalonia.Media.Color.Parse(value);
                FontColorBrush = new Avalonia.Media.SolidColorBrush(color);
            }
            catch
            {
                // 无效颜色，保持当前值
            }
        }
    }
    
    private void LoadAvailableFonts()
    {
        // 获取系统字体（使用中文名称以匹配 SettingsModel）
        AvailableFonts = new List<string>
        {
            "宋体",        // SimSun
            "黑体",        // SimHei
            "微软雅黑",    // Microsoft YaHei
            "楷体",        // KaiTi
            "仿宋",        // FangSong
            "Arial",
            "Times New Roman",
            "Courier New"
        };
    }
    
    [RelayCommand]
    private void ToggleBold()
    {
        IsBold = !IsBold;
    }
    
    [RelayCommand]
    private void ToggleItalic()
    {
        IsItalic = !IsItalic;
    }
    
    [RelayCommand]
    private async Task OpenColorPicker()
    {
        if (FontColorPickerHandler != null)
        {
            var inlineResult = await FontColorPickerHandler(FontColor == "默认" ? "#FFFFFF" : FontColor);
            if (inlineResult != null)
            {
                FontColor = inlineResult;
            }

            return;
        }

        var mainWindow = GetMainWindow();
        if (mainWindow == null)
            return;
            
        var dialog = new Views.ColorPickerDialog
        {
            DataContext = new ColorPickerViewModel(FontColor == "默认" ? "#FFFFFF" : FontColor)
        };
        
        var result = await dialog.ShowDialog<string?>(mainWindow);
        
        if (result != null)
        {
            FontColor = result;
        }
    }
    
    [RelayCommand]
    private async Task OpenBackgroundColorPicker()
    {
        if (BackgroundColorPickerHandler != null)
        {
            var inlineResult = await BackgroundColorPickerHandler(BackgroundColor);
            if (inlineResult != null)
            {
                BackgroundColor = inlineResult;
            }

            return;
        }

        var mainWindow = GetMainWindow();
        if (mainWindow == null)
            return;
            
        var dialog = new Views.ColorPickerDialog
        {
            DataContext = new ColorPickerViewModel(BackgroundColor)
        };
        
        var result = await dialog.ShowDialog<string?>(mainWindow);
        
        if (result != null)
        {
            BackgroundColor = result;
        }
    }
    
    private Avalonia.Controls.Window? GetMainWindow()
    {
        // Try to get the main window from the application
        if (Avalonia.Application.Current?.ApplicationLifetime is Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop)
        {
            return desktop.MainWindow;
        }
        return null;
    }
    
    [RelayCommand]
    private void Save()
    {
        Console.WriteLine("=== Save Command Triggered ===");
        Console.WriteLine($"Current BackgroundColor: {BackgroundColor}");
        Console.WriteLine($"Current BackgroundOpacity: {BackgroundOpacity}");
        
        if (ValidateAll())
        {
            Console.WriteLine("Validation passed");
            var settings = ToSettingsModel();
            Console.WriteLine($"Settings model created - BackgroundColor: {settings.BackgroundColor}, Opacity: {settings.BackgroundOpacity}");
            
            _configManager.SaveSettings(settings);
            Console.WriteLine("Settings saved to file");
            
            // 触发保存事件，由窗口处理关闭
            Console.WriteLine("Invoking SettingsSaved event");
            SettingsSaved?.Invoke(this, settings);
            Console.WriteLine("=== Save Command Complete ===");
        }
        else
        {
            Console.WriteLine("Validation failed");
        }
    }
    
    [RelayCommand]
    private void Cancel()
    {
        // 触发取消事件，由窗口处理关闭
        SettingsCancelled?.Invoke(this, EventArgs.Empty);
    }
    
    public event EventHandler<SettingsModel>? SettingsSaved;
    public event EventHandler? SettingsCancelled;
    
    public bool ValidateAll()
    {
        bool isValid = true;
        
        // 验证界面宽
        if (WindowWidth < 10 || WindowWidth > 100)
        {
            WindowWidthError = "界面宽必须在 10-100 之间";
            isValid = false;
        }
        else
        {
            WindowWidthError = "";
        }
        
        // 验证圆角
        if (CornerRadius < 0 || CornerRadius > 100)
        {
            CornerRadiusError = "圆角必须在 0-100 之间";
            isValid = false;
        }
        else
        {
            CornerRadiusError = "";
        }
        
        // 验证字体大小
        if (FontSize < 1 || FontSize > 100)
        {
            FontSizeError = "字体大小必须在 1-100 之间";
            isValid = false;
        }
        else
        {
            FontSizeError = "";
        }
        
        // 验证显示行数
        if (MaxDisplayLines < 1 || MaxDisplayLines > 20)
        {
            MaxDisplayLinesError = "显示行数必须在 1-20 之间";
            isValid = false;
        }
        else
        {
            MaxDisplayLinesError = "";
        }
        
        // 验证背景色
        if (!IsValidHexColor(BackgroundColor))
        {
            BackgroundColorError = "背景色格式无效，请使用十六进制格式（如 #000000）";
            isValid = false;
        }
        else
        {
            BackgroundColorError = "";
        }
        
        // 验证字体颜色
        if (FontColor != "默认" && !IsValidHexColor(FontColor))
        {
            FontColorError = "字体颜色格式无效，请使用十六进制格式（如 #FFFFFF）或输入\"默认\"";
            isValid = false;
        }
        else
        {
            FontColorError = "";
        }
        
        // 验证服务器 IP
        if (string.IsNullOrWhiteSpace(ServerIp))
        {
            ServerIpError = "服务器 IP 不能为空";
            isValid = false;
        }
        else if (!IsValidIpAddress(ServerIp))
        {
            ServerIpError = "IP 地址格式无效（例如：127.0.0.1 或 192.168.1.100）";
            isValid = false;
        }
        else
        {
            ServerIpError = "";
        }
        
        // 验证服务器端口
        if (string.IsNullOrWhiteSpace(ServerPort))
        {
            ServerPortError = "端口号不能为空";
            isValid = false;
        }
        else if (!int.TryParse(ServerPort, out int port) || port < 1 || port > 65535)
        {
            ServerPortError = "端口号必须在 1-65535 之间";
            isValid = false;
        }
        else
        {
            ServerPortError = "";
        }
        
        // 验证 WebSocket URL（自动生成的）
        if (!IsValidWebSocketUrl(WebSocketUrl))
        {
            WebSocketUrlError = "WebSocket 地址格式无效";
            isValid = false;
        }
        else
        {
            WebSocketUrlError = "";
        }
        
        return isValid;
    }
    
    public void LoadSettings(SettingsModel settings)
    {
        WindowWidth = settings.WindowWidth;
        CornerRadius = settings.CornerRadius;
        BackgroundColor = settings.BackgroundColor;
        BackgroundOpacity = settings.BackgroundOpacity;
        SelectedFont = settings.FontFamily;
        FontSize = settings.FontSize;
        FontColor = settings.FontColor;
        IsBold = settings.IsBold;
        IsItalic = settings.IsItalic;
        ShowEnglish = settings.ShowEnglish;
        MaxDisplayLines = settings.MaxDisplayLines;
        WebSocketUrl = settings.WebSocketUrl;
        
        // 解析 WebSocket URL 到独立字段
        ParseWebSocketUrl(settings.WebSocketUrl);
    }
    
    private void ParseWebSocketUrl(string url)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(url))
            {
                UseSecureConnection = false;
                ServerIp = "192.168.2.169";
                ServerPort = "10095";
                return;
            }
            
            var uri = new Uri(url);
            UseSecureConnection = uri.Scheme == "wss";
            ServerIp = uri.Host;
            ServerPort = uri.Port.ToString();
        }
        catch
        {
            // 解析失败，使用默认值
            UseSecureConnection = false;
            ServerIp = "192.168.2.169";
            ServerPort = "10095";
        }
    }
    
    public SettingsModel ToSettingsModel()
    {
        return new SettingsModel
        {
            WindowWidth = WindowWidth,
            CornerRadius = CornerRadius,
            BackgroundColor = BackgroundColor,
            BackgroundOpacity = BackgroundOpacity,
            FontFamily = SelectedFont,
            FontSize = FontSize,
            FontColor = FontColor,
            IsBold = IsBold,
            IsItalic = IsItalic,
            ShowEnglish = ShowEnglish,
            MaxDisplayLines = MaxDisplayLines,
            WebSocketUrl = WebSocketUrl
        };
    }
    
    private bool IsValidHexColor(string color)
    {
        if (string.IsNullOrWhiteSpace(color))
            return false;
            
        color = color.TrimStart('#');
        return color.Length == 6 && color.All(c => 
            (c >= '0' && c <= '9') || 
            (c >= 'A' && c <= 'F') || 
            (c >= 'a' && c <= 'f'));
    }
    
    private bool IsValidWebSocketUrl(string url)
    {
        if (string.IsNullOrWhiteSpace(url))
            return false;
            
        return url.StartsWith("ws://", StringComparison.OrdinalIgnoreCase) ||
               url.StartsWith("wss://", StringComparison.OrdinalIgnoreCase);
    }
    
    private bool IsValidIpAddress(string ip)
    {
        if (string.IsNullOrWhiteSpace(ip))
            return false;
        
        // 支持 IPv4 地址和主机名
        // IPv4 格式验证
        var parts = ip.Split('.');
        if (parts.Length == 4)
        {
            return parts.All(part => 
                int.TryParse(part, out int num) && num >= 0 && num <= 255);
        }
        
        // 主机名格式验证（简单检查）
        return ip.All(c => char.IsLetterOrDigit(c) || c == '.' || c == '-') && 
               !ip.StartsWith("-") && !ip.EndsWith("-");
    }
}
