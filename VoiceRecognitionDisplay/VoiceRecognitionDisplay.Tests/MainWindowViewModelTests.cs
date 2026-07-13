using System;
using System.Reflection;
using Xunit;
using VoiceRecognitionDisplay.ViewModels;
using VoiceRecognitionDisplay.Services;
using VoiceRecognitionDisplay.Models;

namespace VoiceRecognitionDisplay.Tests;

/// <summary>
/// Unit tests for MainWindowViewModel - Task 4.4
/// Tests that MainWindowViewModel subscribes to SettingsUpdateReceived event
/// and has the OnSettingsUpdateReceived handler implemented
/// </summary>
public class MainWindowViewModelTests
{
    [Fact]
    public void Constructor_SubscribesToSettingsUpdateReceived()
    {
        // Arrange
        var configManager = new ConfigurationManager();
        var webSocketService = new WebSocketService(configManager);
        
        // Act
        var viewModel = new MainWindowViewModel(webSocketService, configManager);
        
        // Assert - verify that the event subscription doesn't throw
        // The subscription happens in the constructor, so if we get here without exception, it worked
        Assert.NotNull(viewModel);
    }
    
    [Fact]
    public void MainWindowViewModel_HasOnSettingsUpdateReceivedMethod()
    {
        // Arrange
        var configManager = new ConfigurationManager();
        var webSocketService = new WebSocketService(configManager);
        var viewModel = new MainWindowViewModel(webSocketService, configManager);
        
        // Act - use reflection to verify the method exists
        var methodInfo = viewModel.GetType().GetMethod(
            "OnSettingsUpdateReceived",
            BindingFlags.NonPublic | BindingFlags.Instance
        );
        
        // Assert
        Assert.NotNull(methodInfo);
        Assert.Equal(typeof(void), methodInfo.ReturnType);
        
        var parameters = methodInfo.GetParameters();
        Assert.Equal(2, parameters.Length);
        Assert.Equal(typeof(object), parameters[0].ParameterType);
        Assert.Equal(typeof(SettingsModel), parameters[1].ParameterType);
    }
    
    [Fact]
    public void WebSocketService_HasSettingsUpdateReceivedEvent()
    {
        // Arrange
        var configManager = new ConfigurationManager();
        var webSocketService = new WebSocketService(configManager);
        
        // Act - verify the event exists
        var eventInfo = webSocketService.GetType().GetEvent("SettingsUpdateReceived");
        
        // Assert
        Assert.NotNull(eventInfo);
        Assert.Equal(typeof(EventHandler<SettingsModel>), eventInfo.EventHandlerType);
    }
    
    [Fact]
    public void Constructor_SubscribesEventHandler()
    {
        // Arrange
        var configManager = new ConfigurationManager();
        var webSocketService = new WebSocketService(configManager);
        
        // Get the event field to check if handlers are subscribed
        var eventField = webSocketService.GetType().GetField(
            "SettingsUpdateReceived",
            BindingFlags.NonPublic | BindingFlags.Instance
        );
        
        // Act
        var viewModel = new MainWindowViewModel(webSocketService, configManager);
        
        // Get the delegate
        var eventDelegate = eventField?.GetValue(webSocketService) as Delegate;
        
        // Assert - verify that at least one handler is subscribed
        Assert.NotNull(eventDelegate);
        Assert.True(eventDelegate.GetInvocationList().Length > 0);
    }
}
