using Android.App;
using Android.Content;
using Android.Content.PM;
using Android.OS;
using Android.Runtime;
using Android.Views;
using Avalonia;
using Avalonia.Android;
using System;
using VoiceRecognitionDisplay.Android.Services;

namespace VoiceRecognitionDisplay.Android;

[Activity(
    Name = "com.smartmeeting.display.MainActivity",
    Label = "智能会议",
    Theme = "@style/TransparentFloatingTheme",
    ConfigurationChanges = ConfigChanges.Orientation | ConfigChanges.ScreenSize | ConfigChanges.UiMode,
    ScreenOrientation = ScreenOrientation.Unspecified,
    LaunchMode = LaunchMode.SingleTop,
    ExcludeFromRecents = true,
    WindowSoftInputMode = SoftInput.AdjustResize)]
[Register("com.smartmeeting.display.MainActivity")]
public class MainActivity : AvaloniaMainActivity<App>
{
    private string? _startupAction;

    protected override void OnCreate(Bundle? savedInstanceState)
    {
        _startupAction = Intent?.GetStringExtra(AndroidLaunchState.ActionExtraName);
        AndroidLaunchState.SetPendingAction(_startupAction);

        AndroidDiagnostics.WriteLine(
            AndroidDiagnostics.WindowLogFileName,
            $"[MainActivity] OnCreate action={_startupAction ?? "(none)"}");

        base.OnCreate(savedInstanceState);

        if (string.IsNullOrWhiteSpace(_startupAction))
        {
            Finish();
        }
    }

    protected override void OnDestroy()
    {
        AndroidLaunchState.ClearPendingAction(_startupAction);
        base.OnDestroy();
    }

    public void FinishTransientUi()
    {
        Finish();
    }

    public void SetExpandedMode(bool expanded)
    {
        _ = expanded;
    }

    public void ReloadOverlayAndFinish()
    {
        try
        {
            var intent = new Intent(this, typeof(OverlayService));
            intent.SetAction(VoiceRecognitionDisplay.Android.Services.OverlayService.ActionReloadSettings);

            if (Build.VERSION.SdkInt >= BuildVersionCodes.O)
            {
                StartForegroundService(intent);
            }
            else
            {
                StartService(intent);
            }
        }
        catch (Exception ex)
        {
            AndroidDiagnostics.WriteException(
                AndroidDiagnostics.CrashLogFileName,
                "MainActivity.ReloadOverlayAndFinish",
                ex);
        }
        finally
        {
            Finish();
        }
    }

    protected override AppBuilder CustomizeAppBuilder(AppBuilder builder)
        => base.CustomizeAppBuilder(builder)
            .LogToTrace();
}
