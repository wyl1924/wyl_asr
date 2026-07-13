using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Data.Core;
using Avalonia.Data.Core.Plugins;
using Avalonia.Markup.Xaml;
using System;
using System.Linq;
using VoiceRecognitionDisplay.Services;
using VoiceRecognitionDisplay.ViewModels;
using VoiceRecognitionDisplay.Views;
using VoiceRecognitionDisplay.Models;

namespace VoiceRecognitionDisplay.iOS;

public partial class App : Application
{
    // 服务实例
    private ConfigurationManager? _configManager;
    private WebSocketService? _webSocketService;
    private ShareService? _shareService;
    private MainWindowViewModel? _mainViewModel;
    private bool _isInBackground = false;

    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is ISingleViewApplicationLifetime singleView)
        {
            // Avoid duplicate validations from both Avalonia and the CommunityToolkit.
            DisableAvaloniaDataAnnotationValidation();
            
            try
            {
                // 初始化服务
                InitializeServices();
                
                // 创建主窗口
                var mainWindow = new MainWindow(_mainViewModel!, _configManager!, _shareService!);
                singleView.MainView = mainWindow;
                
                // 连接到 WebSocket 服务器
                ConnectToWebSocket();
                
                Console.WriteLine("iOS 应用初始化完成");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"iOS 应用初始化失败: {ex}");
                throw;
            }
        }

        base.OnFrameworkInitializationCompleted();
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
            
            Console.WriteLine("iOS 服务初始化成功");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"iOS 服务初始化失败: {ex.Message}");
            throw;
        }
    }

    /// <summary>
    /// 连接到 WebSocket 服务器
    /// </summary>
    private async void ConnectToWebSocket()
    {
        try
        {
            if (_webSocketService != null && !_isInBackground)
            {
                await _webSocketService.ConnectAsync();
                Console.WriteLine("iOS WebSocket 连接已启动");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"iOS WebSocket 连接失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 应用进入后台时调用
    /// </summary>
    public async void OnEnterBackground()
    {
        _isInBackground = true;
        Console.WriteLine("iOS 应用进入后台，断开 WebSocket");
        
        try
        {
            // 保存当前设置
            if (_mainViewModel != null && _configManager != null)
            {
                var settings = _mainViewModel.ToSettingsModel();
                _configManager.SaveSettings(settings);
            }
            
            // 断开 WebSocket 连接以节省电量
            if (_webSocketService != null)
            {
                await _webSocketService.DisconnectAsync();
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"iOS 后台处理失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 应用恢复到前台时调用
    /// </summary>
    public void OnEnterForeground()
    {
        _isInBackground = false;
        Console.WriteLine("iOS 应用恢复到前台，重新连接 WebSocket");
        
        try
        {
            // 重新连接 WebSocket
            ConnectToWebSocket();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"iOS 前台处理失败: {ex.Message}");
        }
    }

    private void DisableAvaloniaDataAnnotationValidation()
    {
        var dataValidationPluginsToRemove =
            BindingPlugins.DataValidators.OfType<DataAnnotationsValidationPlugin>().ToArray();

        foreach (var plugin in dataValidationPluginsToRemove)
        {
            BindingPlugins.DataValidators.Remove(plugin);
        }
    }
}
