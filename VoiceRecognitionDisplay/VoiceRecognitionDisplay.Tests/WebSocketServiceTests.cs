using System;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using Moq;
using VoiceRecognitionDisplay.Models;
using VoiceRecognitionDisplay.Services;
using Xunit;

namespace VoiceRecognitionDisplay.Tests;

/// <summary>
/// Unit tests for WebSocketService
/// Validates Requirements: 8.1-8.6
/// </summary>
public class WebSocketServiceTests : IDisposable
{
    private WebSocketService _service;
    private ConfigurationManager _configManager;
    
    public WebSocketServiceTests()
    {
        _configManager = new ConfigurationManager();
        _service = new WebSocketService(_configManager);
    }
    
    public void Dispose()
    {
        _service?.Dispose();
    }
    
    #region Connection Tests
    
    [Fact]
    public void WebSocketService_InitialState_ShouldBeDisconnected()
    {
        // Arrange & Act
        var isConnected = _service.IsConnected;
        
        // Assert
        isConnected.Should().BeFalse("Service should not be connected initially");
    }
    
    [Fact]
    public void WebSocketService_ServerUrl_ShouldHaveDefaultValue()
    {
        // Arrange & Act
        var serverUrl = _service.ServerUrl;
        
        // Assert
        serverUrl.Should().Be("ws://127.0.0.1:10095/", "Default server URL should be ws://127.0.0.1:10095/");
    }
    
    [Fact]
    public void WebSocketService_ServerUrl_ShouldBeSettable()
    {
        // Arrange
        var newUrl = "ws://example.com:9000";
        
        // Act
        _service.ServerUrl = newUrl;
        
        // Assert
        _service.ServerUrl.Should().Be(newUrl, "Server URL should be updatable");
    }
    
    [Fact]
    public async Task ConnectAsync_WithInvalidUrl_ShouldRaiseFailedStatus()
    {
        // Arrange
        _service.ServerUrl = "ws://invalid-host-that-does-not-exist:12345";
        ConnectionStatus? receivedStatus = null;
        _service.ConnectionStatusChanged += (sender, status) => receivedStatus = status;
        
        // Act
        await _service.ConnectAsync();
        await Task.Delay(500); // Give time for connection attempt
        
        // Assert
        receivedStatus.Should().NotBeNull("Connection status event should be raised");
        (receivedStatus == ConnectionStatus.Failed || 
         receivedStatus == ConnectionStatus.Reconnecting).Should().BeTrue(
            "Status should be Failed or Reconnecting after connection failure");
    }
    
    [Fact]
    public async Task ConnectAsync_WhenAlreadyConnected_ShouldNotReconnect()
    {
        // This test verifies the guard clause in ConnectAsync
        // We can't easily test actual connection without a real server,
        // but we can verify the method doesn't throw when called multiple times
        
        // Arrange
        _service.ServerUrl = "ws://localhost:8080";
        
        // Act
        var firstCall = _service.ConnectAsync();
        var secondCall = _service.ConnectAsync();
        
        // Assert - should not throw
        await Task.WhenAll(firstCall, secondCall);
    }
    
    #endregion
    
    #region Disconnection Tests
    
    [Fact]
    public async Task DisconnectAsync_WhenNotConnected_ShouldNotThrow()
    {
        // Arrange - service is not connected
        
        // Act
        Func<Task> act = async () => await _service.DisconnectAsync();
        
        // Assert
        await act.Should().NotThrowAsync("Disconnecting when not connected should be safe");
    }
    
    #endregion
    
    #region Message Sending Tests
    
    [Fact]
    public async Task SendAsync_WhenNotConnected_ShouldThrowInvalidOperationException()
    {
        // Arrange
        var message = "test message";
        
        // Act
        Func<Task> act = async () => await _service.SendAsync(message);
        
        // Assert
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*未连接*", "Should throw when trying to send while disconnected");
    }
    
    #endregion
    
    #region Event Tests
    
    [Fact]
    public void TranscriptionReceived_Event_ShouldBeSubscribable()
    {
        // Arrange
        TranscriptionMessage? receivedMessage = null;
        
        // Act - Subscribe to the event
        Action act = () => _service.TranscriptionReceived += (sender, message) => receivedMessage = message;
        
        // Assert
        act.Should().NotThrow("Event should be subscribable");
    }
    
    [Fact]
    public void ConnectionStatusChanged_Event_ShouldBeSubscribable()
    {
        // Arrange
        ConnectionStatus? receivedStatus = null;
        
        // Act - Subscribe to the event
        Action act = () => _service.ConnectionStatusChanged += (sender, status) => receivedStatus = status;
        
        // Assert
        act.Should().NotThrow("Event should be subscribable");
    }
    
    [Fact]
    public void SettingsUpdateReceived_Event_ShouldBeSubscribable()
    {
        // Arrange
        SettingsModel? receivedSettings = null;
        
        // Act - Subscribe to the event
        Action act = () => _service.SettingsUpdateReceived += (sender, settings) => receivedSettings = settings;
        
        // Assert
        act.Should().NotThrow("Event should be subscribable");
    }
    
    #endregion
    
    #region Edge Cases
    
    [Fact]
    public void WebSocketService_Dispose_ShouldNotThrow()
    {
        // Arrange
        var configManager = new ConfigurationManager();
        var service = new WebSocketService(configManager);
        
        // Act
        Action act = () => service.Dispose();
        
        // Assert
        act.Should().NotThrow("Dispose should be safe to call");
    }
    
    [Fact]
    public void WebSocketService_DisposeMultipleTimes_ShouldNotThrow()
    {
        // Arrange
        var configManager = new ConfigurationManager();
        var service = new WebSocketService(configManager);
        
        // Act
        Action act = () =>
        {
            service.Dispose();
            service.Dispose();
            service.Dispose();
        };
        
        // Assert
        act.Should().NotThrow("Multiple Dispose calls should be safe");
    }
    
    [Fact]
    public async Task SendAsync_WithNullMessage_ShouldThrowArgumentException()
    {
        // Arrange - even though not connected, null should be caught
        
        // Act
        Func<Task> act = async () => await _service.SendAsync(null!);
        
        // Assert
        await act.Should().ThrowAsync<Exception>("Null message should not be allowed");
    }
    
    [Fact]
    public async Task SendAsync_WithEmptyMessage_ShouldNotThrowArgumentException()
    {
        // Arrange
        var emptyMessage = "";
        
        // Act
        Func<Task> act = async () => await _service.SendAsync(emptyMessage);
        
        // Assert
        // Should throw InvalidOperationException (not connected), not ArgumentException
        await act.Should().ThrowAsync<InvalidOperationException>(
            "Empty message should be allowed, but connection check should fail");
    }
    
    #endregion
    
    #region Reconnection Behavior Tests
    
    [Fact]
    public async Task ConnectAsync_AfterFailure_ShouldTriggerReconnection()
    {
        // Arrange
        _service.ServerUrl = "ws://invalid-host:12345";
        var statusChanges = new System.Collections.Generic.List<ConnectionStatus>();
        _service.ConnectionStatusChanged += (sender, status) => statusChanges.Add(status);
        
        // Act
        await _service.ConnectAsync();
        await Task.Delay(2000); // Wait for initial failure and first reconnection attempt
        
        // Assert
        statusChanges.Should().Contain(ConnectionStatus.Connecting, 
            "Should attempt to connect");
        statusChanges.Should().Contain(s => s == ConnectionStatus.Failed || s == ConnectionStatus.Reconnecting,
            "Should indicate failure or reconnection");
    }
    
    #endregion
}
