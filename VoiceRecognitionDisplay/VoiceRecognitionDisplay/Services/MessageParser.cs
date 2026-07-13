using System;
using System.Text.Json;
using VoiceRecognitionDisplay.Models;

namespace VoiceRecognitionDisplay.Services;

/// <summary>
/// WebSocket 消息解析器
/// 支持 FunASR 服务器的实际消息格式
/// </summary>
public class MessageParser
{
    private readonly JsonSerializerOptions _jsonOptions;

    public MessageParser()
    {
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        };
    }

    /// <summary>
    /// 解析 WebSocket 消息
    /// </summary>
    /// <param name="json">JSON 格式的消息</param>
    /// <returns>解析后的转录消息</returns>
    /// <exception cref="JsonException">JSON 格式无效时抛出</exception>
    public TranscriptionMessage ParseMessage(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            throw new ArgumentException("消息内容不能为空", nameof(json));
        }

        try
        {
            // 尝试解析为 FunASR 格式
            using var document = JsonDocument.Parse(json);
            var root = document.RootElement;
            
            // 检查是否是 FunASR 格式（包含 mode, text, speaker_name）
            if (root.TryGetProperty("mode", out var modeElement) && root.TryGetProperty("text", out var textElement))
            {
                var translationText = root.TryGetProperty("translation", out var translationElement)
                    ? translationElement.GetString() ?? ""
                    : "";

                var message = new TranscriptionMessage
                {
                    Type = modeElement.GetString() ?? "transcription",
                    Mode = modeElement.GetString() ?? "",
                    Text = textElement.GetString() ?? "",
                    SpeakerName = root.TryGetProperty("speaker_name", out var speakerNameElement)
                        ? speakerNameElement.GetString() ?? ""
                        : "",
                    Translation = translationText,
                    Speaker = new SpeakerInfo
                    {
                        Id = root.TryGetProperty("speaker_name", out var speakerNameElement2)
                            ? speakerNameElement2.GetString() ?? "unknown"
                            : "unknown",
                        Name = root.TryGetProperty("speaker_name", out var speakerNameElement3)
                            ? speakerNameElement3.GetString() ?? "未知说话人"
                            : "未知说话人",
                        Icon = "👤"
                    },
                    Content = new ContentInfo
                    {
                        Chinese = textElement.GetString() ?? "",
                        English = translationText
                    },
                    Timestamp = DateTime.Now
                };

                return message;
            }
            
            // 尝试标准格式
            var standardMessage = JsonSerializer.Deserialize<TranscriptionMessage>(json, _jsonOptions);
            
            if (standardMessage == null)
            {
                throw new JsonException("无法解析消息：反序列化结果为 null");
            }

            return standardMessage;
        }
        catch (JsonException ex)
        {
            throw new JsonException($"解析消息失败: {ex.Message}", ex);
        }
    }

    /// <summary>
    /// 尝试解析 WebSocket 消息（安全版本）
    /// </summary>
    /// <param name="json">JSON 格式的消息</param>
    /// <param name="message">解析后的转录消息</param>
    /// <returns>解析是否成功</returns>
    public bool TryParseMessage(string json, out TranscriptionMessage? message)
    {
        message = null;

        if (string.IsNullOrWhiteSpace(json))
        {
            return false;
        }

        try
        {
            message = ParseMessage(json);
            return message != null;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    /// <summary>
    /// 将转录消息序列化为 JSON
    /// </summary>
    /// <param name="message">转录消息</param>
    /// <returns>JSON 字符串</returns>
    public string SerializeMessage(TranscriptionMessage message)
    {
        if (message == null)
        {
            throw new ArgumentNullException(nameof(message));
        }

        return JsonSerializer.Serialize(message, _jsonOptions);
    }

    /// <summary>
    /// 解析设置更新消息
    /// </summary>
    /// <param name="json">JSON 格式的消息</param>
    /// <returns>解析后的设置模型，如果不是设置更新消息或解析失败则返回 null</returns>
    public SettingsModel? ParseSettingsUpdate(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(json);
            var root = document.RootElement;

            // 检查是否是设置更新消息
            if (root.TryGetProperty("type", out var typeElement) &&
                typeElement.GetString() == "settings_update" &&
                root.TryGetProperty("data", out var dataElement))
            {
                var settings = JsonSerializer.Deserialize<SettingsModel>(
                    dataElement.GetRawText(),
                    _jsonOptions
                );
                return settings;
            }

            return null;
        }
        catch (JsonException ex)
        {
            Console.WriteLine($"解析设置更新失败: {ex.Message}");
            return null;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"解析设置更新时发生意外错误: {ex.Message}");
            return null;
        }
    }
}
