using Android.App;
using Android.Util;
using System;
using System.IO;

namespace VoiceRecognitionDisplay.Android;

internal static class AndroidDiagnostics
{
    internal const string WindowLogFileName = "window_debug.log";
    internal const string CrashLogFileName = "crash.log";
    internal const string InitLogFileName = "app_init.log";

    private const string DefaultPackageName = "com.smartmeeting.display";
    private const string LogDirectoryName = "Logs";
    private const string LogTag = "SmartMeeting";
    private static readonly object SyncRoot = new();

    internal static string GetLogDirectoryPath()
    {
        var context = Application.Context;
        var externalFilesDir = context?.GetExternalFilesDir(null)?.AbsolutePath;

        if (!string.IsNullOrWhiteSpace(externalFilesDir))
        {
            return Path.Combine(externalFilesDir, LogDirectoryName);
        }

        var packageName = context?.PackageName ?? DefaultPackageName;
        return Path.Combine("/sdcard", "Android", "data", packageName, "files", LogDirectoryName);
    }

    internal static string GetLogFilePath(string fileName)
    {
        return Path.Combine(GetLogDirectoryPath(), fileName);
    }

    internal static void ResetLog(string fileName, params string[] headerLines)
    {
        var logPath = EnsureLogPath(fileName);

        lock (SyncRoot)
        {
            File.WriteAllText(logPath, string.Empty);

            foreach (var headerLine in headerLines)
            {
                AppendLineInternal(logPath, headerLine, logToSystem: false);
            }
        }
    }

    internal static void WriteLine(string fileName, string message)
    {
        var logPath = EnsureLogPath(fileName);

        lock (SyncRoot)
        {
            AppendLineInternal(logPath, message, logToSystem: true);
        }
    }

    internal static void WriteException(string fileName, string context, Exception exception)
    {
        WriteLine(fileName, $"[{context}] {exception.GetType().FullName}: {exception.Message}");

        if (!string.IsNullOrWhiteSpace(exception.StackTrace))
        {
            WriteLine(fileName, exception.StackTrace);
        }

        if (exception.InnerException != null)
        {
            WriteLine(
                fileName,
                $"[{context}] Inner {exception.InnerException.GetType().FullName}: {exception.InnerException.Message}");

            if (!string.IsNullOrWhiteSpace(exception.InnerException.StackTrace))
            {
                WriteLine(fileName, exception.InnerException.StackTrace);
            }
        }
    }

    private static string EnsureLogPath(string fileName)
    {
        var logPath = GetLogFilePath(fileName);
        var logDirectory = Path.GetDirectoryName(logPath);

        if (!string.IsNullOrWhiteSpace(logDirectory))
        {
            Directory.CreateDirectory(logDirectory);
        }

        return logPath;
    }

    private static void AppendLineInternal(string logPath, string message, bool logToSystem)
    {
        var line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] {message}";
        File.AppendAllText(logPath, line + Environment.NewLine);

        try
        {
            Console.WriteLine(message);
        }
        catch
        {
            // Ignore console forwarding errors on Android.
        }

        if (logToSystem)
        {
            try
            {
                Log.Info(LogTag, message);
            }
            catch
            {
                // Ignore logcat forwarding errors.
            }
        }
    }
}
