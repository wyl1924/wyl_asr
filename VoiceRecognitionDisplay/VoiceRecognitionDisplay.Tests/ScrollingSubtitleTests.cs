using System;
using System.Collections.Generic;
using System.Threading;
using Xunit;
using FluentAssertions;
using VoiceRecognitionDisplay.ViewModels;
using VoiceRecognitionDisplay.Models;
using VoiceRecognitionDisplay.Services;

namespace VoiceRecognitionDisplay.Tests;

/// <summary>
/// 横向滚动字幕功能单元测试
/// 测试需求: 11.2, 11.3, 11.5, 11.8
/// </summary>
public class ScrollingSubtitleTests
{
    private MainWindowViewModel CreateViewModel()
    {
        var configManager = new ConfigurationManager();
        var webSocketService = new WebSocketService(configManager);
        return new MainWindowViewModel(webSocketService, configManager);
    }

    [Fact]
    public void ScrollingText_ShouldIncludeSpeakerName_WhenTranscriptionReceived()
    {
        // Arrange
        var viewModel = CreateViewModel();
        var message = new TranscriptionMessage
        {
            Type = "transcription",
            Speaker = new SpeakerInfo
            {
                Id = "speaker_001",
                Name = "张三",
                Icon = ""
            },
            Content = new ContentInfo
            {
                Chinese = "这是测试文本",
                English = "This is test text"
            },
            Timestamp = DateTime.Now
        };

        // Act
        viewModel.OnTranscriptionReceived(null, message);

        // Assert
        viewModel.ScrollingText.Should().Contain("张三:");
        viewModel.ScrollingText.Should().Contain("这是测试文本");
    }

    [Fact]
    public void ScrollingText_ShouldUpdateSpeakerName_WhenSpeakerChanges()
    {
        // Arrange
        var viewModel = CreateViewModel();
        
        var message1 = new TranscriptionMessage
        {
            Type = "transcription",
            Speaker = new SpeakerInfo { Name = "张三" },
            Content = new ContentInfo { Chinese = "第一句话" }
        };
        
        var message2 = new TranscriptionMessage
        {
            Type = "transcription",
            Speaker = new SpeakerInfo { Name = "李四" },
            Content = new ContentInfo { Chinese = "第二句话" }
        };

        // Act
        viewModel.OnTranscriptionReceived(null, message1);
        viewModel.OnTranscriptionReceived(null, message2);

        // Assert
        viewModel.ScrollingText.Should().Contain("张三: 第一句话");
        viewModel.ScrollingText.Should().Contain("李四: 第二句话");
    }

    [Fact]
    public void BufferManagement_ShouldRemoveOldestLines_WhenExceedingMaxDisplayLines()
    {
        // Arrange
        var viewModel = CreateViewModel();
        var settings = new SettingsModel { MaxDisplayLines = 2 };
        viewModel.ApplySettings(settings);

        // Act - 添加3条消息，超过MaxDisplayLines
        for (int i = 1; i <= 3; i++)
        {
            var message = new TranscriptionMessage
            {
                Type = "transcription",
                Speaker = new SpeakerInfo { Name = $"说话人{i}" },
                Content = new ContentInfo { Chinese = $"文本{i}" }
            };
            viewModel.OnTranscriptionReceived(null, message);
        }

        // Assert - 应该只保留最后2行
        viewModel.ScrollingText.Should().NotContain("文本1");
        viewModel.ScrollingText.Should().Contain("文本2");
        viewModel.ScrollingText.Should().Contain("文本3");
    }

    [Fact]
    public void BufferManagement_ShouldMaintainCorrectLineCount_AfterMultipleMessages()
    {
        // Arrange
        var viewModel = CreateViewModel();
        var settings = new SettingsModel { MaxDisplayLines = 5 };
        viewModel.ApplySettings(settings);

        // Act - 添加10条消息
        for (int i = 1; i <= 10; i++)
        {
            var message = new TranscriptionMessage
            {
                Type = "transcription",
                Speaker = new SpeakerInfo { Name = "说话人" },
                Content = new ContentInfo { Chinese = $"文本{i}" }
            };
            viewModel.OnTranscriptionReceived(null, message);
        }

        // Assert - 应该只保留最后5行
        var lines = viewModel.ScrollingText.Split(" | ", StringSplitOptions.RemoveEmptyEntries);
        lines.Length.Should().BeLessOrEqualTo(5);
        
        // 验证保留的是最新的行
        viewModel.ScrollingText.Should().Contain("文本10");
        viewModel.ScrollingText.Should().Contain("文本9");
        viewModel.ScrollingText.Should().Contain("文本8");
        viewModel.ScrollingText.Should().Contain("文本7");
        viewModel.ScrollingText.Should().Contain("文本6");
        viewModel.ScrollingText.Should().NotContain("文本1");
    }

    [Fact]
    public void RecognitionMode_ShouldUpdateCorrectly_BasedOnMessageType()
    {
        // Arrange
        var viewModel = CreateViewModel();

        // Act & Assert - 在线模式
        var onlineMessage = new TranscriptionMessage
        {
            Type = "2pass-online",
            Speaker = new SpeakerInfo { Name = "测试" },
            Content = new ContentInfo { Chinese = "在线文本" }
        };
        viewModel.OnTranscriptionReceived(null, onlineMessage);
        viewModel.RecognitionMode.Should().Be("2pass-online");

        // Act & Assert - 离线模式
        var offlineMessage = new TranscriptionMessage
        {
            Type = "2pass-offline",
            Speaker = new SpeakerInfo { Name = "测试" },
            Content = new ContentInfo { Chinese = "离线文本" }
        };
        viewModel.OnTranscriptionReceived(null, offlineMessage);
        viewModel.RecognitionMode.Should().Be("2pass-offline");
    }

    [Fact]
    public void ScrollSpeed_ShouldBeApplied_FromSettings()
    {
        // Arrange
        var viewModel = CreateViewModel();
        var settings = new SettingsModel { ScrollSpeed = 100 };

        // Act
        viewModel.ApplySettings(settings);

        // Assert
        viewModel.ScrollSpeed.Should().Be(100);
    }

    [Fact]
    public void ScrollingText_ShouldBeEmpty_Initially()
    {
        // Arrange & Act
        var viewModel = CreateViewModel();

        // Assert
        viewModel.ScrollingText.Should().BeEmpty();
    }

    [Fact]
    public void BufferManagement_ShouldClearAll_WhenExceedingMaxBufferSize()
    {
        // Arrange
        var viewModel = CreateViewModel();
        
        // Act - 添加超过MaxBufferSize的消息（1000条）
        for (int i = 1; i <= 1001; i++)
        {
            var message = new TranscriptionMessage
            {
                Type = "transcription",
                Speaker = new SpeakerInfo { Name = "说话人" },
                Content = new ContentInfo { Chinese = $"文本{i}" }
            };
            viewModel.OnTranscriptionReceived(null, message);
        }

        // Assert - 缓冲区应该被清空并重新开始
        // 由于清空后又添加了一条，所以应该只有最后一条
        var lines = viewModel.ScrollingText.Split(" | ", StringSplitOptions.RemoveEmptyEntries);
        lines.Length.Should().BeLessOrEqualTo(viewModel.MaxDisplayLines);
    }

    [Fact]
    public void ScrollingText_ShouldSeparateLines_WithPipeDelimiter()
    {
        // Arrange
        var viewModel = CreateViewModel();
        var settings = new SettingsModel { MaxDisplayLines = 3 };
        viewModel.ApplySettings(settings);

        // Act
        for (int i = 1; i <= 3; i++)
        {
            var message = new TranscriptionMessage
            {
                Type = "transcription",
                Speaker = new SpeakerInfo { Name = $"说话人{i}" },
                Content = new ContentInfo { Chinese = $"文本{i}" }
            };
            viewModel.OnTranscriptionReceived(null, message);
        }

        // Assert
        viewModel.ScrollingText.Should().Contain(" | ");
        var lines = viewModel.ScrollingText.Split(" | ", StringSplitOptions.RemoveEmptyEntries);
        lines.Length.Should().Be(3);
    }

    [Fact]
    public void SameSpeaker_ShouldClearBuffer_WhenExceedingMaxDisplayLines()
    {
        // Arrange
        var viewModel = CreateViewModel();
        var settings = new SettingsModel { MaxDisplayLines = 2 };
        viewModel.ApplySettings(settings);
        Thread.Sleep(100); // 等待UI线程处理

        // Act - 同一说话人发送3条消息（超过2行限制）
        for (int i = 1; i <= 3; i++)
        {
            var message = new TranscriptionMessage
            {
                Type = "transcription",
                Speaker = new SpeakerInfo { Name = "张三" },
                Content = new ContentInfo { Chinese = $"第{i}句话" }
            };
            viewModel.OnTranscriptionReceived(null, message);
            Thread.Sleep(100); // 等待UI线程处理
        }

        // Assert - 第3条消息应该触发清空，所以只显示第3条
        viewModel.ScrollingText.Should().NotContain("第1句话");
        viewModel.ScrollingText.Should().NotContain("第2句话");
        viewModel.ScrollingText.Should().Contain("第3句话");
    }

    [Fact]
    public void DifferentSpeaker_ShouldClearBuffer_Immediately()
    {
        // Arrange
        var viewModel = CreateViewModel();
        var settings = new SettingsModel { MaxDisplayLines = 2 };
        viewModel.ApplySettings(settings);
        Thread.Sleep(100); // 等待UI线程处理

        // Act - 第一个说话人发送消息
        var message1 = new TranscriptionMessage
        {
            Type = "transcription",
            Speaker = new SpeakerInfo { Name = "张三" },
            Content = new ContentInfo { Chinese = "张三的话" }
        };
        viewModel.OnTranscriptionReceived(null, message1);
        Thread.Sleep(100); // 等待UI线程处理

        // 第二个说话人发送消息
        var message2 = new TranscriptionMessage
        {
            Type = "transcription",
            Speaker = new SpeakerInfo { Name = "李四" },
            Content = new ContentInfo { Chinese = "李四的话" }
        };
        viewModel.OnTranscriptionReceived(null, message2);
        Thread.Sleep(100); // 等待UI线程处理

        // Assert - 应该只显示李四的话
        viewModel.ScrollingText.Should().NotContain("张三的话");
        viewModel.ScrollingText.Should().Contain("李四的话");
    }

    [Fact]
    public void SameSpeaker_ShouldAccumulate_WhenWithinMaxDisplayLines()
    {
        // Arrange
        var viewModel = CreateViewModel();
        var settings = new SettingsModel { MaxDisplayLines = 3 };
        viewModel.ApplySettings(settings);
        Thread.Sleep(100); // 等待UI线程处理

        // Act - 同一说话人发送2条消息（未超过3行限制）
        for (int i = 1; i <= 2; i++)
        {
            var message = new TranscriptionMessage
            {
                Type = "transcription",
                Speaker = new SpeakerInfo { Name = "张三" },
                Content = new ContentInfo { Chinese = $"第{i}句话" }
            };
            viewModel.OnTranscriptionReceived(null, message);
            Thread.Sleep(100); // 等待UI线程处理
        }

        // Assert - 应该累加显示两条消息
        viewModel.ScrollingText.Should().Contain("第1句话");
        viewModel.ScrollingText.Should().Contain("第2句话");
    }
}
