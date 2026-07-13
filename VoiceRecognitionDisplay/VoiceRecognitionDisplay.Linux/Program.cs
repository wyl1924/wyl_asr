using Avalonia;
using System;
using System.Threading.Tasks;

namespace VoiceRecognitionDisplay.Linux;

class Program
{
    // Initialization code. Don't use any Avalonia, third-party APIs or any
    // SynchronizationContext-reliant code before AppMain is called: things aren't initialized
    // yet and stuff might break.
    [STAThread]
    public static void Main(string[] args)
    {
        // 设置全局异常处理器
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
        TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;
        
        try
        {
            BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"应用程序崩溃: {ex}");
            LogException("应用程序崩溃", ex);
            throw;
        }
    }

    private static void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        var exception = e.ExceptionObject as Exception;
        Console.WriteLine($"未处理的异常: {exception?.Message}");
        Console.WriteLine($"堆栈跟踪: {exception?.StackTrace}");
        
        LogException("未处理的异常", exception);
    }

    private static void OnUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        Console.WriteLine($"未观察到的任务异常: {e.Exception.Message}");
        
        // 标记为已处理，防止应用崩溃
        e.SetObserved();
        
        LogException("未观察到的任务异常", e.Exception);
    }

    private static void LogException(string context, Exception? exception)
    {
        if (exception == null) return;
        
        try
        {
            var logPath = System.IO.Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                ".config", "VoiceRecognitionDisplay", "Logs", "crash.log");
            
            var logDir = System.IO.Path.GetDirectoryName(logPath);
            if (!string.IsNullOrEmpty(logDir) && !System.IO.Directory.Exists(logDir))
            {
                System.IO.Directory.CreateDirectory(logDir);
            }
            
            System.IO.File.AppendAllText(logPath, 
                $"\n[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {context}:\n{exception}\n");
        }
        catch { }
    }

    // Avalonia configuration, don't remove; also used by visual designer.
    public static AppBuilder BuildAvaloniaApp()
        => AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .WithInterFont()
            .LogToTrace();
}
