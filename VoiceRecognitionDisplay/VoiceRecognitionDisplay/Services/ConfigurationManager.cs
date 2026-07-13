using System;
using System.IO;
using System.Text.Json;
using VoiceRecognitionDisplay.Models;

namespace VoiceRecognitionDisplay.Services;

/// <summary>
/// 配置管理器，负责加载和保存应用设置
/// </summary>
public class ConfigurationManager
{
    private const string AppName = "VoiceRecognitionDisplay";
    private const string SettingsFileName = "settings.json";
    private const string PositionFileName = "position.json";

    /// <summary>
    /// 加载设置
    /// </summary>
    public SettingsModel LoadSettings()
    {
        try
        {
            var settingsPath = GetSettingsFilePath();
            
            if (!File.Exists(settingsPath))
            {
                return new SettingsModel();
            }

            var json = File.ReadAllText(settingsPath);
            var settings = JsonSerializer.Deserialize<SettingsModel>(json);
            
            return settings ?? new SettingsModel();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"加载设置失败: {ex.Message}");
            return new SettingsModel();
        }
    }

    /// <summary>
    /// 保存设置
    /// </summary>
    public void SaveSettings(SettingsModel settings)
    {
        try
        {
            var settingsPath = GetSettingsFilePath();
            var directory = Path.GetDirectoryName(settingsPath);
            
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }

            var options = new JsonSerializerOptions
            {
                WriteIndented = true
            };
            
            var json = JsonSerializer.Serialize(settings, options);
            File.WriteAllText(settingsPath, json);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"保存设置失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 加载窗口位置
    /// </summary>
    public WindowPosition? LoadWindowPosition()
    {
        try
        {
            var positionPath = GetPositionFilePath();
            
            if (!File.Exists(positionPath))
            {
                return null;
            }

            var json = File.ReadAllText(positionPath);
            return JsonSerializer.Deserialize<WindowPosition>(json);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"加载窗口位置失败: {ex.Message}");
            return null;
        }
    }

    /// <summary>
    /// 保存窗口位置
    /// </summary>
    public void SaveWindowPosition(WindowPosition position)
    {
        try
        {
            var positionPath = GetPositionFilePath();
            var directory = Path.GetDirectoryName(positionPath);
            
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }

            var options = new JsonSerializerOptions
            {
                WriteIndented = true
            };
            
            var json = JsonSerializer.Serialize(position, options);
            File.WriteAllText(positionPath, json);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"保存窗口位置失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 获取设置文件路径
    /// </summary>
    private string GetSettingsFilePath()
    {
        return Path.Combine(GetSettingsDirectory(), SettingsFileName);
    }

    /// <summary>
    /// 获取位置文件路径
    /// </summary>
    private string GetPositionFilePath()
    {
        return Path.Combine(GetSettingsDirectory(), PositionFileName);
    }

    /// <summary>
    /// 获取设置目录（使用应用程序所在目录）
    /// </summary>
    private string GetSettingsDirectory()
    {
        // 获取应用程序可执行文件所在目录
        var appDirectory = AppContext.BaseDirectory;
        
        // 在应用程序目录下创建 config 子目录
        return Path.Combine(appDirectory, "config");
    }
}
