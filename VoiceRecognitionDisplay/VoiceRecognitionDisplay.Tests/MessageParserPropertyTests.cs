using System;
using System.Text.Json;
using FluentAssertions;
using FsCheck;
using FsCheck.Xunit;
using VoiceRecognitionDisplay.Models;
using VoiceRecognitionDisplay.Services;

namespace VoiceRecognitionDisplay.Tests;

/// <summary>
/// Property-based tests for MessageParser
/// Feature: subtitle-display-settings-broadcast
/// </summary>
public class MessageParserPropertyTests
{
    private readonly MessageParser _parser;

    public MessageParserPropertyTests()
    {
        _parser = new MessageParser();
    }

    #region Property 9: Settings Parsing Round-Trip

    /// <summary>
    /// Property 9: For any valid SettingsModel object, serializing it to JSON as a 
    /// settings_update message and then parsing it back should produce an equivalent 
    /// SettingsModel object.
    /// 
    /// **Validates: Requirements 4.1, 4.2**
    /// 
    /// Feature: subtitle-display-settings-broadcast, Property 9: Settings Parsing Round-Trip
    /// </summary>
    [Property(MaxTest = 100)]
    public Property SettingsParsing_RoundTrip_ShouldPreserveAllValues()
    {
        return Prop.ForAll(
            GenerateValidSettings(),
            originalSettings =>
            {
                // Arrange - Create a settings_update message
                var message = new
                {
                    type = "settings_update",
                    data = originalSettings
                };
                var json = JsonSerializer.Serialize(message);

                // Act - Parse the message back
                var parsedSettings = _parser.ParseSettingsUpdate(json);

                // Assert - All properties should match
                parsedSettings.Should().NotBeNull("Parsing should succeed for valid settings");
                parsedSettings!.WindowWidth.Should().Be(originalSettings.WindowWidth, 
                    "WindowWidth should be preserved");
                parsedSettings.CornerRadius.Should().Be(originalSettings.CornerRadius, 
                    "CornerRadius should be preserved");
                parsedSettings.BackgroundColor.Should().Be(originalSettings.BackgroundColor, 
                    "BackgroundColor should be preserved");
                parsedSettings.BackgroundOpacity.Should().Be(originalSettings.BackgroundOpacity, 
                    "BackgroundOpacity should be preserved");
                parsedSettings.FontFamily.Should().Be(originalSettings.FontFamily, 
                    "FontFamily should be preserved");
                parsedSettings.FontSize.Should().Be(originalSettings.FontSize, 
                    "FontSize should be preserved");
                parsedSettings.FontColor.Should().Be(originalSettings.FontColor, 
                    "FontColor should be preserved");
                parsedSettings.IsBold.Should().Be(originalSettings.IsBold, 
                    "IsBold should be preserved");
                parsedSettings.IsItalic.Should().Be(originalSettings.IsItalic, 
                    "IsItalic should be preserved");
                parsedSettings.ShowEnglish.Should().Be(originalSettings.ShowEnglish, 
                    "ShowEnglish should be preserved");
                parsedSettings.MaxDisplayLines.Should().Be(originalSettings.MaxDisplayLines, 
                    "MaxDisplayLines should be preserved");
                parsedSettings.ScrollSpeed.Should().Be(originalSettings.ScrollSpeed, 
                    "ScrollSpeed should be preserved");
                parsedSettings.WebSocketUrl.Should().Be(originalSettings.WebSocketUrl, 
                    "WebSocketUrl should be preserved");

                return true;
            });
    }

    /// <summary>
    /// Property 9 (Edge Case): Settings parsing round-trip should work with minimum values
    /// 
    /// **Validates: Requirements 4.1, 4.2**
    /// 
    /// Feature: subtitle-display-settings-broadcast, Property 9: Settings Parsing Round-Trip (Min Values)
    /// </summary>
    [Property(MaxTest = 50)]
    public Property SettingsParsing_RoundTrip_WithMinimumValues_ShouldPreserveValues()
    {
        return Prop.ForAll(
            GenerateMinimumSettings(),
            originalSettings =>
            {
                // Arrange
                var message = new
                {
                    type = "settings_update",
                    data = originalSettings
                };
                var json = JsonSerializer.Serialize(message);

                // Act
                var parsedSettings = _parser.ParseSettingsUpdate(json);

                // Assert
                parsedSettings.Should().NotBeNull();
                parsedSettings!.WindowWidth.Should().Be(originalSettings.WindowWidth);
                parsedSettings.CornerRadius.Should().Be(originalSettings.CornerRadius);
                parsedSettings.BackgroundOpacity.Should().Be(originalSettings.BackgroundOpacity);
                parsedSettings.FontSize.Should().Be(originalSettings.FontSize);
                parsedSettings.MaxDisplayLines.Should().Be(originalSettings.MaxDisplayLines);
                parsedSettings.ScrollSpeed.Should().Be(originalSettings.ScrollSpeed);

                return true;
            });
    }

    /// <summary>
    /// Property 9 (Edge Case): Settings parsing round-trip should work with maximum values
    /// 
    /// **Validates: Requirements 4.1, 4.2**
    /// 
    /// Feature: subtitle-display-settings-broadcast, Property 9: Settings Parsing Round-Trip (Max Values)
    /// </summary>
    [Property(MaxTest = 50)]
    public Property SettingsParsing_RoundTrip_WithMaximumValues_ShouldPreserveValues()
    {
        return Prop.ForAll(
            GenerateMaximumSettings(),
            originalSettings =>
            {
                // Arrange
                var message = new
                {
                    type = "settings_update",
                    data = originalSettings
                };
                var json = JsonSerializer.Serialize(message);

                // Act
                var parsedSettings = _parser.ParseSettingsUpdate(json);

                // Assert
                parsedSettings.Should().NotBeNull();
                parsedSettings!.WindowWidth.Should().Be(originalSettings.WindowWidth);
                parsedSettings.CornerRadius.Should().Be(originalSettings.CornerRadius);
                parsedSettings.BackgroundOpacity.Should().Be(originalSettings.BackgroundOpacity);
                parsedSettings.FontSize.Should().Be(originalSettings.FontSize);
                parsedSettings.MaxDisplayLines.Should().Be(originalSettings.MaxDisplayLines);
                parsedSettings.ScrollSpeed.Should().Be(originalSettings.ScrollSpeed);

                return true;
            });
    }

    /// <summary>
    /// Property 9 (Edge Case): Settings parsing should handle special color values
    /// 
    /// **Validates: Requirements 4.1, 4.2**
    /// 
    /// Feature: subtitle-display-settings-broadcast, Property 9: Settings Parsing Round-Trip (Special Colors)
    /// </summary>
    [Property(MaxTest = 50)]
    public Property SettingsParsing_RoundTrip_WithSpecialColors_ShouldPreserveValues()
    {
        return Prop.ForAll(
            GenerateSettingsWithSpecialColors(),
            originalSettings =>
            {
                // Arrange
                var message = new
                {
                    type = "settings_update",
                    data = originalSettings
                };
                var json = JsonSerializer.Serialize(message);

                // Act
                var parsedSettings = _parser.ParseSettingsUpdate(json);

                // Assert
                parsedSettings.Should().NotBeNull();
                parsedSettings!.BackgroundColor.Should().Be(originalSettings.BackgroundColor,
                    "Background color should be preserved");
                parsedSettings.FontColor.Should().Be(originalSettings.FontColor,
                    "Font color should be preserved (including '默认')");

                return true;
            });
    }

    #endregion

    #region Helper Methods - Generators

    /// <summary>
    /// Generate valid SettingsModel objects with random values within valid ranges
    /// </summary>
    private static Arbitrary<SettingsModel> GenerateValidSettings()
    {
        var fontFamilies = new[] { "宋体", "黑体", "微软雅黑", "Arial", "SimSun", "Microsoft YaHei" };
        var protocols = new[] { "ws://", "wss://" };
        var hosts = new[] { "127.0.0.1", "localhost", "example.com", "192.168.1.1" };

        return Arb.From(
            from windowWidth in Gen.Choose(10, 100)
            from cornerRadius in Gen.Choose(0, 100)
            from backgroundColor in GenerateHexColor()
            from backgroundOpacity in Gen.Choose(0, 100)
            from fontFamily in Gen.Elements(fontFamilies)
            from fontSize in Gen.Choose(1, 100)
            from fontColor in GenerateFontColor()
            from isBold in Arb.Generate<bool>()
            from isItalic in Arb.Generate<bool>()
            from showEnglish in Arb.Generate<bool>()
            from maxDisplayLines in Gen.Choose(1, 20)
            from scrollSpeed in Gen.Choose(20, 200)
            from protocol in Gen.Elements(protocols)
            from host in Gen.Elements(hosts)
            from port in Gen.Choose(1000, 65535)
            select new SettingsModel
            {
                WindowWidth = windowWidth,
                CornerRadius = cornerRadius,
                BackgroundColor = backgroundColor,
                BackgroundOpacity = backgroundOpacity,
                FontFamily = fontFamily,
                FontSize = fontSize,
                FontColor = fontColor,
                IsBold = isBold,
                IsItalic = isItalic,
                ShowEnglish = showEnglish,
                MaxDisplayLines = maxDisplayLines,
                ScrollSpeed = scrollSpeed,
                WebSocketUrl = $"{protocol}{host}:{port}/"
            });
    }

    /// <summary>
    /// Generate SettingsModel with minimum valid values
    /// </summary>
    private static Arbitrary<SettingsModel> GenerateMinimumSettings()
    {
        return Arb.From(
            from backgroundColor in GenerateHexColor()
            from fontColor in GenerateFontColor()
            select new SettingsModel
            {
                WindowWidth = 10,
                CornerRadius = 0,
                BackgroundColor = backgroundColor,
                BackgroundOpacity = 0,
                FontFamily = "Arial",
                FontSize = 1,
                FontColor = fontColor,
                IsBold = false,
                IsItalic = false,
                ShowEnglish = false,
                MaxDisplayLines = 1,
                ScrollSpeed = 20,
                WebSocketUrl = "ws://localhost/"
            });
    }

    /// <summary>
    /// Generate SettingsModel with maximum valid values
    /// </summary>
    private static Arbitrary<SettingsModel> GenerateMaximumSettings()
    {
        return Arb.From(
            from backgroundColor in GenerateHexColor()
            from fontColor in GenerateFontColor()
            select new SettingsModel
            {
                WindowWidth = 100,
                CornerRadius = 100,
                BackgroundColor = backgroundColor,
                BackgroundOpacity = 100,
                FontFamily = "Microsoft YaHei",
                FontSize = 100,
                FontColor = fontColor,
                IsBold = true,
                IsItalic = true,
                ShowEnglish = true,
                MaxDisplayLines = 20,
                ScrollSpeed = 200,
                WebSocketUrl = "wss://example.com:8080/"
            });
    }

    /// <summary>
    /// Generate SettingsModel with special color values (3-digit hex, 6-digit hex, "默认")
    /// </summary>
    private static Arbitrary<SettingsModel> GenerateSettingsWithSpecialColors()
    {
        var specialBackgroundColors = new[] { "#000", "#FFF", "#F00", "#0F0", "#00F", "#000000", "#FFFFFF", "#FF0000" };
        var specialFontColors = new[] { "默认", "#000", "#FFF", "#000000", "#FFFFFF" };

        return Arb.From(
            from backgroundColor in Gen.Elements(specialBackgroundColors)
            from fontColor in Gen.Elements(specialFontColors)
            select new SettingsModel
            {
                WindowWidth = 80,
                CornerRadius = 10,
                BackgroundColor = backgroundColor,
                BackgroundOpacity = 75,
                FontFamily = "宋体",
                FontSize = 14,
                FontColor = fontColor,
                IsBold = false,
                IsItalic = false,
                ShowEnglish = false,
                MaxDisplayLines = 2,
                ScrollSpeed = 60,
                WebSocketUrl = "ws://127.0.0.1:10095/"
            });
    }

    /// <summary>
    /// Generate valid hex color strings (#RGB or #RRGGBB format)
    /// </summary>
    private static Gen<string> GenerateHexColor()
    {
        var hexDigits = "0123456789ABCDEF".ToCharArray();
        
        // Generate either 3-digit or 6-digit hex colors
        var gen3Digit = from r in Gen.Elements(hexDigits)
                        from g in Gen.Elements(hexDigits)
                        from b in Gen.Elements(hexDigits)
                        select $"#{r}{g}{b}";

        var gen6Digit = from r1 in Gen.Elements(hexDigits)
                        from r2 in Gen.Elements(hexDigits)
                        from g1 in Gen.Elements(hexDigits)
                        from g2 in Gen.Elements(hexDigits)
                        from b1 in Gen.Elements(hexDigits)
                        from b2 in Gen.Elements(hexDigits)
                        select $"#{r1}{r2}{g1}{g2}{b1}{b2}";

        return Gen.OneOf(gen3Digit, gen6Digit);
    }

    /// <summary>
    /// Generate valid font color values (hex color or "默认")
    /// </summary>
    private static Gen<string> GenerateFontColor()
    {
        var defaultColor = Gen.Constant("默认");
        var hexColor = GenerateHexColor();
        
        return Gen.OneOf(defaultColor, hexColor);
    }

    #endregion
}
