using Avalonia;
using Avalonia.iOS;
using Foundation;
using UIKit;
using System;

namespace VoiceRecognitionDisplay.iOS;

[Register("AppDelegate")]
public class AppDelegate : AvaloniaAppDelegate<App>
{
    public override bool FinishedLaunching(UIApplication application, NSDictionary launchOptions)
    {
        // 设置全局异常处理器
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
        System.Threading.Tasks.TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;
        
        Console.WriteLine("iOS 应用已启动");
        
        return base.FinishedLaunching(application, launchOptions);
    }

    public override void OnActivated(UIApplication application)
    {
        base.OnActivated(application);
        Console.WriteLine("iOS 应用已激活（前台）");
        
        // 通知应用恢复到前台
        if (Avalonia.Application.Current is App app)
        {
            app.OnEnterForeground();
        }
    }

    public override void OnResignActivation(UIApplication application)
    {
        base.OnResignActivation(application);
        Console.WriteLine("iOS 应用即将失去激活状态");
    }

    public override void DidEnterBackground(UIApplication application)
    {
        base.DidEnterBackground(application);
        Console.WriteLine("iOS 应用已进入后台");
        
        // 通知应用进入后台
        if (Avalonia.Application.Current is App app)
        {
            app.OnEnterBackground();
        }
    }

    public override void WillEnterForeground(UIApplication application)
    {
        base.WillEnterForeground(application);
        Console.WriteLine("iOS 应用即将进入前台");
    }

    public override void WillTerminate(UIApplication application)
    {
        Console.WriteLine("iOS 应用即将终止");
        
        // 清理资源
        AppDomain.CurrentDomain.UnhandledException -= OnUnhandledException;
        System.Threading.Tasks.TaskScheduler.UnobservedTaskException -= OnUnobservedTaskException;
        
        base.WillTerminate(application);
    }

    private void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        var exception = e.ExceptionObject as Exception;
        Console.WriteLine($"未处理的异常: {exception?.Message}");
        Console.WriteLine($"堆栈跟踪: {exception?.StackTrace}");
        
        LogException("未处理的异常", exception);
    }

    private void OnUnobservedTaskException(object? sender, System.Threading.Tasks.UnobservedTaskExceptionEventArgs e)
    {
        Console.WriteLine($"未观察到的任务异常: {e.Exception.Message}");
        
        // 标记为已处理，防止应用崩溃
        e.SetObserved();
        
        LogException("未观察到的任务异常", e.Exception);
    }

    private void LogException(string context, Exception? exception)
    {
        if (exception == null) return;
        
        try
        {
            var documentsPath = NSFileManager.DefaultManager.GetUrls(
                NSSearchPathDirectory.DocumentDirectory, 
                NSSearchPathDomain.User)[0].Path;
            
            var logPath = System.IO.Path.Combine(documentsPath, "Logs", "crash.log");
            
            var logDir = System.IO.Path.GetDirectoryName(logPath);
            if (!string.IsNullOrEmpty(logDir) && !System.IO.Directory.Exists(logDir))
            {
                System.IO.Directory.CreateDirectory(logDir);
            }
            
            System.IO.File.AppendAllText(logPath, 
                $"\n[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {context}:\n{exception}\n");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"记录异常失败: {ex.Message}");
        }
    }

    protected override AppBuilder CustomizeAppBuilder(AppBuilder builder)
    {
        return base.CustomizeAppBuilder(builder)
            .WithInterFont()
            .LogToTrace();
    }
}
