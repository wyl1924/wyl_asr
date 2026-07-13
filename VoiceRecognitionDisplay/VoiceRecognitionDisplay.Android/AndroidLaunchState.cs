namespace VoiceRecognitionDisplay.Android;

internal static class AndroidLaunchState
{
    internal const string ActionExtraName = "action";
    internal const string OpenSettingsAction = "open_settings";
    internal const string OpenShareAction = "open_share";

    private static readonly object SyncRoot = new();
    private static string? _pendingAction;

    internal static void SetPendingAction(string? action)
    {
        lock (SyncRoot)
        {
            _pendingAction = action;
        }
    }

    internal static string? TakePendingAction()
    {
        lock (SyncRoot)
        {
            var action = _pendingAction;
            _pendingAction = null;
            return action;
        }
    }

    internal static void ClearPendingAction(string? action = null)
    {
        lock (SyncRoot)
        {
            if (action == null || _pendingAction == action)
            {
                _pendingAction = null;
            }
        }
    }
}
