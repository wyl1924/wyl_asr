using Android.App;
using Android.Content;
using Android.Content.PM;
using Android.OS;
using Android.Provider;
using Android.Runtime;
using System;
using VoiceRecognitionDisplay.Android.Services;

namespace VoiceRecognitionDisplay.Android;

[Activity(
    Name = "com.smartmeeting.display.OverlayLauncherActivity",
    Label = "智能会议",
    Theme = "@style/TransparentFloatingTheme",
    MainLauncher = true,
    ConfigurationChanges = ConfigChanges.Orientation | ConfigChanges.ScreenSize | ConfigChanges.UiMode,
    ScreenOrientation = ScreenOrientation.Unspecified,
    LaunchMode = LaunchMode.SingleTask,
    NoHistory = true,
    ExcludeFromRecents = true)]
[Register("com.smartmeeting.display.OverlayLauncherActivity")]
public class OverlayLauncherActivity : Activity
{
    private bool _waitingForOverlayPermission;

    protected override void OnCreate(Bundle? savedInstanceState)
    {
        base.OnCreate(savedInstanceState);

        AndroidDiagnostics.WriteLine(
            AndroidDiagnostics.WindowLogFileName,
            $"[OverlayLauncherActivity] OnCreate permission={CanDrawOverlay()}");

        HandleLaunch();
    }

    protected override void OnNewIntent(Intent? intent)
    {
        base.OnNewIntent(intent);
        Intent = intent;
        HandleLaunch();
    }

    protected override void OnResume()
    {
        base.OnResume();

        if (!_waitingForOverlayPermission)
        {
            return;
        }

        if (CanDrawOverlay())
        {
            _waitingForOverlayPermission = false;
            StartOverlayServiceAndFinish();
            return;
        }

        _waitingForOverlayPermission = false;
        ShowPermissionDialog();
    }

    private void HandleLaunch()
    {
        if (CanDrawOverlay())
        {
            StartOverlayServiceAndFinish();
            return;
        }

        RequestOverlayPermission();
    }

    private bool CanDrawOverlay()
    {
        return Build.VERSION.SdkInt < BuildVersionCodes.M || Settings.CanDrawOverlays(this);
    }

    private void RequestOverlayPermission()
    {
        if (Build.VERSION.SdkInt < BuildVersionCodes.M)
        {
            StartOverlayServiceAndFinish();
            return;
        }

        _waitingForOverlayPermission = true;

        AndroidDiagnostics.WriteLine(
            AndroidDiagnostics.WindowLogFileName,
            "[OverlayLauncherActivity] Requesting overlay permission");

        var intent = new Intent(Settings.ActionManageOverlayPermission);
        intent.SetData(global::Android.Net.Uri.Parse($"package:{PackageName}"));

        StartActivity(intent);
    }

    private void StartOverlayServiceAndFinish()
    {
        try
        {
            var intent = new Intent(this, typeof(OverlayService));

            if (Build.VERSION.SdkInt >= BuildVersionCodes.O)
            {
                StartForegroundService(intent);
            }
            else
            {
                StartService(intent);
            }

            AndroidDiagnostics.WriteLine(
                AndroidDiagnostics.WindowLogFileName,
                "[OverlayLauncherActivity] Overlay service started");
        }
        catch (Exception ex)
        {
            AndroidDiagnostics.WriteException(
                AndroidDiagnostics.CrashLogFileName,
                "OverlayLauncherActivity.StartOverlayServiceAndFinish",
                ex);
        }
        finally
        {
            Finish();
        }
    }

    private void ShowPermissionDialog()
    {
        new AlertDialog.Builder(this)
            .SetTitle("需要悬浮窗权限")!
            .SetMessage("只有授予悬浮窗权限后，字幕条才能只显示在底部一小块，并且不影响下面软件的操作。")!
            .SetPositiveButton("去设置", (_, _) => RequestOverlayPermission())!
            .SetNegativeButton("退出", (_, _) => Finish())!
            .SetCancelable(false)!
            .Show();
    }
}
