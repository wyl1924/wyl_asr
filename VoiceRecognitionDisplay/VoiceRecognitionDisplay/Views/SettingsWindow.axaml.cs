using System;
using System.Diagnostics;
using Avalonia.Controls;
using VoiceRecognitionDisplay.ViewModels;

namespace VoiceRecognitionDisplay.Views;

public partial class SettingsWindow : Window
{
    public SettingsWindow()
    {
        InitializeComponent();
    }
    
    protected override void OnDataContextChanged(System.EventArgs e)
    {
        base.OnDataContextChanged(e);
        
        if (DataContext is SettingsViewModel viewModel)
        {
            Debug.WriteLine("SettingsWindow: DataContext set, subscribing to events");
            
            viewModel.SettingsSaved += (s, settings) =>
            {
                Debug.WriteLine($"SettingsWindow: SettingsSaved event received - BackgroundColor: {settings.BackgroundColor}");
                Debug.WriteLine("SettingsWindow: Closing with result = true");
                Close(true);
            };
            
            viewModel.SettingsCancelled += (s, args) =>
            {
                Debug.WriteLine("SettingsWindow: SettingsCancelled event received");
                Debug.WriteLine("SettingsWindow: Closing with result = false");
                Close(false);
            };
        }
    }
}
