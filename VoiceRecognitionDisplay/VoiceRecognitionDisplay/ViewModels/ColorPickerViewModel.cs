using System;
using Avalonia.Media;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace VoiceRecognitionDisplay.ViewModels;

public partial class ColorPickerViewModel : ViewModelBase
{
    private bool _isUpdating = false;
    
    [ObservableProperty]
    private double _hue = 0;
    
    [ObservableProperty]
    private double _saturation = 100;
    
    [ObservableProperty]
    private double _value = 100;
    
    [ObservableProperty]
    private string _hexColor = "#000000";
    
    [ObservableProperty]
    private Color _selectedColor = Colors.Black;
    
    [ObservableProperty]
    private IBrush _selectedBrush = new SolidColorBrush(Colors.Black);
    
    [ObservableProperty]
    private IBrush _hueColorBrush = new SolidColorBrush(Colors.Red);
    
    public event EventHandler<string>? ColorConfirmed;
    public event EventHandler? ColorCancelled;
    
    public ColorPickerViewModel()
    {
    }
    
    public ColorPickerViewModel(string initialColor)
    {
        if (!string.IsNullOrEmpty(initialColor) && initialColor.StartsWith("#"))
        {
            try
            {
                var color = Color.Parse(initialColor);
                SelectedColor = color;
                SelectedBrush = new SolidColorBrush(color);
                HexColor = initialColor.ToUpper();
                UpdateHsvFromColor();
            }
            catch
            {
                // Use default values
                InitializeDefaults();
            }
        }
        else
        {
            InitializeDefaults();
        }
    }
    
    private void InitializeDefaults()
    {
        SelectedColor = Colors.Red;
        SelectedBrush = new SolidColorBrush(Colors.Red);
        HueColorBrush = new SolidColorBrush(Colors.Red);
        HexColor = "#FF0000";
        Hue = 0;
        Saturation = 100;
        Value = 100;
    }
    
    partial void OnHueChanged(double value)
    {
        if (!_isUpdating)
        {
            // 更新纯色相背景
            var hueColor = HsvToRgb(value, 1.0, 1.0);
            HueColorBrush = new SolidColorBrush(hueColor);
            UpdateColorFromHsv();
        }
    }
    
    partial void OnSaturationChanged(double value)
    {
        if (!_isUpdating)
            UpdateColorFromHsv();
    }
    
    partial void OnValueChanged(double value)
    {
        if (!_isUpdating)
            UpdateColorFromHsv();
    }
    
    partial void OnHexColorChanged(string value)
    {
        if (_isUpdating)
            return;
            
        if (!string.IsNullOrEmpty(value) && value.StartsWith("#") && value.Length == 7)
        {
            try
            {
                var color = Color.Parse(value);
                SelectedColor = color;
                SelectedBrush = new SolidColorBrush(color);
                UpdateHsvFromColor();
            }
            catch
            {
                // Invalid hex color, ignore
            }
        }
    }
    
    private void UpdateColorFromHsv()
    {
        var color = HsvToRgb(Hue, Saturation / 100.0, Value / 100.0);
        SelectedColor = color;
        SelectedBrush = new SolidColorBrush(color);
        HexColor = $"#{color.R:X2}{color.G:X2}{color.B:X2}";
    }
    
    private void UpdateHsvFromColor()
    {
        var (h, s, v) = RgbToHsv(SelectedColor);
        
        // 临时禁用更新，避免循环
        _isUpdating = true;
        
        var tempHue = h;
        var tempSat = s * 100;
        var tempVal = v * 100;
        
        if (Math.Abs(Hue - tempHue) > 0.01)
            Hue = tempHue;
        if (Math.Abs(Saturation - tempSat) > 0.01)
            Saturation = tempSat;
        if (Math.Abs(Value - tempVal) > 0.01)
            Value = tempVal;
            
        _isUpdating = false;
    }
    
    private static Color HsvToRgb(double h, double s, double v)
    {
        var c = v * s;
        var x = c * (1 - Math.Abs((h / 60.0) % 2 - 1));
        var m = v - c;
        
        double r = 0, g = 0, b = 0;
        
        if (h < 60)
        {
            r = c; g = x; b = 0;
        }
        else if (h < 120)
        {
            r = x; g = c; b = 0;
        }
        else if (h < 180)
        {
            r = 0; g = c; b = x;
        }
        else if (h < 240)
        {
            r = 0; g = x; b = c;
        }
        else if (h < 300)
        {
            r = x; g = 0; b = c;
        }
        else
        {
            r = c; g = 0; b = x;
        }
        
        return Color.FromRgb(
            (byte)Math.Round((r + m) * 255),
            (byte)Math.Round((g + m) * 255),
            (byte)Math.Round((b + m) * 255)
        );
    }
    
    private static (double h, double s, double v) RgbToHsv(Color color)
    {
        var r = color.R / 255.0;
        var g = color.G / 255.0;
        var b = color.B / 255.0;
        
        var max = Math.Max(r, Math.Max(g, b));
        var min = Math.Min(r, Math.Min(g, b));
        var delta = max - min;
        
        double h = 0;
        if (delta != 0)
        {
            if (max == r)
                h = 60 * (((g - b) / delta) % 6);
            else if (max == g)
                h = 60 * (((b - r) / delta) + 2);
            else
                h = 60 * (((r - g) / delta) + 4);
        }
        
        if (h < 0) h += 360;
        
        var s = max == 0 ? 0 : delta / max;
        var v = max;
        
        return (h, s, v);
    }
    
    [RelayCommand]
    private void Confirm()
    {
        Console.WriteLine($"[ColorPicker] Confirm color={HexColor}");
        ColorConfirmed?.Invoke(this, HexColor);
    }
    
    [RelayCommand]
    private void Cancel()
    {
        Console.WriteLine("[ColorPicker] Cancel");
        ColorCancelled?.Invoke(this, EventArgs.Empty);
    }
}
