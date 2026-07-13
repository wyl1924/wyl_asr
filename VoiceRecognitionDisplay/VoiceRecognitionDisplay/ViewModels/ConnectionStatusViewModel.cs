using System;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Avalonia.Media;
using VoiceRecognitionDisplay.Models;
using VoiceRecognitionDisplay.Services;

namespace VoiceRecognitionDisplay.ViewModels;

/// <summary>
/// 连接状态 ViewModel
/// </summary>
public partial class ConnectionStatusViewModel : ViewModelBase
{
    private readonly WebSocketService _webSocketService;
    
    [ObservableProperty]
    private string _statusText = "未连接";
    
    [ObservableProperty]
    private IBrush _statusColor = Brushes.Gray;
    
    [ObservableProperty]
    private bool _isConnected = false;
    
    [ObservableProperty]
    private bool _canReconnect = true;
    
    public ConnectionStatusViewModel(WebSocketService webSocketService)
    {
        _webSocketService = webSocketService;
        _webSocketService.ConnectionStatusChanged += OnConnectionStatusChanged;
        
        // 初始状态
        UpdateStatus(_webSocketService.IsConnected ? ConnectionStatus.Connected : ConnectionStatus.Disconnected);
    }
    
    [RelayCommand(CanExecute = nameof(CanReconnect))]
    private async System.Threading.Tasks.Task ReconnectAsync()
    {
        try
        {
            CanReconnect = false;
            await _webSocketService.ConnectAsync();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"手动重连失败: {ex.Message}");
        }
        finally
        {
            CanReconnect = true;
        }
    }
    
    [RelayCommand]
    private async System.Threading.Tasks.Task DisconnectAsync()
    {
        try
        {
            await _webSocketService.DisconnectAsync();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"断开连接失败: {ex.Message}");
        }
    }
    
    private void OnConnectionStatusChanged(object? sender, ConnectionStatus status)
    {
        UpdateStatus(status);
    }
    
    private void UpdateStatus(ConnectionStatus status)
    {
        switch (status)
        {
            case ConnectionStatus.Connected:
                StatusText = "已连接";
                StatusColor = Brushes.Green;
                IsConnected = true;
                CanReconnect = false;
                break;
                
            case ConnectionStatus.Connecting:
                StatusText = "连接中...";
                StatusColor = Brushes.Orange;
                IsConnected = false;
                CanReconnect = false;
                break;
                
            case ConnectionStatus.Reconnecting:
                StatusText = "重连中...";
                StatusColor = Brushes.Orange;
                IsConnected = false;
                CanReconnect = false;
                break;
                
            case ConnectionStatus.Disconnected:
                StatusText = "已断开";
                StatusColor = Brushes.Gray;
                IsConnected = false;
                CanReconnect = true;
                break;
                
            case ConnectionStatus.Failed:
                StatusText = "连接失败";
                StatusColor = Brushes.Red;
                IsConnected = false;
                CanReconnect = true;
                break;
        }
    }
}
