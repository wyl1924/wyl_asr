using System;
using System.Text.Json;
using FluentAssertions;
using VoiceRecognitionDisplay.Models;
using VoiceRecognitionDisplay.Services;
using Xunit;

namespace VoiceRecognitionDisplay.Tests;

/// <summary>
/// Unit tests for MessageParser
/// Validates Requirements: 4.1
/// </summary>
public class MessageParserTests
{
    private readonly MessageParser _parser;

    public MessageParserTests()
    {
        _parser = new MessageParser();
    }

    #region ParseSettingsUpdate Tests

    [Fact]
    public void ParseSettingsUpdate_WithValidSettingsMessage_ShouldReturnSettingsModel()
    {
        // Arrange
        var settingsData = new
        {
            windowWidth = 80,
            cornerRadius = 10,
            backgroundColor = "#000000",
            backgroundOpacity = 75,
            fontFamily = "宋体",
            fontSize = 14,
            fontColor = "默认",
            isBold = false,
            isItalic = false,
            showEnglish = false,
            maxDisplayLines = 2,
            scrollSpeed = 60,
            webSocketUrl = "ws://127.0.0.1:10095/"
        };

        var message = new
        {
            type = "settings_update",
            data = settingsData
        };

        var json = JsonSerializer.Serialize(message);

        // Act
        var result = _parser.ParseSettingsUpdate(json);

        // Assert
        result.Should().NotBeNull();
        result!.WindowWidth.Should().Be(80);
        result.CornerRadius.Should().Be(10);
        result.BackgroundColor.Should().Be("#000000");
        result.BackgroundOpacity.Should().Be(75);
        result.FontFamily.Should().Be("宋体");
        result.FontSize.Should().Be(14);
        result.FontColor.Should().Be("默认");
        result.IsBold.Should().BeFalse();
        result.IsItalic.Should().BeFalse();
        result.ShowEnglish.Should().BeFalse();
        result.MaxDisplayLines.Should().Be(2);
        result.ScrollSpeed.Should().Be(60);
        result.WebSocketUrl.Should().Be("ws://127.0.0.1:10095/");
    }

    [Fact]
    public void ParseSettingsUpdate_WithNonSettingsMessage_ShouldReturnNull()
    {
        // Arrange
        var message = new
        {
            type = "transcription",
            text = "Hello world"
        };

        var json = JsonSerializer.Serialize(message);

        // Act
        var result = _parser.ParseSettingsUpdate(json);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public void ParseSettingsUpdate_WithMissingTypeField_ShouldReturnNull()
    {
        // Arrange
        var message = new
        {
            data = new
            {
                windowWidth = 80
            }
        };

        var json = JsonSerializer.Serialize(message);

        // Act
        var result = _parser.ParseSettingsUpdate(json);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public void ParseSettingsUpdate_WithMissingDataField_ShouldReturnNull()
    {
        // Arrange
        var message = new
        {
            type = "settings_update"
        };

        var json = JsonSerializer.Serialize(message);

        // Act
        var result = _parser.ParseSettingsUpdate(json);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public void ParseSettingsUpdate_WithInvalidJson_ShouldReturnNull()
    {
        // Arrange
        var invalidJson = "{ invalid json }";

        // Act
        var result = _parser.ParseSettingsUpdate(invalidJson);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public void ParseSettingsUpdate_WithNullInput_ShouldReturnNull()
    {
        // Act
        var result = _parser.ParseSettingsUpdate(null!);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public void ParseSettingsUpdate_WithEmptyString_ShouldReturnNull()
    {
        // Act
        var result = _parser.ParseSettingsUpdate("");

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public void ParseSettingsUpdate_WithWhitespaceString_ShouldReturnNull()
    {
        // Act
        var result = _parser.ParseSettingsUpdate("   ");

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public void ParseSettingsUpdate_WithPartialSettingsData_ShouldUseDefaults()
    {
        // Arrange - only provide some fields
        var message = new
        {
            type = "settings_update",
            data = new
            {
                windowWidth = 90,
                fontSize = 20
            }
        };

        var json = JsonSerializer.Serialize(message);

        // Act
        var result = _parser.ParseSettingsUpdate(json);

        // Assert
        result.Should().NotBeNull();
        result!.WindowWidth.Should().Be(90);
        result.FontSize.Should().Be(20);
        // Other fields should have default values
        result.CornerRadius.Should().Be(10); // default
        result.BackgroundColor.Should().Be("#000000"); // default
    }

    [Fact]
    public void ParseSettingsUpdate_WithAllFieldsAtMinimumValues_ShouldParse()
    {
        // Arrange
        var settingsData = new
        {
            windowWidth = 10,
            cornerRadius = 0,
            backgroundColor = "#000",
            backgroundOpacity = 0,
            fontFamily = "Arial",
            fontSize = 1,
            fontColor = "#FFF",
            isBold = false,
            isItalic = false,
            showEnglish = false,
            maxDisplayLines = 1,
            scrollSpeed = 20,
            webSocketUrl = "ws://localhost/"
        };

        var message = new
        {
            type = "settings_update",
            data = settingsData
        };

        var json = JsonSerializer.Serialize(message);

        // Act
        var result = _parser.ParseSettingsUpdate(json);

        // Assert
        result.Should().NotBeNull();
        result!.WindowWidth.Should().Be(10);
        result.CornerRadius.Should().Be(0);
        result.BackgroundOpacity.Should().Be(0);
        result.FontSize.Should().Be(1);
        result.MaxDisplayLines.Should().Be(1);
        result.ScrollSpeed.Should().Be(20);
    }

    [Fact]
    public void ParseSettingsUpdate_WithAllFieldsAtMaximumValues_ShouldParse()
    {
        // Arrange
        var settingsData = new
        {
            windowWidth = 100,
            cornerRadius = 100,
            backgroundColor = "#FFFFFF",
            backgroundOpacity = 100,
            fontFamily = "SimSun",
            fontSize = 100,
            fontColor = "#000000",
            isBold = true,
            isItalic = true,
            showEnglish = true,
            maxDisplayLines = 20,
            scrollSpeed = 200,
            webSocketUrl = "wss://example.com:8080/"
        };

        var message = new
        {
            type = "settings_update",
            data = settingsData
        };

        var json = JsonSerializer.Serialize(message);

        // Act
        var result = _parser.ParseSettingsUpdate(json);

        // Assert
        result.Should().NotBeNull();
        result!.WindowWidth.Should().Be(100);
        result.CornerRadius.Should().Be(100);
        result.BackgroundOpacity.Should().Be(100);
        result.FontSize.Should().Be(100);
        result.MaxDisplayLines.Should().Be(20);
        result.ScrollSpeed.Should().Be(200);
        result.IsBold.Should().BeTrue();
        result.IsItalic.Should().BeTrue();
        result.ShowEnglish.Should().BeTrue();
    }

    [Fact]
    public void ParseSettingsUpdate_WithCaseInsensitivePropertyNames_ShouldParse()
    {
        // Arrange - using different casing
        var json = @"{
            ""type"": ""settings_update"",
            ""data"": {
                ""WINDOWWIDTH"": 85,
                ""cornerradius"": 15,
                ""BackgroundColor"": ""#FF0000""
            }
        }";

        // Act
        var result = _parser.ParseSettingsUpdate(json);

        // Assert
        result.Should().NotBeNull();
        result!.WindowWidth.Should().Be(85);
        result.CornerRadius.Should().Be(15);
        result.BackgroundColor.Should().Be("#FF0000");
    }

    [Fact]
    public void ParseSettingsUpdate_WithExtraFields_ShouldIgnoreExtraFields()
    {
        // Arrange
        var json = @"{
            ""type"": ""settings_update"",
            ""data"": {
                ""windowWidth"": 75,
                ""extraField"": ""should be ignored"",
                ""anotherExtra"": 123
            }
        }";

        // Act
        var result = _parser.ParseSettingsUpdate(json);

        // Assert
        result.Should().NotBeNull();
        result!.WindowWidth.Should().Be(75);
    }

    #endregion

    #region Integration with Existing ParseMessage Tests

    [Fact]
    public void ParseMessage_ShouldNotInterfereWithSettingsUpdate()
    {
        // Arrange - a settings update message
        var settingsMessage = new
        {
            type = "settings_update",
            data = new { windowWidth = 80 }
        };
        var json = JsonSerializer.Serialize(settingsMessage);

        // Act - ParseMessage should not parse settings messages
        var transcriptionResult = _parser.TryParseMessage(json, out var message);

        // Assert - should fail to parse as transcription
        transcriptionResult.Should().BeFalse();
        message.Should().BeNull();
    }

    [Fact]
    public void ParseSettingsUpdate_ShouldNotParseTranscriptionMessages()
    {
        // Arrange - a transcription message
        var transcriptionJson = @"{
            ""type"": ""transcription"",
            ""speaker"": {
                ""id"": ""user1"",
                ""name"": ""张三"",
                ""icon"": ""👤""
            },
            ""content"": {
                ""chinese"": ""你好"",
                ""english"": ""Hello""
            }
        }";

        // Act
        var result = _parser.ParseSettingsUpdate(transcriptionJson);

        // Assert
        result.Should().BeNull();
    }

    #endregion
}
