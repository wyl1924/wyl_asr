using System;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using VoiceRecognitionDisplay.ViewModels;

namespace VoiceRecognitionDisplay.Views;

public partial class ColorPickerPanel : UserControl
{
    private enum InteractionMode
    {
        None,
        ColorArea,
        HueBar,
        ValueBar
    }

    private IPointer? _activePointer;
    private InteractionMode _interactionMode;

    public ColorPickerPanel()
    {
        InitializeComponent();
    }

    private void ColorPickerArea_PointerPressed(object? sender, PointerPressedEventArgs e)
    {
        BeginInteraction(sender, e, InteractionMode.ColorArea);
    }

    private void ColorPickerArea_PointerMoved(object? sender, PointerEventArgs e)
    {
        ContinueInteraction(sender, e, InteractionMode.ColorArea);
    }

    private void HueBar_PointerPressed(object? sender, PointerPressedEventArgs e)
    {
        BeginInteraction(sender, e, InteractionMode.HueBar);
    }

    private void HueBar_PointerMoved(object? sender, PointerEventArgs e)
    {
        ContinueInteraction(sender, e, InteractionMode.HueBar);
    }

    private void ValueBar_PointerPressed(object? sender, PointerPressedEventArgs e)
    {
        BeginInteraction(sender, e, InteractionMode.ValueBar);
    }

    private void ValueBar_PointerMoved(object? sender, PointerEventArgs e)
    {
        ContinueInteraction(sender, e, InteractionMode.ValueBar);
    }

    private void InteractiveBorder_PointerReleased(object? sender, PointerReleasedEventArgs e)
    {
        if (_activePointer != e.Pointer)
        {
            return;
        }

        e.Pointer.Capture(null);
        _activePointer = null;
        _interactionMode = InteractionMode.None;
        e.Handled = true;
    }

    private void BeginInteraction(object? sender, PointerPressedEventArgs e, InteractionMode mode)
    {
        if (sender is not Border border || DataContext is not ColorPickerViewModel viewModel)
        {
            return;
        }

        _activePointer = e.Pointer;
        _interactionMode = mode;
        e.Pointer.Capture(border);

        ApplyInteraction(border, e.GetPosition(border), viewModel, mode);
        e.Handled = true;
    }

    private void ContinueInteraction(object? sender, PointerEventArgs e, InteractionMode mode)
    {
        if (_activePointer != e.Pointer || _interactionMode != mode)
        {
            return;
        }

        if (sender is not Border border || DataContext is not ColorPickerViewModel viewModel)
        {
            return;
        }

        ApplyInteraction(border, e.GetPosition(border), viewModel, mode);
        e.Handled = true;
    }

    private static void ApplyInteraction(
        Border border,
        Point position,
        ColorPickerViewModel viewModel,
        InteractionMode mode)
    {
        var width = Math.Max(border.Bounds.Width, 1);
        var height = Math.Max(border.Bounds.Height, 1);

        switch (mode)
        {
            case InteractionMode.ColorArea:
            {
                var saturation = ClampPercentage((position.X / width) * 100);
                var value = ClampPercentage((1 - position.Y / height) * 100);

                viewModel.Saturation = saturation;
                viewModel.Value = value;
                break;
            }
            case InteractionMode.HueBar:
            {
                var hue = Math.Max(0, Math.Min(360, (position.X / width) * 360));
                viewModel.Hue = hue;
                break;
            }
            case InteractionMode.ValueBar:
            {
                var value = ClampPercentage((1 - position.X / width) * 100);
                viewModel.Value = value;
                break;
            }
        }
    }

    private static double ClampPercentage(double value)
    {
        return Math.Max(0, Math.Min(100, value));
    }
}
