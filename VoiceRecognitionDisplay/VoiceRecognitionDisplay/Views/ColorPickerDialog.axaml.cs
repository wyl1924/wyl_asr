using Avalonia.Controls;
using VoiceRecognitionDisplay.ViewModels;

namespace VoiceRecognitionDisplay.Views;

public partial class ColorPickerDialog : Window
{
    public ColorPickerDialog()
    {
        InitializeComponent();
    }
    
    protected override void OnDataContextChanged(System.EventArgs e)
    {
        base.OnDataContextChanged(e);
        
        if (DataContext is ColorPickerViewModel viewModel)
        {
            viewModel.ColorConfirmed += (s, color) =>
            {
                Close(color);
            };
            
            viewModel.ColorCancelled += (s, args) =>
            {
                Close(null);
            };
        }
    }
}
