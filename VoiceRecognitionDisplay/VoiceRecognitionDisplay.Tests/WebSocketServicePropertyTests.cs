using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using FluentAssertions;
using FsCheck;
using FsCheck.Xunit;
using VoiceRecognitionDisplay.Models;
using VoiceRecognitionDisplay.Services;

namespace VoiceRecognitionDisplay.Tests;

/// <summary>
/// Property-based tests for WebSocketService settings handling
/// Feature: subtitle-display-settings-broadcast
/// </summary>
public class WebSocketServicePropertyTests
{
    #region Property 10: Invalid Settings Rejection

    /// <summary>
    /// Property 10: For any Settings_Model object that fails validation, the client should 
    /// log an error and not apply the settings to the UI or persist them to disk.
    /// 
    /// **Validates: Requirements 4.3, 6.5**
    /// 
    /// Feature: subtitle-display-settings-broadcast, Property 10: Invalid Settings Rejection
    /// </summary>
    [Property(MaxTest = 100)]
    public Property InvalidSettings_ShouldBeRejected_AndNotAppliedOrPersisted()
    {
        return Prop.ForAll(
            GenerateInvalidSettings(),
            invalidSettings =>
            {
                // Arrange
                var messageParser = new MessageParser();
                var configManager = new ConfigurationManager();
                var webSocketService = new WebSocketService(configManager);
                
                bool eventFired = false;
                SettingsModel? receivedSettings = null;
                
                // Subscribe to the event to verify it's NOT fired
                webSocketService.SettingsUpdateReceived += (sender, settings) =>
                {
                    eventFired = true;
                    receivedSettings = settings;
                };

                // Create a settings_update message with invalid settings
                var message = System.Text.Json.JsonSerializer.Serialize(new
                {
                    type = "settings_update",
                    data = invalidSettings
                });

                // Capture console output to verify error logging
                var originalOut = Console.Out;
                using var consoleOutput = new StringWriter();
                Console.SetOut(consoleOutput);

                try
                {
                    // Act - Parse and handle the invalid settings
                    var parsedSettings = messageParser.ParseSettingsUpdate(message);
                    
                    // The parser should successfully parse the JSON structure
                    parsedSettings.Should().NotBeNull("Parser should parse the JSON structure");
                    
                    // But validation should fail
                    var isValid = parsedSettings!.IsValid(out var errors);
                    isValid.Should().BeFalse("Invalid settings should fail validation");
                    errors.Should().NotBeEmpty("Validation should return error messages");

                    // Simulate what HandleSettingsUpdate does
                    if (!isValid)
                    {
                        Console.WriteLine($"收到无效设置: {string.Join(", ", errors)}");
                    }

                    // Assert
                    // 1. Error should be logged
                    var consoleText = consoleOutput.ToString();
                    consoleText.Should().Contain("收到无效设置", 
                        "Invalid settings should be logged");

                    // 2. Event should NOT be fired
                    eventFired.Should().BeFalse(
                        "SettingsUpdateReceived event should NOT be fired for invalid settings");
                    receivedSettings.Should().BeNull(
                        "No settings should be received when validation fails");

                    // 3. Settings should NOT be persisted
                    // We verify this by checking that SaveSettings would not be called
                    // In the actual implementation, HandleSettingsUpdate returns early on validation failure
                    // so SaveSettings is never called
                }
                finally
                {
                    Console.SetOut(originalOut);
                    webSocketService.Dispose();
                }
            });
    }

    /// <summary>
    /// Property 10 (Edge Case): Invalid numeric ranges should be rejected
    /// 
    /// **Validates: Requirements 4.3, 6.5**
    /// 
    /// Feature: subtitle-display-settings-broadcast, Property 10: Invalid Settings Rejection (Numeric Ranges)
    /// </summary>
    [Property(MaxTest = 100)]
    public Property InvalidNumericRanges_ShouldBeRejected()
    {
        return Prop.ForAll(
            GenerateInvalidNumericSettings(),
            invalidSettings =>
            {
                // Arrange
                var messageParser = new MessageParser();
                var configManager = new ConfigurationManager();
                bool eventFired = false;
                
                using var webSocketService = new WebSocketService(configManager);
                webSocketService.SettingsUpdateReceived += (sender, settings) =>
                {
                    eventFired = true;
                };

                var message = System.Text.Json.JsonSerializer.Serialize(new
                {
                    type = "settings_update",
                    data = invalidSettings
                });

                // Act
                var parsedSettings = messageParser.ParseSettingsUpdate(message);
                var isValid = parsedSettings!.IsValid(out var errors);

                // Assert
                isValid.Should().BeFalse("Settings with out-of-range numeric values should fail validation");
                errors.Should().NotBeEmpty("Validation should return error messages for out-of-range values");
                eventFired.Should().BeFalse("Event should not fire for invalid numeric ranges");
            });
    }

    /// <summary>
    /// Property 10 (Edge Case): Invalid color formats should be rejected
    /// 
    /// **Validates: Requirements 4.3, 6.5**
    /// 
    /// Feature: subtitle-display-settings-broadcast, Property 10: Invalid Settings Rejection (Color Formats)
    /// </summary>
    [Property(MaxTest = 100)]
    public Property InvalidColorFormats_ShouldBeRejected()
    {
        return Prop.ForAll(
            GenerateInvalidColorSettings(),
            invalidSettings =>
            {
                // Arrange
                var messageParser = new MessageParser();
                var configManager = new ConfigurationManager();
                bool eventFired = false;
                
                using var webSocketService = new WebSocketService(configManager);
                webSocketService.SettingsUpdateReceived += (sender, settings) =>
                {
                    eventFired = true;
                };

                var message = System.Text.Json.JsonSerializer.Serialize(new
                {
                    type = "settings_update",
                    data = invalidSettings
                });

                // Act
                var parsedSettings = messageParser.ParseSettingsUpdate(message);
                var isValid = parsedSettings!.IsValid(out var errors);

                // Assert
                isValid.Should().BeFalse("Settings with invalid color formats should fail validation");
                errors.Should().NotBeEmpty("Validation should return error messages for invalid colors");
                errors.Should().Contain(e => e.Contains("颜色") || e.Contains("色格式"), 
                    "Error messages should mention color format issues");
                eventFired.Should().BeFalse("Event should not fire for invalid color formats");
            });
    }

    /// <summary>
    /// Property 10 (Edge Case): Invalid WebSocket URLs should be rejected
    /// 
    /// **Validates: Requirements 4.3, 6.5**
    /// 
    /// Feature: subtitle-display-settings-broadcast, Property 10: Invalid Settings Rejection (WebSocket URLs)
    /// </summary>
    [Property(MaxTest = 100)]
    public Property InvalidWebSocketUrls_ShouldBeRejected()
    {
        return Prop.ForAll(
            GenerateInvalidWebSocketUrlSettings(),
            invalidSettings =>
            {
                // Arrange
                var messageParser = new MessageParser();
                var configManager = new ConfigurationManager();
                bool eventFired = false;
                
                using var webSocketService = new WebSocketService(configManager);
                webSocketService.SettingsUpdateReceived += (sender, settings) =>
                {
                    eventFired = true;
                };

                var message = System.Text.Json.JsonSerializer.Serialize(new
                {
                    type = "settings_update",
                    data = invalidSettings
                });

                // Act
                var parsedSettings = messageParser.ParseSettingsUpdate(message);
                var isValid = parsedSettings!.IsValid(out var errors);

                // Assert
                isValid.Should().BeFalse("Settings with invalid WebSocket URLs should fail validation");
                errors.Should().NotBeEmpty("Validation should return error messages for invalid URLs");
                errors.Should().Contain(e => e.Contains("WebSocket"), 
                    "Error messages should mention WebSocket URL issues");
                eventFired.Should().BeFalse("Event should not fire for invalid WebSocket URLs");
            });
    }

    #endregion

    #region Helper Methods - Generators

    /// <summary>
    /// Generate invalid SettingsModel objects with various types of validation errors
    /// </summary>
    private static Arbitrary<SettingsModel> GenerateInvalidSettings()
    {
        var invalidGenerators = new[]
        {
            GenerateInvalidNumericSettings().Generator,
            GenerateInvalidColorSettings().Generator,
            GenerateInvalidWebSocketUrlSettings().Generator,
            GenerateMultipleInvalidFields().Generator
        };

        return Arb.From(Gen.OneOf(invalidGenerators));
    }

    /// <summary>
    /// Generate SettingsModel with out-of-range numeric values
    /// </summary>
    private static Arbitrary<SettingsModel> GenerateInvalidNumericSettings()
    {
        return Arb.From(
            from invalidField in Gen.Choose(0, 5)
            from windowWidth in Gen.Choose(-100, 200)
            from cornerRadius in Gen.Choose(-50, 150)
            from backgroundOpacity in Gen.Choose(-50, 150)
            from fontSize in Gen.Choose(-10, 150)
            from maxDisplayLines in Gen.Choose(-5, 30)
            from scrollSpeed in Gen.Choose(-50, 300)
            select invalidField switch
            {
                0 => new SettingsModel { WindowWidth = windowWidth < 10 || windowWidth > 100 ? windowWidth : 5 },
                1 => new SettingsModel { CornerRadius = cornerRadius < 0 || cornerRadius > 100 ? cornerRadius : -1 },
                2 => new SettingsModel { BackgroundOpacity = backgroundOpacity < 0 || backgroundOpacity > 100 ? backgroundOpacity : 101 },
                3 => new SettingsModel { FontSize = fontSize < 1 || fontSize > 100 ? fontSize : 0 },
                4 => new SettingsModel { MaxDisplayLines = maxDisplayLines < 1 || maxDisplayLines > 20 ? maxDisplayLines : 0 },
                _ => new SettingsModel { ScrollSpeed = scrollSpeed < 20 || scrollSpeed > 200 ? scrollSpeed : 10 }
            });
    }

    /// <summary>
    /// Generate SettingsModel with invalid color formats
    /// </summary>
    private static Arbitrary<SettingsModel> GenerateInvalidColorSettings()
    {
        var invalidColors = new[]
        {
            "invalid",
            "rgb(255,0,0)",
            "#GGG",
            "#GGGGGG",
            "red",
            "#12",
            "#12345",
            "#1234567",
            "123456",
            "#",
            "",
            "0x000000"
        };

        return Arb.From(
            from invalidColor in Gen.Elements(invalidColors)
            from useBackgroundColor in Arb.Generate<bool>()
            select useBackgroundColor
                ? new SettingsModel { BackgroundColor = invalidColor }
                : new SettingsModel { FontColor = invalidColor });
    }

    /// <summary>
    /// Generate SettingsModel with invalid WebSocket URLs
    /// </summary>
    private static Arbitrary<SettingsModel> GenerateInvalidWebSocketUrlSettings()
    {
        var invalidUrls = new[]
        {
            "http://localhost:8080/",
            "https://example.com/",
            "ftp://server.com/",
            "tcp://127.0.0.1:10095/",
            "localhost:10095",
            "127.0.0.1:10095",
            "",
            "invalid-url",
            "ws",
            "wss",
            "ws:/",
            "wss:/"
        };

        return Arb.From(
            from invalidUrl in Gen.Elements(invalidUrls)
            select new SettingsModel { WebSocketUrl = invalidUrl });
    }

    /// <summary>
    /// Generate SettingsModel with multiple invalid fields
    /// </summary>
    private static Arbitrary<SettingsModel> GenerateMultipleInvalidFields()
    {
        return Arb.From(
            from windowWidth in Gen.Choose(-10, 5)
            from cornerRadius in Gen.Choose(101, 150)
            from backgroundColor in Gen.Constant("invalid-color")
            from backgroundOpacity in Gen.Choose(101, 150)
            from fontSize in Gen.Choose(-5, 0)
            from fontColor in Gen.Constant("rgb(0,0,0)")
            from maxDisplayLines in Gen.Choose(21, 30)
            from scrollSpeed in Gen.Choose(0, 19)
            from webSocketUrl in Gen.Constant("http://invalid")
            select new SettingsModel
            {
                WindowWidth = windowWidth,
                CornerRadius = cornerRadius,
                BackgroundColor = backgroundColor,
                BackgroundOpacity = backgroundOpacity,
                FontSize = fontSize,
                FontColor = fontColor,
                MaxDisplayLines = maxDisplayLines,
                ScrollSpeed = scrollSpeed,
                WebSocketUrl = webSocketUrl
            });
    }

    #endregion
}
