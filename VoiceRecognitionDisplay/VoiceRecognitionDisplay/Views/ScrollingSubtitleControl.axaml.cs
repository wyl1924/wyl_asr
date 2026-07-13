using System;
using System.ComponentModel;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;

namespace VoiceRecognitionDisplay.Views;

public partial class ScrollingSubtitleControl : UserControl, INotifyPropertyChanged
{
    // 依赖属性
    public static readonly StyledProperty<string> ScrollingTextProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, string>(nameof(ScrollingText), "");
    
    public static readonly StyledProperty<string> RecognitionModeProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, string>(nameof(RecognitionMode), "2pass-online");
    
    public static readonly StyledProperty<int> ScrollSpeedProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, int>(nameof(ScrollSpeed), 60);
    
    public static readonly StyledProperty<IBrush> FontColorProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, IBrush>(nameof(FontColor), Brushes.White);
    
    public static readonly StyledProperty<FontFamily> FontFamilyProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, FontFamily>(nameof(FontFamily), new FontFamily("SimSun"));
    
    public static readonly StyledProperty<double> FontSizeProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, double>(nameof(FontSize), 14.0);
    
    public static readonly StyledProperty<FontWeight> FontWeightProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, FontWeight>(nameof(FontWeight), FontWeight.Normal);
    
    public static readonly StyledProperty<FontStyle> FontStyleProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, FontStyle>(nameof(FontStyle), FontStyle.Normal);
    
    public static readonly StyledProperty<int> MaxDisplayLinesProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, int>(nameof(MaxDisplayLines), 2);

    public static readonly StyledProperty<string> TranslationTextProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, string>(nameof(TranslationText), "");

    public static readonly StyledProperty<double> TranslationFontSizeProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, double>(nameof(TranslationFontSize), 12.0);

    public static readonly StyledProperty<IBrush> TranslationFontColorProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, IBrush>(nameof(TranslationFontColor), Brushes.LightGray);

    public static readonly StyledProperty<bool> HasTranslationProperty =
        AvaloniaProperty.Register<ScrollingSubtitleControl, bool>(nameof(HasTranslation), false);

    private int _currentLineCount = 0;
    private string _previousText = ""; // 记录上一次的文本
    
    public string ScrollingText
    {
        get => GetValue(ScrollingTextProperty);
        set => SetValue(ScrollingTextProperty, value);
    }
    
    public string RecognitionMode
    {
        get => GetValue(RecognitionModeProperty);
        set
        {
            SetValue(RecognitionModeProperty, value);
            OnPropertyChanged(nameof(RecognitionMode));
            OnPropertyChanged(nameof(RecognitionModeText));
            OnPropertyChanged(nameof(RecognitionModeBackground));
        }
    }
    
    public int ScrollSpeed
    {
        get => GetValue(ScrollSpeedProperty);
        set
        {
            SetValue(ScrollSpeedProperty, value);
            OnPropertyChanged(nameof(ScrollSpeed));
        }
    }
    
    public IBrush FontColor
    {
        get => GetValue(FontColorProperty);
        set
        {
            SetValue(FontColorProperty, value);
            OnPropertyChanged(nameof(FontColor));
        }
    }
    
    public new FontFamily FontFamily
    {
        get => GetValue(FontFamilyProperty);
        set
        {
            SetValue(FontFamilyProperty, value);
            OnPropertyChanged(nameof(FontFamily));
        }
    }
    
    public new double FontSize
    {
        get => GetValue(FontSizeProperty);
        set
        {
            SetValue(FontSizeProperty, value);
            OnPropertyChanged(nameof(FontSize));
        }
    }
    
    public new FontWeight FontWeight
    {
        get => GetValue(FontWeightProperty);
        set
        {
            SetValue(FontWeightProperty, value);
            OnPropertyChanged(nameof(FontWeight));
        }
    }
    
    public new FontStyle FontStyle
    {
        get => GetValue(FontStyleProperty);
        set
        {
            SetValue(FontStyleProperty, value);
            OnPropertyChanged(nameof(FontStyle));
        }
    }
    
    public int MaxDisplayLines
    {
        get => GetValue(MaxDisplayLinesProperty);
        set
        {
            SetValue(MaxDisplayLinesProperty, value);
            OnPropertyChanged(nameof(MaxDisplayLines));
            UpdateControlHeight();
        }
    }

    public string TranslationText
    {
        get => GetValue(TranslationTextProperty);
        set
        {
            SetValue(TranslationTextProperty, value);
            OnPropertyChanged(nameof(TranslationText));
            OnPropertyChanged(nameof(HasTranslation));
        }
    }

    public double TranslationFontSize
    {
        get => GetValue(TranslationFontSizeProperty);
        set
        {
            SetValue(TranslationFontSizeProperty, value);
            OnPropertyChanged(nameof(TranslationFontSize));
        }
    }

    public IBrush TranslationFontColor
    {
        get => GetValue(TranslationFontColorProperty);
        set
        {
            SetValue(TranslationFontColorProperty, value);
            OnPropertyChanged(nameof(TranslationFontColor));
        }
    }

    public bool HasTranslation
    {
        get => GetValue(HasTranslationProperty);
        set => SetValue(HasTranslationProperty, value);
    }

    // 计算属性用于绑定
    public string RecognitionModeText => RecognitionMode == "2pass-offline" ? "离线" : "在线";
    
    public IBrush RecognitionModeBackground => RecognitionMode == "2pass-offline" 
        ? new SolidColorBrush(Color.FromRgb(255, 152, 0)) // 橙色表示离线
        : new SolidColorBrush(Color.FromRgb(76, 175, 80)); // 绿色表示在线
    
    public new event PropertyChangedEventHandler? PropertyChanged;
    public event EventHandler? LineCountExceeded; // 行数超出事件
    
    public ScrollingSubtitleControl()
    {
        InitializeComponent();
        
        // 初始化高度
        UpdateControlHeight();
        
        // 监听属性变化
        ScrollingTextProperty.Changed.AddClassHandler<ScrollingSubtitleControl>((x, e) => 
        {
            var newValue = e.NewValue as string ?? "";
            Console.WriteLine($"[ScrollingSubtitleControl] ScrollingText 变化为: {newValue}");
            Console.WriteLine($"[ScrollingSubtitleControl] _previousText: '{x._previousText}'");
            Console.WriteLine($"[ScrollingSubtitleControl] newValue.Length: {newValue.Length}, _previousText.Length: {x._previousText?.Length ?? 0}");
            
            x.OnPropertyChanged(nameof(ScrollingText));
            
            // 只有在文本变长（累加）时才检查行数
            // 如果文本变短或为空，说明是清空后的第一条消息，不检查
            if (!string.IsNullOrEmpty(newValue) && !string.IsNullOrEmpty(x._previousText) && newValue.Length > x._previousText.Length)
            {
                Console.WriteLine($"[ScrollingSubtitleControl] 文本累加，检查行数");
                x.CheckLineCount();
            }
            else
            {
                Console.WriteLine($"[ScrollingSubtitleControl] 第一条消息或清空后，跳过行数检查");
            }
            
            x._previousText = newValue;
        });
        
        RecognitionModeProperty.Changed.AddClassHandler<ScrollingSubtitleControl>((x, e) =>
        {
            x.OnPropertyChanged(nameof(RecognitionMode));
            x.OnPropertyChanged(nameof(RecognitionModeText));
            x.OnPropertyChanged(nameof(RecognitionModeBackground));
        });

        TranslationTextProperty.Changed.AddClassHandler<ScrollingSubtitleControl>((x, e) =>
        {
            x.OnPropertyChanged(nameof(TranslationText));
            x.SetValue(HasTranslationProperty, !string.IsNullOrWhiteSpace(x.TranslationText));
            x.OnPropertyChanged(nameof(HasTranslation));
            x.UpdateControlHeight();
        });

        MaxDisplayLinesProperty.Changed.AddClassHandler<ScrollingSubtitleControl>((x, e) =>
        {
            x.UpdateControlHeight();
        });
    }
    
    private void UpdateControlHeight()
    {
        // 根据 MaxDisplayLines 计算控件高度
        // 中文 LineHeight = 24px, 翻译 LineHeight = 20px
        // Margin = 10px (上下各10px，共20px)
        double chineseLineHeight = 24.0;
        double translationLineHeight = 20.0;
        double separatorHeight = 1.0;
        double baseMargin = 12.0;

        double calculatedHeight = (MaxDisplayLines * chineseLineHeight) + baseMargin;

        // 如果有翻译，增加翻译文本的高度
        if (HasTranslation)
        {
            calculatedHeight += separatorHeight + 36.0 + translationLineHeight;
        }

        this.Height = calculatedHeight;
        Console.WriteLine($"[UpdateControlHeight] MaxDisplayLines={MaxDisplayLines}, HasTranslation={HasTranslation}, Height={calculatedHeight}");
    }
    
    protected void OnPropertyChanged(string propertyName)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
    
    private void CheckLineCount()
    {
        // 在布局完成后检查行数
        Avalonia.Threading.Dispatcher.UIThread.Post(() =>
        {
            var textBlock = this.FindControl<TextBlock>("ScrollingTextBlock");
            if (textBlock != null && !string.IsNullOrEmpty(textBlock.Text))
            {
                Console.WriteLine($"[CheckLineCount] 开始检查，文本: '{textBlock.Text}'");
                Console.WriteLine($"[CheckLineCount] 控件宽度: {this.Bounds.Width}, MaxDisplayLines: {MaxDisplayLines}");
                
                if (MaxDisplayLines == 1)
                {
                    // 1行模式：不换行，检查文本宽度是否超过窗口宽度
                    textBlock.TextWrapping = Avalonia.Media.TextWrapping.NoWrap;
                    textBlock.MaxLines = 0; // 不限制行数（因为不换行）
                    
                    // 强制测量文本（不限制宽度，让文本自然展开）
                    textBlock.Measure(new Size(double.PositiveInfinity, double.PositiveInfinity));
                    
                    var textWidth = textBlock.DesiredSize.Width;
                    var windowWidth = this.Bounds.Width - 20; // 减去边距（左右各10px）
                    
                    Console.WriteLine($"[CheckLineCount] 1行模式 - 文本宽度: {textWidth:F2}, 窗口宽度: {windowWidth:F2}");
                    
                    // 如果文本宽度超过窗口宽度，触发清空
                    if (textWidth > windowWidth)
                    {
                        Console.WriteLine($"[CheckLineCount] 文本宽度超出窗口，触发清空事件");
                        LineCountExceeded?.Invoke(this, EventArgs.Empty);
                    }
                    else
                    {
                        Console.WriteLine($"[CheckLineCount] 文本宽度未超限，继续累加");
                    }
                }
                else
                {
                    // 2+行模式：换行，检查实际行数是否超过 MaxDisplayLines
                    textBlock.TextWrapping = Avalonia.Media.TextWrapping.Wrap;
                    textBlock.MaxLines = MaxDisplayLines;
                    
                    // 强制测量文本（限制宽度为窗口宽度）
                    var windowWidth = this.Bounds.Width - 20; // 减去边距
                    textBlock.Measure(new Size(windowWidth, double.PositiveInfinity));
                    
                    var textHeight = textBlock.DesiredSize.Height;
                    var lineHeight = 24.0; // 与 AXAML 中的 LineHeight 一致
                    var actualLines = (int)Math.Ceiling(textHeight / lineHeight);
                    
                    _currentLineCount = actualLines;
                    
                    Console.WriteLine($"[CheckLineCount] 多行模式 - 文本高度: {textHeight:F2}, 行高: {lineHeight}, 实际行数: {actualLines}, 最大行数: {MaxDisplayLines}");
                    
                    // 如果实际行数超过最大行数，触发清空
                    if (actualLines > MaxDisplayLines)
                    {
                        Console.WriteLine($"[CheckLineCount] 行数超出限制，触发清空事件");
                        LineCountExceeded?.Invoke(this, EventArgs.Empty);
                    }
                    else
                    {
                        Console.WriteLine($"[CheckLineCount] 行数未超限，继续累加");
                    }
                }
            }
            else
            {
                Console.WriteLine($"[CheckLineCount] TextBlock 为空或文本为空，跳过检查");
            }
        }, Avalonia.Threading.DispatcherPriority.Render);
    }
    
    public int GetCurrentLineCount()
    {
        return _currentLineCount;
    }
    
    /// <summary>
    /// 手动触发行数检查（由 MainWindow 调用）
    /// </summary>
    public void CheckLineCountManually()
    {
        var currentText = ScrollingText;
        Console.WriteLine($"[CheckLineCountManually] 当前文本: '{currentText}'");
        Console.WriteLine($"[CheckLineCountManually] _previousText: '{_previousText}'");
        Console.WriteLine($"[CheckLineCountManually] 文本长度: {currentText?.Length ?? 0}, 上次长度: {_previousText?.Length ?? 0}");
        
        // 只有在文本变长（累加）时才检查行数
        if (!string.IsNullOrEmpty(currentText) && !string.IsNullOrEmpty(_previousText) && currentText.Length > _previousText.Length)
        {
            Console.WriteLine($"[CheckLineCountManually] 文本累加，检查行数");
            CheckLineCount();
        }
        else
        {
            Console.WriteLine($"[CheckLineCountManually] 第一条消息或清空后，跳过行数检查");
        }
        
        _previousText = currentText;
    }
}
