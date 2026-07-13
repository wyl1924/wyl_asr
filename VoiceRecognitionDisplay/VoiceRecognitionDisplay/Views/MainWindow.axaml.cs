using System;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using VoiceRecognitionDisplay.ViewModels;
using VoiceRecognitionDisplay.Services;
using VoiceRecognitionDisplay.Models;

namespace VoiceRecognitionDisplay.Views;

public partial class MainWindow : Window
{
    private readonly ConfigurationManager? _configManager;
    private readonly ShareService? _shareService;
    private MainWindowViewModel? _viewModel;
    
    public MainWindow()
    {
        InitializeComponent();
        
        // 不在这里注册全局 PointerPressed，而是在特定元素上注册
        
        // 注册窗口关闭事件
        Closing += Window_Closing;
    }
    
    public MainWindow(MainWindowViewModel viewModel, ConfigurationManager configManager, ShareService shareService) : this()
    {
        _viewModel = viewModel;
        _configManager = configManager;
        _shareService = shareService;
        
        // 设置 DataContext
        DataContext = viewModel;
        
        // 加载窗口位置
        LoadWindowPosition();
        
        // 订阅 ScrollingSubtitleControl 的行数超出事件
        this.Opened += (s, e) =>
        {
            // 为 Border 添加拖动事件（而不是整个窗口）
            var border = this.FindControl<Border>("DraggableBorder");
            if (border != null)
            {
                border.PointerPressed += Border_PointerPressed;
            }
            
            var scrollingControl = this.FindControl<ScrollingSubtitleControl>("SubtitleControl");
            if (scrollingControl != null)
            {
                scrollingControl.LineCountExceeded += OnLineCountExceeded;
                
                // 监听字幕控件高度变化
                scrollingControl.GetObservable(ScrollingSubtitleControl.HeightProperty).Subscribe(_ =>
                {
                    UpdateWindowHeight();
                });
                
                scrollingControl.GetObservable(ScrollingSubtitleControl.MaxDisplayLinesProperty).Subscribe(_ =>
                {
                    UpdateWindowHeight();
                });
                
                // 初始化窗口高度
                Avalonia.Threading.Dispatcher.UIThread.Post(() =>
                {
                    UpdateWindowHeight();
                }, Avalonia.Threading.DispatcherPriority.Loaded);
            }
        };
    }
    
    private void UpdateWindowHeight()
    {
        var scrollingControl = this.FindControl<ScrollingSubtitleControl>("SubtitleControl");
        if (scrollingControl != null && scrollingControl.Height > 0)
        {
            // 获取屏幕 DPI 缩放因子
            double scaling = 1.0;
            if (Screens.Primary != null)
            {
                scaling = Screens.Primary.Scaling;
            }
            
            // 计算窗口总高度（逻辑像素）
            // 顶部栏高度约 52px (32px 图标 + 20px 边距)
            // Border padding: 15px * 2 = 30px
            // Border thickness: 2px * 2 = 4px
            double topBarHeight = 52;
            double borderPadding = 30;
            double borderThickness = 4;
            double subtitleHeight = scrollingControl.Height;
            
            double totalHeight = topBarHeight + subtitleHeight + borderPadding + borderThickness;
            
            // 不需要手动调整 DPI，Avalonia 会自动处理
            // 但我们可以记录缩放信息用于调试
            this.Height = totalHeight;
            this.MinHeight = totalHeight;
            this.MaxHeight = totalHeight;
            
            System.Diagnostics.Debug.WriteLine($"[UpdateWindowHeight] DPI Scaling={scaling:F2}, SubtitleHeight={subtitleHeight}, TotalHeight={totalHeight}");
            Console.WriteLine($"[UpdateWindowHeight] DPI Scaling={scaling:F2}, SubtitleHeight={subtitleHeight}, TotalHeight={totalHeight}");
        }
    }
    
    protected override void OnDataContextChanged(EventArgs e)
    {
        base.OnDataContextChanged(e);
        
        if (DataContext is MainWindowViewModel viewModel)
        {
            _viewModel = viewModel;
            
            // 订阅 ViewModel 事件
            _viewModel.ShareRequested += OnShareRequested;
            _viewModel.SettingsRequested += OnSettingsRequested;
            _viewModel.CloseRequested += OnCloseRequested;
        }
    }
    
    private void Border_PointerPressed(object? sender, PointerPressedEventArgs e)
    {
        var point = e.GetCurrentPoint(this);
        
        // 支持鼠标左键或触屏拖动窗口
        if (point.Properties.IsLeftButtonPressed || 
            point.Pointer.Type == PointerType.Touch)
        {
            BeginMoveDrag(e);
        }
    }
    
    private void Window_PointerPressed(object? sender, PointerPressedEventArgs e)
    {
        var point = e.GetCurrentPoint(this);
        
        // 支持鼠标左键或触屏拖动窗口
        if (point.Properties.IsLeftButtonPressed || 
            point.Pointer.Type == PointerType.Touch)
        {
            BeginMoveDrag(e);
        }
    }
    
    private void Window_Closing(object? sender, WindowClosingEventArgs e)
    {
        // 保存窗口位置
        SaveWindowPosition();
    }
    
    private void LoadWindowPosition()
    {
        if (_configManager == null) return;
        
        try
        {
            var position = _configManager.LoadWindowPosition();
            
            if (position != null && Screens.Primary != null)
            {
                var screen = Screens.Primary.WorkingArea;
                
                // 验证位置是否在屏幕范围内
                if (position.IsValid(screen.Width, screen.Height))
                {
                    Position = new PixelPoint((int)position.X, (int)position.Y);
                    
                    if (position.Width > 0 && position.Height > 0)
                    {
                        Width = position.Width;
                        Height = position.Height;
                    }
                    return;
                }
            }
            
            // 如果没有保存的位置或位置无效，设置为屏幕最下方
            if (Screens.Primary != null)
            {
                var screen = Screens.Primary.WorkingArea;
                var x = (screen.Width - (int)Width) / 2; // 水平居中
                var y = screen.Height - (int)Height - 10; // 垂直位置在屏幕最下方，留10像素边距
                Position = new PixelPoint(x, y);
            }
        }
        catch (Exception ex)
        {
            // 日志记录错误，但不影响窗口显示
            Console.WriteLine($"Failed to load window position: {ex.Message}");
            
            // 出错时也设置为最下方
            if (Screens.Primary != null)
            {
                var screen = Screens.Primary.WorkingArea;
                var x = (screen.Width - (int)Width) / 2;
                var y = screen.Height - (int)Height - 10;
                Position = new PixelPoint(x, y);
            }
        }
    }
    
    private void SaveWindowPosition()
    {
        if (_configManager == null) return;
        
        try
        {
            var position = new WindowPosition
            {
                X = Position.X,
                Y = Position.Y,
                Width = Width,
                Height = Height
            };
            
            _configManager.SaveWindowPosition(position);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Failed to save window position: {ex.Message}");
        }
    }
    
    private async void OnShareRequested(object? sender, EventArgs e)
    {
        if (_viewModel == null || _shareService == null) return;
        
        try
        {
            // 创建分享对话框
            var shareViewModel = new ShareViewModel(_shareService)
            {
                FileName = $"会议记录_{DateTime.Now:yyyyMMdd_HHmmss}.txt"
            };
            
            // 获取当前内容
            var content = _viewModel.GetCurrentContent();
            
            // 初始化分享对话框
            await shareViewModel.InitializeAsync(content, shareViewModel.FileName);
            
            // 显示分享对话框
            var shareDialog = new ShareDialog
            {
                DataContext = shareViewModel
            };
            
            shareViewModel.CloseRequested += (s, args) => shareDialog.Close();
            
            await shareDialog.ShowDialog(this);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Failed to show share dialog: {ex.Message}");
        }
    }
    
    private async void OnSettingsRequested(object? sender, EventArgs e)
    {
        if (_viewModel == null || _configManager == null) return;
        
        try
        {
            Console.WriteLine("Opening settings window...");
            
            // 创建设置窗口
            var settingsViewModel = new SettingsViewModel(_configManager);
            
            // 加载当前设置
            var currentSettings = _viewModel.ToSettingsModel();
            Console.WriteLine($"Current background color: {currentSettings.BackgroundColor}");
            Console.WriteLine($"Current WebSocket URL: {currentSettings.WebSocketUrl}");
            settingsViewModel.LoadSettings(currentSettings);
            
            var settingsWindow = new SettingsWindow
            {
                DataContext = settingsViewModel
            };
            
            // 显示设置窗口
            var result = await settingsWindow.ShowDialog<bool>(this);
            
            Console.WriteLine($"Settings window closed with result: {result}");
            
            // 如果用户保存了设置，应用新设置
            if (result)
            {
                var newSettings = settingsViewModel.ToSettingsModel();
                Console.WriteLine($"New background color: {newSettings.BackgroundColor}");
                Console.WriteLine($"New WebSocket URL: {newSettings.WebSocketUrl}");
                _viewModel.ApplySettings(newSettings);
                _configManager.SaveSettings(newSettings);
                Console.WriteLine("Settings applied and saved");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Failed to show settings window: {ex.Message}");
            Console.WriteLine($"Stack trace: {ex.StackTrace}");
        }
    }
    
    private void OnCloseRequested(object? sender, EventArgs e)
    {
        Close();
    }
    
    private void OnLineCountExceeded(object? sender, EventArgs e)
    {
        // 行数超出限制，通知 ViewModel 清空缓冲区
        if (_viewModel != null)
        {
            Console.WriteLine("[MainWindow] 行数超出限制，清空缓冲区");
            _viewModel.ClearBuffer();
        }
    }
}
