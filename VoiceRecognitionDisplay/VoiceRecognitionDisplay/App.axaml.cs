using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;

namespace VoiceRecognitionDisplay;

public partial class App : Application
{
    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {
        // 注意：实际的初始化逻辑在平台特定的 App.axaml.cs 中
        // 例如：VoiceRecognitionDisplay.Desktop/App.axaml.cs
        base.OnFrameworkInitializationCompleted();
    }
}
