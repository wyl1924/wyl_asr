using System;
using System.Globalization;
using Avalonia.Data.Converters;
using Avalonia.Media;

namespace VoiceRecognitionDisplay.Converters;

/// <summary>
/// 将布尔值转换为颜色的转换器
/// </summary>
public class BoolToColorConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is not bool boolValue)
            return new SolidColorBrush(Colors.White);

        // 如果有参数，使用参数指定的颜色
        if (parameter is string colorPair)
        {
            var colors = colorPair.Split(',');
            if (colors.Length == 2)
            {
                var colorString = boolValue ? colors[0] : colors[1];
                try
                {
                    return new SolidColorBrush(Color.Parse(colorString));
                }
                catch
                {
                    // 解析失败，使用默认值
                }
            }
        }

        // 默认：true = 灰色，false = 白色
        return new SolidColorBrush(boolValue ? Color.FromRgb(220, 220, 220) : Colors.White);
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        throw new NotImplementedException();
    }
}
