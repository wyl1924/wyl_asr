using System;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using VoiceRecognitionDisplay.Models;

namespace VoiceRecognitionDisplay.Services;

/// <summary>
/// WebSocket 服务，管理与语音识别后端的连接
/// </summary>
public class WebSocketService : IDisposable
{
    private ClientWebSocket? _webSocket;
    private CancellationTokenSource? _cancellationTokenSource;
    private readonly MessageParser _messageParser;
    private readonly ConfigurationManager _configManager;
    private bool _isDisposed;
    private bool _isReconnecting;
    private readonly SemaphoreSlim _reconnectLock = new(1, 1);

    public event EventHandler<TranscriptionMessage>? TranscriptionReceived;
    public event EventHandler<ConnectionStatus>? ConnectionStatusChanged;
    public event EventHandler<SettingsModel>? SettingsUpdateReceived;

    public bool IsConnected => _webSocket?.State == WebSocketState.Open;
    public string ServerUrl { get; set; } = "ws://127.0.0.1:10095/";

    public WebSocketService(ConfigurationManager configManager)
    {
        _messageParser = new MessageParser();
        _configManager = configManager ?? throw new ArgumentNullException(nameof(configManager));
    }

    /// <summary>
    /// 连接到 WebSocket 服务器
    /// </summary>
    public async Task ConnectAsync()
    {
        if (IsConnected)
        {
            return;
        }

        try
        {
            _cancellationTokenSource = new CancellationTokenSource();
            _webSocket = new ClientWebSocket();

            OnConnectionStatusChanged(ConnectionStatus.Connecting);

            await _webSocket.ConnectAsync(new Uri(ServerUrl), _cancellationTokenSource.Token);

            OnConnectionStatusChanged(ConnectionStatus.Connected);

            // 发送初始化配置
            await SendInitializationConfigAsync();

            // 开始接收消息
            _ = Task.Run(() => ReceiveMessagesAsync(_cancellationTokenSource.Token));
        }
        catch (Exception ex)
        {
            Console.WriteLine($"连接失败: {ex.Message}");
            OnConnectionStatusChanged(ConnectionStatus.Failed);
            
            // 启动重连（不递归调用）
            _ = Task.Run(async () =>
            {
                try
                {
                    await ReconnectWithBackoffAsync();
                }
                catch (Exception reconnectEx)
                {
                    Console.WriteLine($"重连任务失败: {reconnectEx.Message}");
                }
            });
        }
    }

    /// <summary>
    /// 断开 WebSocket 连接
    /// </summary>
    public async Task DisconnectAsync()
    {
        if (_webSocket == null || _webSocket.State != WebSocketState.Open)
        {
            return;
        }

        try
        {
            _cancellationTokenSource?.Cancel();
            
            await _webSocket.CloseAsync(
                WebSocketCloseStatus.NormalClosure,
                "Client disconnecting",
                CancellationToken.None);

            OnConnectionStatusChanged(ConnectionStatus.Disconnected);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"断开连接失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 发送初始化配置到服务器
    /// </summary>
    private async Task SendInitializationConfigAsync()
    {
        var config = new
        {
            chunk_size = new[] { 5, 10, 5 },
            wav_name = "client",
            is_speaking = true,
            chunk_interval = 10,
            mode = "2pass",
            language = "zh",
            enable_translation = true
        };

        var json = System.Text.Json.JsonSerializer.Serialize(config);
        Console.WriteLine($"发送初始化配置: {json}");
        await SendAsync(json);
    }

    /// <summary>
    /// 发送消息到服务器
    /// </summary>
    public async Task SendAsync(string message)
    {
        if (!IsConnected || _webSocket == null)
        {
            throw new InvalidOperationException("WebSocket 未连接");
        }

        var bytes = Encoding.UTF8.GetBytes(message);
        await _webSocket.SendAsync(
            new ArraySegment<byte>(bytes),
            WebSocketMessageType.Text,
            true,
            CancellationToken.None);
    }

    /// <summary>
    /// 接收消息循环
    /// </summary>
    private async Task ReceiveMessagesAsync(CancellationToken cancellationToken)
    {
        var buffer = new byte[1024 * 4];

        try
        {
            while (_webSocket != null && _webSocket.State == WebSocketState.Open && !cancellationToken.IsCancellationRequested)
            {
                var result = await _webSocket.ReceiveAsync(
                    new ArraySegment<byte>(buffer),
                    cancellationToken);

                if (result.MessageType == WebSocketMessageType.Close)
                {
                    await _webSocket.CloseAsync(
                        WebSocketCloseStatus.NormalClosure,
                        string.Empty,
                        CancellationToken.None);
                    
                    OnConnectionStatusChanged(ConnectionStatus.Disconnected);
                    
                    // 启动重连（不递归调用）
                    _ = Task.Run(async () =>
                    {
                        try
                        {
                            await ReconnectWithBackoffAsync();
                        }
                        catch (Exception reconnectEx)
                        {
                            Console.WriteLine($"重连任务失败: {reconnectEx.Message}");
                        }
                    });
                    break;
                }

                var message = Encoding.UTF8.GetString(buffer, 0, result.Count);
                Console.WriteLine($"🔍 [WebSocket] 收到原始消息: {message}");
                await HandleMessage(message);
            }
        }
        catch (OperationCanceledException)
        {
            // 正常取消，不需要重连
            Console.WriteLine("接收消息已取消");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"接收消息失败: {ex.Message}");
            OnConnectionStatusChanged(ConnectionStatus.Failed);
            
            // 启动重连（不递归调用）
            _ = Task.Run(async () =>
            {
                try
                {
                    await ReconnectWithBackoffAsync();
                }
                catch (Exception reconnectEx)
                {
                    Console.WriteLine($"重连任务失败: {reconnectEx.Message}");
                }
            });
        }
    }

    /// <summary>
    /// 处理接收到的消息
    /// </summary>
    private async Task HandleMessage(string message)
    {
        try
        {
            // Try to parse as settings update first
            var settings = _messageParser.ParseSettingsUpdate(message);
            if (settings != null)
            {
                await HandleSettingsUpdate(settings);
                return;
            }
            
            // Otherwise, parse as transcription message
            if (_messageParser.TryParseMessage(message, out var transcriptionMessage) && 
                transcriptionMessage != null)
            {
                TranscriptionReceived?.Invoke(this, transcriptionMessage);
            }
            else
            {
                Console.WriteLine($"无法解析消息: {message}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"处理消息失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 处理设置更新消息
    /// </summary>
    private async Task HandleSettingsUpdate(SettingsModel settings)
    {
        // Validate settings
        if (!settings.IsValid(out var errors))
        {
            Console.WriteLine($"收到无效设置: {string.Join(", ", errors)}");
            return;
        }
        
        // Notify UI to apply settings
        SettingsUpdateReceived?.Invoke(this, settings);
        
        // Persist settings to file
        try
        {
            _configManager.SaveSettings(settings);
            Console.WriteLine("设置已保存到配置文件");
        }
        catch (Exception ex)
        {
            // Log error but don't fail the operation
            Console.WriteLine($"保存设置到文件失败: {ex.Message}");
            // Settings are still applied in memory, so the operation is not a complete failure
        }
        
        await Task.CompletedTask;
    }

    /// <summary>
    /// 使用指数退避策略重连
    /// </summary>
    private async Task ReconnectWithBackoffAsync()
    {
        // 防止多个重连任务同时运行
        if (!await _reconnectLock.WaitAsync(0))
        {
            Console.WriteLine("重连任务已在运行中");
            return;
        }

        try
        {
            if (_isReconnecting || _isDisposed)
            {
                return;
            }

            _isReconnecting = true;
            int attempt = 0;
            int delay = 1000; // 1 秒
            const int maxDelay = 60000; // 60 秒
            const int maxAttempts = 10; // 最大重试次数

            while (!IsConnected && !_isDisposed && attempt < maxAttempts)
            {
                try
                {
                    OnConnectionStatusChanged(ConnectionStatus.Reconnecting);
                    
                    await Task.Delay(delay);
                    
                    // 直接重连，不调用 ConnectAsync 避免递归
                    _cancellationTokenSource?.Cancel();
                    _cancellationTokenSource?.Dispose();
                    _webSocket?.Dispose();
                    
                    _cancellationTokenSource = new CancellationTokenSource();
                    _webSocket = new ClientWebSocket();

                    await _webSocket.ConnectAsync(new Uri(ServerUrl), _cancellationTokenSource.Token);
                    OnConnectionStatusChanged(ConnectionStatus.Connected);

                    // 开始接收消息
                    _ = Task.Run(() => ReceiveMessagesAsync(_cancellationTokenSource.Token));

                    Console.WriteLine($"重连成功（尝试 {attempt + 1} 次）");
                    return;
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"重连尝试 {attempt + 1} 失败: {ex.Message}");
                }

                attempt++;
                delay = Math.Min(delay * 2, maxDelay);
            }

            if (attempt >= maxAttempts)
            {
                Console.WriteLine($"达到最大重连次数 ({maxAttempts})，停止重连");
                OnConnectionStatusChanged(ConnectionStatus.Failed);
            }
        }
        finally
        {
            _isReconnecting = false;
            _reconnectLock.Release();
        }
    }

    /// <summary>
    /// 触发连接状态变更事件
    /// </summary>
    private void OnConnectionStatusChanged(ConnectionStatus status)
    {
        ConnectionStatusChanged?.Invoke(this, status);
    }

    public void Dispose()
    {
        if (_isDisposed)
        {
            return;
        }

        _isDisposed = true;
        
        try
        {
            _cancellationTokenSource?.Cancel();
        }
        catch { }
        
        try
        {
            _cancellationTokenSource?.Dispose();
            _webSocket?.Dispose();
            _reconnectLock?.Dispose();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Dispose 失败: {ex.Message}");
        }
    }
}
