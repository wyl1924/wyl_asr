using System;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using VoiceRecognitionDisplay.ViewModels;
using VoiceRecognitionDisplay.Services;
using Avalonia.VisualTree;
using Avalonia.Threading;

namespace VoiceRecognitionDisplay.Views;

public partial class MainView : UserControl
{
    private const string OpenSettingsAction = "open_settings";
    private const string OpenShareAction = "open_share";

    private readonly ConfigurationManager? _configManager;
    private readonly ShareService? _shareService;
    private readonly string? _startupAction;
    private readonly Action<bool>? _setExpandedMode;
    private readonly Action? _closeHost;
    private readonly Action<Control>? _showFloatingModal;
    private readonly Action? _closeFloatingModal;
    private MainWindowViewModel? _viewModel;
    private bool _startupActionTriggered;
    private bool _viewInitialized;
    
    public MainView()
    {
        InitializeComponent();
        AttachedToVisualTree += OnAttachedToVisualTree;
    }
    
    public MainView(
        MainWindowViewModel viewModel,
        ConfigurationManager configManager,
        ShareService shareService,
        string? startupAction = null,
        Action<bool>? setExpandedMode = null,
        Action? closeHost = null,
        Action<Control>? showFloatingModal = null,
        Action? closeFloatingModal = null) : this()
    {
        _viewModel = viewModel;
        _configManager = configManager;
        _shareService = shareService;
        _startupAction = startupAction;
        _setExpandedMode = setExpandedMode;
        _closeHost = closeHost;
        _showFloatingModal = showFloatingModal;
        _closeFloatingModal = closeFloatingModal;
        
        // 设置 DataContext
        DataContext = viewModel;
        
        Console.WriteLine("[MainView] 构造函数开始");
    }
    
    protected override void OnDataContextChanged(EventArgs e)
    {
        base.OnDataContextChanged(e);
        
        if (_viewModel != null)
        {
            _viewModel.ShareRequested -= OnShareRequested;
            _viewModel.SettingsRequested -= OnSettingsRequested;
            _viewModel.CloseRequested -= OnCloseRequested;
        }

        if (DataContext is MainWindowViewModel viewModel)
        {
            _viewModel = viewModel;
            _viewModel.ShareRequested += OnShareRequested;
            _viewModel.SettingsRequested += OnSettingsRequested;
            _viewModel.CloseRequested += OnCloseRequested;
            Console.WriteLine("[MainView] DataContext 已更新");
        }
        else
        {
            _viewModel = null;
        }
    }

    private void OnAttachedToVisualTree(object? sender, VisualTreeAttachmentEventArgs e)
    {
        if (_viewInitialized)
        {
            return;
        }

        _viewInitialized = true;
        Console.WriteLine("[MainView] AttachedToVisualTree 事件触发");
        ConfigureTransparentTopLevel();

        var scrollingControl = this.FindControl<ScrollingSubtitleControl>("SubtitleControl");
        if (scrollingControl != null)
        {
            scrollingControl.LineCountExceeded += OnLineCountExceeded;

            scrollingControl.GetObservable(ScrollingSubtitleControl.HeightProperty).Subscribe(_ =>
            {
                UpdateViewHeight();
            });

            scrollingControl.GetObservable(ScrollingSubtitleControl.MaxDisplayLinesProperty).Subscribe(_ =>
            {
                UpdateViewHeight();
            });

            Dispatcher.UIThread.Post(() =>
            {
                UpdateViewHeight();
            }, DispatcherPriority.Loaded);
        }

        if (_viewModel != null && _configManager != null)
        {
            var settings = _configManager.LoadSettings();
            _viewModel.ApplySettings(settings);
            Console.WriteLine($"[MainView] 窗口宽度已应用: {_viewModel.WindowWidth}");
        }

        if (_shareService != null)
        {
            _shareService.TopLevelProvider = () => TopLevel.GetTopLevel(this);
        }

        TriggerStartupActionIfNeeded();
    }

    private void ShowModal(Control content, bool expanded)
    {
        if (_showFloatingModal != null && string.IsNullOrWhiteSpace(_startupAction))
        {
            _showFloatingModal(content);
            return;
        }

        ShowInlineModal(content, expanded);
    }

    private void ShowInlineModal(Control content, bool expanded)
    {
        ConfigureTransparentTopLevel();

        var modalHost = this.FindControl<ContentControl>("ModalContentHost");
        var modalSpacing = this.FindControl<Border>("ModalSpacing");
        var draggableBorder = this.FindControl<Border>("DraggableBorder");

        if (modalHost == null || modalSpacing == null || draggableBorder == null)
        {
            Console.WriteLine("[MainView] 未找到内嵌弹层宿主");
            return;
        }

        modalHost.Content = ResolveInlineModalContent(content);
        modalHost.IsVisible = true;
        modalSpacing.IsVisible = true;
        draggableBorder.IsVisible = true;
        SetExpandedMode(expanded);
    }

    private void ConfigureTransparentTopLevel()
    {
        try
        {
            var topLevel = TopLevel.GetTopLevel(this);
            if (topLevel == null)
            {
                return;
            }

            topLevel.TransparencyLevelHint = new[] { WindowTransparencyLevel.Transparent };
            topLevel.TransparencyBackgroundFallback = Brushes.Transparent;
            topLevel.Background = Brushes.Transparent;

            Console.WriteLine(
                $"[MainView] TopLevel transparency configured, actual={topLevel.ActualTransparencyLevel}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[MainView] 配置透明顶层失败: {ex.Message}");
        }
    }

    private Control ResolveInlineModalContent(Control content)
    {
        if (content is UserControl userControl && userControl.Content is Control innerContent)
        {
            innerContent.DataContext = userControl.DataContext;

            return innerContent;
        }

        return content;
    }

    private void CloseInlineModal(bool reloadOverlay = false)
    {
        var modalHost = this.FindControl<ContentControl>("ModalContentHost");
        var modalSpacing = this.FindControl<Border>("ModalSpacing");
        var draggableBorder = this.FindControl<Border>("DraggableBorder");

        if (modalHost != null)
        {
            modalHost.Content = null;
            modalHost.IsVisible = false;
        }

        if (modalSpacing != null)
        {
            modalSpacing.IsVisible = false;
        }

        if (draggableBorder != null)
        {
            draggableBorder.IsVisible = true;
        }

        SetExpandedMode(false);

        if (!string.IsNullOrWhiteSpace(_startupAction))
        {
            FinishTransientAndroidHost(reloadOverlay);
        }
    }

    private void CloseModal(bool reloadOverlay = false)
    {
        if (_closeFloatingModal != null && string.IsNullOrWhiteSpace(_startupAction))
        {
            _closeFloatingModal();
            return;
        }

        CloseInlineModal(reloadOverlay);
    }

    private void SetExpandedMode(bool expanded)
    {
        if (_setExpandedMode != null)
        {
            _setExpandedMode(expanded);
            return;
        }

        try
        {
            var topLevel = TopLevel.GetTopLevel(this);
            var platformImpl = topLevel?.PlatformImpl;
            var activityProperty = platformImpl?.GetType().GetProperty("Activity");
            var activity = activityProperty?.GetValue(platformImpl);
            var setExpandedMode = activity?.GetType().GetMethod("SetExpandedMode");

            setExpandedMode?.Invoke(activity, new object[] { expanded });
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[MainView] 切换 Android 窗口模式失败: {ex.Message}");
        }
    }

    private Task<string?> ShowInlineColorPickerAsync(SettingsPanel settingsPanel, string initialColor)
    {
        var completionSource = new TaskCompletionSource<string?>();
        var colorPickerViewModel = new ColorPickerViewModel(initialColor);
        var colorPickerPanel = new ColorPickerPanel
        {
            DataContext = colorPickerViewModel
        };

        void RestoreSettingsPanel(string? result)
        {
            ShowModal(settingsPanel, expanded: true);
            completionSource.TrySetResult(result);
        }

        colorPickerViewModel.ColorConfirmed += (s, color) => RestoreSettingsPanel(color);
        colorPickerViewModel.ColorCancelled += (s, args) => RestoreSettingsPanel(null);

        ShowModal(colorPickerPanel, expanded: true);
        return completionSource.Task;
    }

    private void TriggerStartupActionIfNeeded()
    {
        if (_startupActionTriggered || string.IsNullOrWhiteSpace(_startupAction))
        {
            return;
        }

        _startupActionTriggered = true;

        Dispatcher.UIThread.Post(() =>
        {
            switch (_startupAction)
            {
                case OpenSettingsAction:
                    OnSettingsRequested(this, EventArgs.Empty);
                    break;
                case OpenShareAction:
                    OnShareRequested(this, EventArgs.Empty);
                    break;
            }
        }, DispatcherPriority.Background);
    }

    private void FinishTransientAndroidHost(bool reloadOverlay)
    {
        try
        {
            var topLevel = TopLevel.GetTopLevel(this);
            var platformImpl = topLevel?.PlatformImpl;
            var activityProperty = platformImpl?.GetType().GetProperty("Activity");
            var activity = activityProperty?.GetValue(platformImpl);

            if (activity == null)
            {
                return;
            }

            var methodName = reloadOverlay ? "ReloadOverlayAndFinish" : "FinishTransientUi";
            var finishMethod = activity.GetType().GetMethod(methodName);
            finishMethod?.Invoke(activity, Array.Empty<object>());
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[MainView] 关闭临时 Android 页面失败: {ex.Message}");
        }
    }
    
    private async void OnShareRequested(object? sender, EventArgs e)
    {
        if (_viewModel == null || _shareService == null) return;
        
        try
        {
            Console.WriteLine("[MainView] 分享按钮被点击");
            
            // 获取当前内容
            var content = _viewModel.GetCurrentContent();
            
            // 创建分享对话框
            var shareViewModel = new ShareViewModel(_shareService)
            {
                FileName = $"会议记录_{DateTime.Now:yyyyMMdd_HHmmss}.txt"
            };
            
            // 初始化分享对话框
            await shareViewModel.InitializeAsync(content, shareViewModel.FileName);

            var ownerWindow = this.FindAncestorOfType<Window>();
            if (ownerWindow != null)
            {
                var shareDialog = new ShareDialog
                {
                    DataContext = shareViewModel
                };

                shareViewModel.CloseRequested += (s, args) => shareDialog.Close();
                await shareDialog.ShowDialog(ownerWindow);
            }
            else
            {
                Console.WriteLine("[MainView] 使用悬浮分享面板");

                var sharePanel = new SharePanel
                {
                    DataContext = shareViewModel
                };

                shareViewModel.CloseRequested += (s, args) => CloseModal();
                ShowModal(sharePanel, expanded: true);
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Failed to share: {ex.Message}");
            Console.WriteLine($"Stack trace: {ex.StackTrace}");

            if (!string.IsNullOrWhiteSpace(_startupAction))
            {
                FinishTransientAndroidHost(false);
            }
        }
    }
    
    private async void OnSettingsRequested(object? sender, EventArgs e)
    {
        if (_viewModel == null || _configManager == null) return;
        
        try
        {
            Console.WriteLine("[MainView] 设置按钮被点击");
            
            // 创建设置窗口
            var settingsViewModel = new SettingsViewModel(_configManager);
            
            // 加载当前设置
            var currentSettings = _viewModel.ToSettingsModel();
            Console.WriteLine($"Current background color: {currentSettings.BackgroundColor}");
            settingsViewModel.LoadSettings(currentSettings);

            var ownerWindow = this.FindAncestorOfType<Window>();
            if (ownerWindow != null)
            {
                var settingsWindow = new SettingsWindow
                {
                    DataContext = settingsViewModel
                };

                var result = await settingsWindow.ShowDialog<bool>(ownerWindow);
                
                Console.WriteLine($"Settings window closed with result: {result}");
                
                // 如果用户保存了设置，应用新设置
                if (result)
                {
                    var newSettings = settingsViewModel.ToSettingsModel();
                    Console.WriteLine($"New background color: {newSettings.BackgroundColor}");
                    _viewModel.ApplySettings(newSettings);
                    _configManager.SaveSettings(newSettings);
                    Console.WriteLine("Settings applied and saved");
                }
            }
            else
            {
                Console.WriteLine("[MainView] 使用悬浮设置面板");

                var settingsPanel = new SettingsPanel
                {
                    DataContext = settingsViewModel
                };

                settingsViewModel.FontColorPickerHandler = initialColor =>
                    ShowInlineColorPickerAsync(settingsPanel, initialColor);
                settingsViewModel.BackgroundColorPickerHandler = initialColor =>
                    ShowInlineColorPickerAsync(settingsPanel, initialColor);

                settingsViewModel.SettingsSaved += (s, settings) =>
                {
                    _viewModel.ApplySettings(settings);
                    _configManager.SaveSettings(settings);
                    CloseModal(reloadOverlay: !string.IsNullOrWhiteSpace(_startupAction));
                };

                settingsViewModel.SettingsCancelled += (s, args) =>
                {
                    CloseModal();
                };

                ShowModal(settingsPanel, expanded: true);
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Failed to show settings: {ex.Message}");
            Console.WriteLine($"Stack trace: {ex.StackTrace}");

            if (!string.IsNullOrWhiteSpace(_startupAction))
            {
                FinishTransientAndroidHost(false);
            }
        }
    }
    
    private void OnCloseRequested(object? sender, EventArgs e)
    {
        Console.WriteLine("[MainView] 关闭按钮被点击");

        if (_closeHost != null)
        {
            _closeHost();
            return;
        }
        
        // Android: 最小化应用而不是关闭
        Console.WriteLine("Close requested on Android - minimizing app");
        
        try
        {
            // 在 Android 上，通过 TopLevel 获取 Activity 并最小化
            var topLevel = Avalonia.Controls.TopLevel.GetTopLevel(this);
            if (topLevel != null)
            {
                // 尝试通过反射获取 Android Activity
                var platformImpl = topLevel.PlatformImpl;
                if (platformImpl != null)
                {
                    var activityProperty = platformImpl.GetType().GetProperty("Activity");
                    if (activityProperty != null)
                    {
                        var activity = activityProperty.GetValue(platformImpl);
                        if (activity != null)
                        {
                            // 使用反射调用 MoveTaskToBack
                            var moveTaskToBackMethod = activity.GetType().GetMethod("MoveTaskToBack");
                            if (moveTaskToBackMethod != null)
                            {
                                moveTaskToBackMethod.Invoke(activity, new object[] { true });
                                Console.WriteLine("应用已最小化到后台");
                                return;
                            }
                        }
                    }
                }
            }
            
            // 如果无法获取 Activity，记录日志
            Console.WriteLine("无法获取 Android Activity，应用将保持在前台");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Failed to minimize: {ex.Message}");
            Console.WriteLine($"Stack trace: {ex.StackTrace}");
        }
    }
    
    private void UpdateViewHeight()
    {
        var scrollingControl = this.FindControl<ScrollingSubtitleControl>("SubtitleControl");
        if (scrollingControl != null && scrollingControl.Height > 0)
        {
            System.Diagnostics.Debug.WriteLine($"[UpdateViewHeight] SubtitleHeight={scrollingControl.Height}");
            Console.WriteLine($"[UpdateViewHeight] SubtitleHeight={scrollingControl.Height}");
        }
    }
    
    private void OnLineCountExceeded(object? sender, EventArgs e)
    {
        // 行数超出限制，通知 ViewModel 清空缓冲区
        if (_viewModel != null)
        {
            Console.WriteLine("[MainView] 行数超出限制，清空缓冲区");
            _viewModel.ClearBuffer();
        }
    }
}
