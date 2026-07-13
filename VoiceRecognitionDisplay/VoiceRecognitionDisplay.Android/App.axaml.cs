using Android.OS;
using Android.Runtime;
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

namespace VoiceRecognitionDisplay.Android;

public partial class App : Avalonia.Application
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
        try
        {
            SetupGlobalExceptionHandlers();
            InitializeAppLog();
            Console.WriteLine("=== App.OnFrameworkInitializationCompleted START ===");
            LogToFile("=== App.OnFrameworkInitializationCompleted START ===");

            if (ApplicationLifetime is ISingleViewApplicationLifetime singleView)
            {
                // Avoid duplicate validations from both Avalonia and the CommunityToolkit.
                DisableAvaloniaDataAnnotationValidation();
                Console.WriteLine("数据验证插件已禁用");
                LogToFile("数据验证插件已禁用");

                try
                {
                    // 初始化服务
                    Console.WriteLine("开始初始化服务...");
                    LogToFile("开始初始化服务...");
                    InitializeServices();
                    Console.WriteLine("服务初始化完成");
                    LogToFile("服务初始化完成");

                    // 创建主视图
                    Console.WriteLine("开始创建主视图...");
                    LogToFile("开始创建主视图...");
                    var startupAction = AndroidLaunchState.TakePendingAction();
                    var mainView = new MainView(_mainViewModel!, _configManager!, _shareService!, startupAction);
                    singleView.MainView = mainView;
                    Console.WriteLine("主视图创建完成");
                    LogToFile("主视图创建完成");

                    // 连接到 WebSocket 服务器
                    Console.WriteLine("开始连接 WebSocket...");
                    LogToFile("开始连接 WebSocket...");
                    ConnectToWebSocket();

                    Console.WriteLine("=== Android 应用初始化完成 ===");
                    LogToFile("=== Android 应用初始化完成 ===");
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"!!! Android 应用初始化失败: {ex}");
                    Console.WriteLine($"!!! 异常类型: {ex.GetType().Name}");
                    Console.WriteLine($"!!! 异常消息: {ex.Message}");
                    Console.WriteLine($"!!! 堆栈跟踪: {ex.StackTrace}");

                    LogToFile($"!!! Android 应用初始化失败 !!!");
                    LogToFile($"异常类型: {ex.GetType().Name}");
                    LogToFile($"异常消息: {ex.Message}");
                    LogToFile($"堆栈跟踪:\n{ex.StackTrace}");

                    if (ex.InnerException != null)
                    {
                        Console.WriteLine($"!!! 内部异常: {ex.InnerException.Message}");
                        LogToFile($"内部异常: {ex.InnerException.Message}");
                        LogToFile($"内部异常堆栈:\n{ex.InnerException.StackTrace}");
                    }

                    throw;
                }
            }
            else
            {
                var msg = $"!!! ApplicationLifetime 类型不匹配: {ApplicationLifetime?.GetType().Name}";
                Console.WriteLine(msg);
                LogToFile(msg);
            }

            base.OnFrameworkInitializationCompleted();
            Console.WriteLine("=== App.OnFrameworkInitializationCompleted END ===");
            LogToFile("=== App.OnFrameworkInitializationCompleted END ===");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"!!! OnFrameworkInitializationCompleted 顶层异常: {ex}");
            LogToFile($"!!! OnFrameworkInitializationCompleted 顶层异常: {ex}");
            throw;
        }
    }
    
    private void SetupGlobalExceptionHandlers()
    {
        AppDomain.CurrentDomain.UnhandledException += (sender, e) =>
        {
            var ex = e.ExceptionObject as Exception;
            if (ex != null)
            {
                AndroidDiagnostics.WriteException(AndroidDiagnostics.CrashLogFileName, "AppDomain.CurrentDomain.UnhandledException", ex);
            }
            else
            {
                var msg = "[全局未处理异常] ExceptionObject 不是 Exception";
                LogToFile(msg);
                Console.WriteLine(msg);
            }
        };
        
        System.Threading.Tasks.TaskScheduler.UnobservedTaskException += (sender, e) =>
        {
            AndroidDiagnostics.WriteException(AndroidDiagnostics.CrashLogFileName, "TaskScheduler.UnobservedTaskException", e.Exception);
            e.SetObserved();
        };

        AndroidEnvironment.UnhandledExceptionRaiser += (sender, e) =>
        {
            var wrappedException = new InvalidOperationException(
                $"Android runtime throwable: {e.Exception?.GetType().FullName}",
                e.Exception);

            AndroidDiagnostics.WriteException(
                AndroidDiagnostics.CrashLogFileName,
                "AndroidEnvironment.UnhandledExceptionRaiser",
                wrappedException);
        };
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
            
            Console.WriteLine("Android 服务初始化成功");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Android 服务初始化失败: {ex.Message}");
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
                Console.WriteLine("Android WebSocket 连接已启动");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Android WebSocket 连接失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 应用进入后台时调用
    /// </summary>
    public async void OnEnterBackground()
    {
        _isInBackground = true;
        Console.WriteLine("Android 应用进入后台，断开 WebSocket");
        
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
            Console.WriteLine($"Android 后台处理失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 应用恢复到前台时调用
    /// </summary>
    public void OnEnterForeground()
    {
        _isInBackground = false;
        Console.WriteLine("Android 应用恢复到前台，重新连接 WebSocket");
        
        try
        {
            // 重新连接 WebSocket
            ConnectToWebSocket();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Android 前台处理失败: {ex.Message}");
        }
    }

    private void InitializeAppLog()
    {
        var initLogPath = AndroidDiagnostics.GetLogFilePath(AndroidDiagnostics.InitLogFileName);
        var packageName = global::Android.App.Application.Context?.PackageName ?? "unknown";
        AndroidDiagnostics.ResetLog(
            AndroidDiagnostics.InitLogFileName,
            "=== Android app initialization log ===",
            $"Package: {packageName}",
            $"Device: {Build.Manufacturer} {Build.Model}",
            $"Android: {Build.VERSION.Release} (API {(int)Build.VERSION.SdkInt})",
            $"Log file: {initLogPath}");
    }

    private void LogToFile(string message)
    {
        try
        {
            AndroidDiagnostics.WriteLine(AndroidDiagnostics.InitLogFileName, $"[App] {message}");
        }
        catch
        {
            // 忽略日志写入错误
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
