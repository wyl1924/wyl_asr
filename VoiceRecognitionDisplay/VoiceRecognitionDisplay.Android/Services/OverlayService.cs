using System;
using System.ComponentModel;
using Android.App;
using Android.Content;
using Android.Graphics;
using Android.OS;
using Android.Runtime;
using Android.Views;
using Avalonia;
using Avalonia.Android;
using Avalonia.Controls;
using global::VoiceRecognitionDisplay.Android;
using global::VoiceRecognitionDisplay.Models;
using global::VoiceRecognitionDisplay.Services;
using global::VoiceRecognitionDisplay.ViewModels;
using global::VoiceRecognitionDisplay.Views;

namespace VoiceRecognitionDisplay.Android.Services;

[Register("com.smartmeeting.display.Services.OverlayService")]
public class OverlayService : Service
{
    public const string ActionReloadSettings = "com.smartmeeting.display.action.RELOAD_SETTINGS";

    private const int NotificationId = 1001;
    private const string ChannelId = "overlay_service_channel";
    private const int BottomMarginDp = 10;
    private const int ModalGapDp = 12;

    private static readonly object AvaloniaSyncRoot = new();
    private static bool _avaloniaInitialized;

    private IWindowManager? _windowManager;
    private WindowManagerLayoutParams? _layoutParams;
    private WindowManagerLayoutParams? _modalLayoutParams;
    private AvaloniaView? _overlayView;
    private AvaloniaView? _modalOverlayView;
    private MainView? _mainView;
    private bool _isExpanded;
    private bool _isModalVisible;

    private ConfigurationManager? _configManager;
    private WebSocketService? _webSocketService;
    private ShareService? _shareService;
    private MainWindowViewModel? _viewModel;
    private SettingsModel _currentSettings = new();
    private string _connectionPlaceholderText = "等待连接服务器...";

    public override IBinder? OnBind(Intent? intent)
    {
        return null;
    }

    public override void OnCreate()
    {
        base.OnCreate();

        WriteLog("OnCreate - service created");

        CreateNotificationChannel();
        StartForeground(NotificationId, CreateNotification());

        EnsureAvaloniaInitialized();
        InitializeServices();
        CreateOverlayWindow();
    }

    public override StartCommandResult OnStartCommand(Intent? intent, StartCommandFlags flags, int startId)
    {
        if (intent?.Action == ActionReloadSettings)
        {
            ReloadSettings();
        }

        return StartCommandResult.Sticky;
    }

    public override void OnDestroy()
    {
        WriteLog("OnDestroy - service disposed");

        if (_windowManager != null && _modalOverlayView != null && _isModalVisible)
        {
            try
            {
                _windowManager.RemoveView(_modalOverlayView);
                _isModalVisible = false;
            }
            catch (Exception ex)
            {
                WriteException("RemoveModalView", ex);
            }
        }

        if (_windowManager != null && _overlayView != null)
        {
            try
            {
                _windowManager.RemoveView(_overlayView);
            }
            catch (Exception ex)
            {
                WriteException("RemoveView", ex);
            }
        }

        if (_viewModel != null)
        {
            _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
        }

        if (_webSocketService != null)
        {
            _webSocketService.ConnectionStatusChanged -= OnConnectionStatusChanged;
            _webSocketService.Dispose();
        }

        base.OnDestroy();
    }

    private void EnsureAvaloniaInitialized()
    {
        lock (AvaloniaSyncRoot)
        {
            if (_avaloniaInitialized || Avalonia.Application.Current != null)
            {
                _avaloniaInitialized = true;
                return;
            }

            try
            {
                AppBuilder.Configure<global::VoiceRecognitionDisplay.App>()
                    .UseAndroid()
                    .LogToTrace()
                    .SetupWithoutStarting();

                _avaloniaInitialized = true;
                WriteLog("Avalonia runtime initialized for overlay host");
            }
            catch (Exception ex)
            {
                if (Avalonia.Application.Current != null)
                {
                    _avaloniaInitialized = true;
                    WriteLog("Avalonia runtime already initialized by another host");
                    return;
                }

                WriteException("EnsureAvaloniaInitialized", ex);
                throw;
            }
        }
    }

    private void InitializeServices()
    {
        try
        {
            _configManager = new ConfigurationManager();
            _shareService = new ShareService();
            _currentSettings = _configManager.LoadSettings();

            _webSocketService = new WebSocketService(_configManager);
            _webSocketService.ServerUrl = _currentSettings.WebSocketUrl;
            _webSocketService.ConnectionStatusChanged += OnConnectionStatusChanged;

            _viewModel = new MainWindowViewModel(_webSocketService, _configManager)
            {
                ScreenSizeProvider = GetScreenSize
            };
            _viewModel.PropertyChanged += OnViewModelPropertyChanged;
            _viewModel.ApplySettings(_currentSettings);

            ApplyConnectionPlaceholderIfNeeded();
            _ = _webSocketService.ConnectAsync();

            WriteLog("Service initialization completed");
        }
        catch (Exception ex)
        {
            WriteException("InitializeServices", ex);
            throw;
        }
    }

    private void CreateNotificationChannel()
    {
        if (Build.VERSION.SdkInt < BuildVersionCodes.O)
        {
            return;
        }

        var channel = new NotificationChannel(
            ChannelId,
            "字幕悬浮窗服务",
            NotificationImportance.Low)
        {
            Description = "保持字幕悬浮窗运行"
        };

        var notificationManager = GetSystemService(NotificationService) as NotificationManager;
        notificationManager?.CreateNotificationChannel(channel);
    }

    private Notification CreateNotification()
    {
        var intent = new Intent(this, typeof(OverlayLauncherActivity));
        var pendingIntent = PendingIntent.GetActivity(
            this,
            0,
            intent,
            PendingIntentFlags.Immutable);

        var builder = Build.VERSION.SdkInt >= BuildVersionCodes.O
            ? new Notification.Builder(this, ChannelId)
            : new Notification.Builder(this);

        return builder
            .SetContentTitle("智能会议")
            .SetContentText("字幕悬浮窗正在运行")
            .SetSmallIcon(global::Android.Resource.Drawable.IcMenuInfoDetails)
            .SetContentIntent(pendingIntent)
            .SetOngoing(true)
            .Build();
    }

    private void CreateOverlayWindow()
    {
        if (_viewModel == null || _configManager == null || _shareService == null)
        {
            return;
        }

        try
        {
            _windowManager = GetSystemService(WindowService)?.JavaCast<IWindowManager>();
            if (_windowManager == null)
            {
                WriteLog("WindowManager is null");
                return;
            }

            _layoutParams = CreateOverlayLayoutParams(GetFallbackOverlaySize(), DpToPx(BottomMarginDp));
            ApplyWindowFlags(_layoutParams, isModal: false);

            _overlayView = CreateOverlayHostView();
            _mainView = new MainView(
                _viewModel,
                _configManager,
                _shareService,
                startupAction: null,
                setExpandedMode: OnExpandedModeChanged,
                closeHost: StopOverlay,
                showFloatingModal: ShowFloatingModal,
                closeFloatingModal: CloseFloatingModal);

            _overlayView.Content = _mainView;
            _windowManager.AddView(_overlayView, _layoutParams);
            RefreshTransparentHost(_overlayView);
            _overlayView.Post(() => RefreshTransparentHost(_overlayView));
            UpdateOverlayLayout();

            WriteLog("Overlay window created with Avalonia host");
        }
        catch (Exception ex)
        {
            WriteException("CreateOverlayWindow", ex);
            throw;
        }
    }

    private void StopOverlay()
    {
        WriteLog("Stop overlay requested");

        if (Build.VERSION.SdkInt >= BuildVersionCodes.N)
        {
            StopForeground(StopForegroundFlags.Remove);
        }
        else
        {
#pragma warning disable CA1422
            StopForeground(true);
#pragma warning restore CA1422
        }

        StopSelf();
    }

    private AvaloniaView CreateOverlayHostView()
    {
        var view = new AvaloniaView(this);
        view.SetBackgroundColor(Color.Transparent);
        view.Focusable = true;
        view.FocusableInTouchMode = true;
        view.Clickable = true;
        view.SetClipChildren(false);
        view.SetClipToPadding(false);
        return view;
    }

    private WindowManagerLayoutParams CreateOverlayLayoutParams(Size size, int bottomOffsetPx)
    {
        return new WindowManagerLayoutParams
        {
            Width = DpToPx((int)Math.Ceiling(size.Width)),
            Height = DpToPx((int)Math.Ceiling(size.Height)),
            Type = Build.VERSION.SdkInt >= BuildVersionCodes.O
                ? WindowManagerTypes.ApplicationOverlay
                : WindowManagerTypes.Phone,
            Format = Format.Translucent,
            Gravity = GravityFlags.Bottom | GravityFlags.CenterHorizontal,
            Y = bottomOffsetPx
        };
    }

    private void ShowFloatingModal(Control content)
    {
        if (_windowManager == null)
        {
            return;
        }

        new Handler(Looper.MainLooper!).Post(() =>
        {
            try
            {
                if (_isModalVisible && _modalOverlayView != null)
                {
                    _windowManager.RemoveView(_modalOverlayView);
                    _modalOverlayView.Content = null;
                    _isModalVisible = false;
                }

                _modalOverlayView = CreateOverlayHostView();
                _modalOverlayView.Content = new FloatingModalHost(content);
                _modalLayoutParams = CreateOverlayLayoutParams(
                    GetFallbackModalSize(content),
                    GetModalBottomOffsetPx());

                ApplyWindowFlags(_modalLayoutParams, isModal: true);
                UpdateModalLayoutCore();

                _windowManager.AddView(_modalOverlayView, _modalLayoutParams);
                _isModalVisible = true;

                RefreshTransparentHost(_modalOverlayView);
                _modalOverlayView.RequestLayout();
                _modalOverlayView.Post(() =>
                {
                    RefreshTransparentHost(_modalOverlayView);
                    UpdateModalLayout();
                });

                WriteLog($"Floating modal shown: {content.GetType().Name}");
            }
            catch (Exception ex)
            {
                WriteException("ShowFloatingModal", ex);
            }
        });
    }

    private void CloseFloatingModal()
    {
        if (_windowManager == null || _modalOverlayView == null || !_isModalVisible)
        {
            return;
        }

        new Handler(Looper.MainLooper!).Post(() =>
        {
            try
            {
                if (_windowManager != null && _modalOverlayView != null && _isModalVisible)
                {
                    _windowManager.RemoveView(_modalOverlayView);
                    _modalOverlayView.Content = null;
                    _modalOverlayView = null;
                    _isModalVisible = false;
                    WriteLog("Floating modal closed");
                }
            }
            catch (Exception ex)
            {
                WriteException("CloseFloatingModal", ex);
            }
        });
    }

    private void OnExpandedModeChanged(bool expanded)
    {
        _isExpanded = expanded;
        WriteLog($"Expanded mode changed: {expanded}");
        UpdateOverlayLayout();
    }

    private void ReloadSettings()
    {
        if (_configManager == null || _viewModel == null)
        {
            return;
        }

        try
        {
            _currentSettings = _configManager.LoadSettings();
            _viewModel.ApplySettings(_currentSettings);
            UpdateOverlayLayout();
            WriteLog("Settings reloaded");
        }
        catch (Exception ex)
        {
            WriteException("ReloadSettings", ex);
        }
    }

    private void OnViewModelPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == null)
        {
            return;
        }

        switch (e.PropertyName)
        {
            case nameof(MainWindowViewModel.WindowWidth):
            case nameof(MainWindowViewModel.MaxDisplayLines):
            case nameof(MainWindowViewModel.ScrollingText):
            case nameof(MainWindowViewModel.TranslationText):
            case nameof(MainWindowViewModel.FontSize):
                UpdateOverlayLayout();
                break;
        }
    }

    private void OnConnectionStatusChanged(object? sender, ConnectionStatus status)
    {
        WriteLog($"Connection status: {status}");

        _connectionPlaceholderText = status switch
        {
            ConnectionStatus.Connecting => "正在连接服务器...",
            ConnectionStatus.Connected => "已连接，等待字幕...",
            ConnectionStatus.Disconnected => "连接已断开",
            ConnectionStatus.Reconnecting => "正在重连...",
            ConnectionStatus.Failed => "连接失败",
            _ => "等待连接服务器..."
        };

        ApplyConnectionPlaceholderIfNeeded();
        UpdateOverlayLayout();
    }

    private void ApplyConnectionPlaceholderIfNeeded()
    {
        if (_viewModel == null || !string.IsNullOrWhiteSpace(_viewModel.ScrollingText))
        {
            return;
        }

        _viewModel.SpeakerName = "说话人";
        _viewModel.ScrollingText = _connectionPlaceholderText;
        _viewModel.TranslationText = string.Empty;
    }

    private void UpdateOverlayLayout()
    {
        if (_windowManager == null || _overlayView == null || _layoutParams == null)
        {
            return;
        }

        new Handler(Looper.MainLooper!).Post(() =>
        {
            try
            {
                var overlaySize = MeasureOverlaySize();
                _layoutParams.Width = DpToPx((int)Math.Ceiling(overlaySize.Width));
                _layoutParams.Height = DpToPx((int)Math.Ceiling(overlaySize.Height));
                _layoutParams.Y = DpToPx(BottomMarginDp);
                ApplyWindowFlags(_layoutParams, isModal: false);
                RefreshTransparentHost(_overlayView);
                _overlayView.RequestLayout();
                _windowManager.UpdateViewLayout(_overlayView, _layoutParams);

                if (_isModalVisible)
                {
                    UpdateModalLayoutCore();
                }

                WriteLog($"Overlay layout updated: {_layoutParams.Width}x{_layoutParams.Height}px expanded={_isExpanded}");
            }
            catch (Exception ex)
            {
                WriteException("UpdateOverlayLayout", ex);
            }
        });
    }

    private Size MeasureOverlaySize()
    {
        if (_mainView != null)
        {
            _mainView.InvalidateMeasure();
            _mainView.Measure(new Size(double.PositiveInfinity, double.PositiveInfinity));

            var desiredSize = _mainView.DesiredSize;
            if (desiredSize.Width > 1 && desiredSize.Height > 1)
            {
                return desiredSize;
            }
        }

        return GetFallbackOverlaySize();
    }

    private void UpdateModalLayout()
    {
        if (_windowManager == null || _modalOverlayView == null || _modalLayoutParams == null || !_isModalVisible)
        {
            return;
        }

        new Handler(Looper.MainLooper!).Post(() =>
        {
            try
            {
                UpdateModalLayoutCore();
            }
            catch (Exception ex)
            {
                WriteException("UpdateModalLayout", ex);
            }
        });
    }

    private void UpdateModalLayoutCore()
    {
        if (_windowManager == null || _modalOverlayView == null || _modalLayoutParams == null)
        {
            return;
        }

        var modalSize = MeasureModalSize();
        _modalLayoutParams.Width = DpToPx((int)Math.Ceiling(modalSize.Width));
        _modalLayoutParams.Height = DpToPx((int)Math.Ceiling(modalSize.Height));
        _modalLayoutParams.Y = GetModalBottomOffsetPx();
        ApplyWindowFlags(_modalLayoutParams, isModal: true);
        RefreshTransparentHost(_modalOverlayView);
        _modalOverlayView.RequestLayout();

        if (_isModalVisible)
        {
            _windowManager.UpdateViewLayout(_modalOverlayView, _modalLayoutParams);
        }
    }

    private Size MeasureModalSize()
    {
        if (_modalOverlayView?.Content is Control control)
        {
            control.InvalidateMeasure();
            control.Measure(new Size(double.PositiveInfinity, double.PositiveInfinity));

            var desiredSize = control.DesiredSize;
            if (desiredSize.Width > 1 && desiredSize.Height > 1)
            {
                return desiredSize;
            }

            return GetFallbackModalSize(control);
        }

        return new Size(320, 240);
    }

    private Size GetFallbackOverlaySize()
    {
        var width = Math.Max(280, _viewModel?.WindowWidth ?? 360);
        var subtitleHeight = GetFallbackSubtitleHeight();
        var totalHeight = 52 + 30 + 4 + subtitleHeight;
        return new Size(width, Math.Max(totalHeight, 110));
    }

    private double GetFallbackSubtitleHeight()
    {
        if (_viewModel == null)
        {
            return 80;
        }

        var height = (_viewModel.MaxDisplayLines * 24.0) + 20.0;
        if (!string.IsNullOrWhiteSpace(_viewModel.TranslationText))
        {
            height += 25.0;
        }

        return height;
    }

    private Size GetFallbackModalSize(Control? content)
    {
        return content switch
        {
            SettingsPanel => new Size(320, 580),
            SharePanel => new Size(450, 500),
            ColorPickerPanel => new Size(350, 420),
            _ => new Size(320, 240)
        };
    }

    private int GetModalBottomOffsetPx()
    {
        var overlayHeight = _layoutParams?.Height
            ?? DpToPx((int)Math.Ceiling(GetFallbackOverlaySize().Height));

        return overlayHeight + DpToPx(BottomMarginDp + ModalGapDp);
    }

    private void ApplyWindowFlags(WindowManagerLayoutParams? layoutParams, bool isModal)
    {
        if (layoutParams == null)
        {
            return;
        }

        layoutParams.Flags = isModal
            ? WindowManagerFlags.LayoutInScreen
            : WindowManagerFlags.NotTouchModal | WindowManagerFlags.LayoutInScreen;
    }

    private void RefreshTransparentHost(View? view)
    {
        if (view == null)
        {
            return;
        }

        try
        {
            ApplyTransparentBackgrounds(view);
        }
        catch (Exception ex)
        {
            WriteException("RefreshTransparentHost", ex);
        }
    }

    private void ApplyTransparentBackgrounds(View view)
    {
        view.SetBackgroundColor(Color.Transparent);

        if (view is SurfaceView surfaceView)
        {
            surfaceView.SetZOrderOnTop(true);
            surfaceView.SetZOrderMediaOverlay(true);
            surfaceView.Holder?.SetFormat(Format.Translucent);
            surfaceView.SetBackgroundColor(Color.Transparent);
        }

        if (view is TextureView textureView)
        {
            textureView.SetOpaque(false);
            textureView.SetBackgroundColor(Color.Transparent);
        }

        if (view is ViewGroup group)
        {
            group.SetClipChildren(false);
            group.SetClipToPadding(false);

            for (var i = 0; i < group.ChildCount; i++)
            {
                var child = group.GetChildAt(i);
                if (child != null)
                {
                    ApplyTransparentBackgrounds(child);
                }
            }
        }
    }

    private (double Width, double Height)? GetScreenSize()
    {
        var metrics = Resources?.DisplayMetrics;
        if (metrics == null)
        {
            return null;
        }

        var density = metrics.Density <= 0 ? 1.0 : metrics.Density;
        return (metrics.WidthPixels / density, metrics.HeightPixels / density);
    }

    private int DpToPx(int dp)
    {
        var density = Resources?.DisplayMetrics?.Density ?? 1.0f;
        return (int)(dp * density);
    }

    private void WriteLog(string message)
    {
        AndroidDiagnostics.WriteLine(AndroidDiagnostics.WindowLogFileName, $"[OverlayService] {message}");
    }

    private void WriteException(string context, Exception exception)
    {
        WriteLog($"{context} failed: {exception.Message}");
        AndroidDiagnostics.WriteException(AndroidDiagnostics.CrashLogFileName, $"OverlayService.{context}", exception);
    }
}
