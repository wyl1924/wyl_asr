using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Data.Core;
using Avalonia.Data.Core.Plugins;
using System;
using System.Linq;
using Avalonia.Markup.Xaml;
using VoiceRecognitionDisplay.Services;
using VoiceRecognitionDisplay.ViewModels;
using VoiceRecognitionDisplay.Views;
using VoiceRecognitionDisplay.Models;

namespace VoiceRecognitionDisplay.Desktop;

public partial class App : Application
{
    // 服务实例
    private ConfigurationManager? _configManager;
    private WebSocketService? _webSocketService;
    private ShareService? _shareService;
    private MainWindowViewModel? _mainViewModel;

    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {
        // 设置全局异常处理器
        SetupExceptionHandlers();
        
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            // 设置关闭模式：只有主窗口关闭时才退出应用
            desktop.ShutdownMode = Avalonia.Controls.ShutdownMode.OnMainWindowClose;
            
            // Avoid duplicate validations from both Avalonia and the CommunityToolkit. 
            // More info: https://docs.avaloniaui.net/docs/guides/development-guides/data-validation#manage-validationplugins
            DisableAvaloniaDataAnnotationValidation();
            
            try
            {
                // 初始化服务
                InitializeServices();
                
                // 创建主窗口
                var mainWindow = new MainWindow(_mainViewModel!, _configManager!, _shareService!);
                desktop.MainWindow = mainWindow;
                
                // 加载窗口位置
                LoadWindowPosition(mainWindow);
                
                // 连接到 WebSocket 服务器
                ConnectToWebSocket();
                
                // 注册应用关闭事件
                desktop.ShutdownRequested += OnShutdownRequested;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"应用初始化失败: {ex}");
                LogException("初始化失败", ex);
                throw;
            }
        }

        base.OnFrameworkInitializationCompleted();
    }
    
    /// <summary>
    /// 设置全局异常处理器
    /// </summary>
    private void SetupExceptionHandlers()
    {
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
        System.Threading.Tasks.TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;
    }
    
    /// <summary>
    /// 处理未捕获的异常
    /// </summary>
    private void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        var exception = e.ExceptionObject as Exception;
        Console.WriteLine($"未处理的异常: {exception?.Message}");
        Console.WriteLine($"堆栈跟踪: {exception?.StackTrace}");
        
        LogException("未处理的异常", exception);
    }
    
    /// <summary>
    /// 处理未观察到的任务异常
    /// </summary>
    private void OnUnobservedTaskException(object? sender, System.Threading.Tasks.UnobservedTaskExceptionEventArgs e)
    {
        Console.WriteLine($"未观察到的任务异常: {e.Exception.Message}");
        
        // 标记为已处理，防止应用崩溃
        e.SetObserved();
        
        LogException("未观察到的任务异常", e.Exception);
    }
    
    /// <summary>
    /// 记录异常到文件
    /// </summary>
    private void LogException(string context, Exception? exception)
    {
        if (exception == null) return;
        
        try
        {
            var logPath = System.IO.Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "VoiceRecognitionDisplay", "Logs", "crash.log");
            
            var logDir = System.IO.Path.GetDirectoryName(logPath);
            if (!string.IsNullOrEmpty(logDir) && !System.IO.Directory.Exists(logDir))
            {
                System.IO.Directory.CreateDirectory(logDir);
            }
            
            var logEntry = $"\n[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {context}:\n{exception}\n";
            System.IO.File.AppendAllText(logPath, logEntry);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"记录异常失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 初始化所有服务
    /// </summary>
    private void InitializeServices()
    {
        try
        {
            // 创建配置管理器
            _configManager = new ConfigurationManager();
            
            // 创建 WebSocket 服务
            _webSocketService = new WebSocketService(_configManager);
            
            // 加载设置并应用到 WebSocket
            var settings = _configManager.LoadSettings();
            _webSocketService.ServerUrl = settings.WebSocketUrl;
            
            // 创建分享服务
            _shareService = new ShareService();
            
            // 创建主 ViewModel
            _mainViewModel = new MainWindowViewModel(_webSocketService, _configManager);
            
            Console.WriteLine("服务初始化成功");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"服务初始化失败: {ex.Message}");
            throw;
        }
    }

    /// <summary>
    /// 加载窗口位置
    /// </summary>
    private void LoadWindowPosition(MainWindow window)
    {
        try
        {
            var position = _configManager?.LoadWindowPosition();
            if (position != null && position.IsValid(1920, 1080)) // 假设最小屏幕尺寸
            {
                window.Position = new Avalonia.PixelPoint((int)position.X, (int)position.Y);
                window.Width = position.Width;
                window.Height = position.Height;
                Console.WriteLine($"窗口位置已恢复: ({position.X}, {position.Y})");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"加载窗口位置失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 连接到 WebSocket 服务器
    /// </summary>
    private async void ConnectToWebSocket()
    {
        try
        {
            if (_webSocketService != null)
            {
                await _webSocketService.ConnectAsync();
                Console.WriteLine("WebSocket 连接已启动");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"WebSocket 连接失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 应用关闭时的处理
    /// </summary>
    private async void OnShutdownRequested(object? sender, ShutdownRequestedEventArgs e)
    {
        try
        {
            Console.WriteLine("应用正在关闭...");
            
            // 保存当前设置
            if (_mainViewModel != null && _configManager != null)
            {
                var settings = _mainViewModel.ToSettingsModel();
                _configManager.SaveSettings(settings);
                Console.WriteLine("设置已保存");
            }
            
            // 保存窗口位置
            if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop && 
                desktop.MainWindow is MainWindow mainWindow &&
                _configManager != null)
            {
                var position = new WindowPosition
                {
                    X = mainWindow.Position.X,
                    Y = mainWindow.Position.Y,
                    Width = mainWindow.Width,
                    Height = mainWindow.Height
                };
                _configManager.SaveWindowPosition(position);
                Console.WriteLine("窗口位置已保存");
            }
            
            // 断开 WebSocket 连接
            if (_webSocketService != null)
            {
                await _webSocketService.DisconnectAsync();
                _webSocketService.Dispose();
                Console.WriteLine("WebSocket 连接已断开");
            }
            
            Console.WriteLine("应用已优雅关闭");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"关闭时发生错误: {ex.Message}");
        }
    }

    private void DisableAvaloniaDataAnnotationValidation()
    {
        // Get an array of plugins to remove
        var dataValidationPluginsToRemove =
            BindingPlugins.DataValidators.OfType<DataAnnotationsValidationPlugin>().ToArray();

        // remove each entry found
        foreach (var plugin in dataValidationPluginsToRemove)
        {
            BindingPlugins.DataValidators.Remove(plugin);
        }
    }
}