using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;

namespace VoiceRecognitionDisplay.Services;

/// <summary>
/// 健康监控服务，监控应用状态和性能
/// </summary>
public class HealthMonitor : IDisposable
{
    private readonly WebSocketService _webSocketService;
    private Timer? _healthCheckTimer;
    private bool _isDisposed;
    private int _consecutiveFailures;
    private const int MaxConsecutiveFailures = 5;
    
    public event EventHandler<HealthStatus>? HealthStatusChanged;
    
    public HealthMonitor(WebSocketService webSocketService)
    {
        _webSocketService = webSocketService;
    }
    
    /// <summary>
    /// 启动健康检查
    /// </summary>
    public void Start()
    {
        if (_healthCheckTimer != null)
        {
            return;
        }
        
        // 每30秒检查一次
        _healthCheckTimer = new Timer(
            PerformHealthCheck,
            null,
            TimeSpan.FromSeconds(5),
            TimeSpan.FromSeconds(30));
        
        Console.WriteLine("健康监控已启动");
    }
    
    /// <summary>
    /// 停止健康检查
    /// </summary>
    public void Stop()
    {
        _healthCheckTimer?.Change(Timeout.Infinite, Timeout.Infinite);
        Console.WriteLine("健康监控已停止");
    }
    
    /// <summary>
    /// 执行健康检查
    /// </summary>
    private void PerformHealthCheck(object? state)
    {
        try
        {
            var status = new HealthStatus
            {
                Timestamp = DateTime.Now,
                IsWebSocketConnected = _webSocketService.IsConnected,
                MemoryUsageMB = GetMemoryUsage(),
                ThreadCount = GetThreadCount()
            };
            
            // 检查连接状态
            if (!status.IsWebSocketConnected)
            {
                _consecutiveFailures++;
                Console.WriteLine($"WebSocket 未连接 (连续失败: {_consecutiveFailures})");
                
                if (_consecutiveFailures >= MaxConsecutiveFailures)
                {
                    Console.WriteLine("达到最大连续失败次数，可能需要人工干预");
                    status.NeedsAttention = true;
                }
            }
            else
            {
                _consecutiveFailures = 0;
            }
            
            // 检查内存使用
            if (status.MemoryUsageMB > 500) // 超过 500MB
            {
                Console.WriteLine($"警告: 内存使用过高 ({status.MemoryUsageMB:F2} MB)");
                status.NeedsAttention = true;
            }
            
            // 触发事件
            HealthStatusChanged?.Invoke(this, status);
            
            // 定期输出状态
            if (DateTime.Now.Second % 60 == 0) // 每分钟输出一次
            {
                Console.WriteLine($"健康状态: WebSocket={status.IsWebSocketConnected}, " +
                                $"内存={status.MemoryUsageMB:F2}MB, " +
                                $"线程={status.ThreadCount}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"健康检查失败: {ex.Message}");
        }
    }
    
    /// <summary>
    /// 获取内存使用量（MB）
    /// </summary>
    private double GetMemoryUsage()
    {
        try
        {
            var process = Process.GetCurrentProcess();
            return process.WorkingSet64 / 1024.0 / 1024.0;
        }
        catch
        {
            return 0;
        }
    }
    
    /// <summary>
    /// 获取线程数
    /// </summary>
    private int GetThreadCount()
    {
        try
        {
            var process = Process.GetCurrentProcess();
            return process.Threads.Count;
        }
        catch
        {
            return 0;
        }
    }
    
    public void Dispose()
    {
        if (_isDisposed)
        {
            return;
        }
        
        _isDisposed = true;
        _healthCheckTimer?.Dispose();
    }
}

/// <summary>
/// 健康状态信息
/// </summary>
public class HealthStatus
{
    public DateTime Timestamp { get; set; }
    public bool IsWebSocketConnected { get; set; }
    public double MemoryUsageMB { get; set; }
    public int ThreadCount { get; set; }
    public bool NeedsAttention { get; set; }
}
