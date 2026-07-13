using System;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.VisualTree;

namespace VoiceRecognitionDisplay.Views;

public sealed class FloatingModalHost : UserControl
{
    public FloatingModalHost(Control content)
    {
        Background = Brushes.Transparent;
        Content = BuildRoot(content);
        AttachedToVisualTree += OnAttachedToVisualTree;
    }

    private static Grid BuildRoot(Control content)
    {
        var root = new Grid
        {
            Background = Brushes.Transparent,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Bottom
        };

        root.Children.Add(content);
        return root;
    }

    private void OnAttachedToVisualTree(object? sender, VisualTreeAttachmentEventArgs e)
    {
        try
        {
            var topLevel = TopLevel.GetTopLevel(this);
            if (topLevel == null)
            {
                return;
            }

            topLevel.TransparencyLevelHint = new[] { WindowTransparencyLevel.Transparent };
            topLevel.TransparencyBackgroundFallback = Brushes.Transparent;
            topLevel.Background = Brushes.Transparent;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[FloatingModalHost] 配置透明顶层失败: {ex.Message}");
        }
    }
}
