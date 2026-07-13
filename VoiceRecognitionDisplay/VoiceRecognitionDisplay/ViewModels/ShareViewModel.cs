using System;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Avalonia.Media.Imaging;
using VoiceRecognitionDisplay.Services;

namespace VoiceRecognitionDisplay.ViewModels;

public partial class ShareViewModel : ViewModelBase
{
    private readonly ShareService _shareService;
    
    [ObservableProperty]
    private Bitmap? _qrCodeImage;
    
    [ObservableProperty]
    private string _fileName = "会议纪要";
    
    [ObservableProperty]
    private string _shareUrl = "";
    
    [ObservableProperty]
    private bool _isLoading = false;
    
    public event EventHandler? CloseRequested;
    
    public ShareViewModel(ShareService shareService)
    {
        _shareService = shareService;
    }
    
    public async Task InitializeAsync(string content, string fileName)
    {
        IsLoading = true;
        FileName = fileName;
        
        try
        {
            // 创建分享链接
            ShareUrl = await CreateShareLink(content);
            
            // 生成二维码
            GenerateQRCode(ShareUrl);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"初始化分享对话框失败: {ex.Message}");
            ShareUrl = "生成分享链接失败";
        }
        finally
        {
            IsLoading = false;
        }
    }
    
    [RelayCommand]
    private async Task CopyAsync()
    {
        if (!string.IsNullOrEmpty(ShareUrl))
        {
            var success = await _shareService.CopyToClipboardAsync(ShareUrl);
            if (success)
            {
                // 可以显示一个提示消息
                Console.WriteLine("链接已复制到剪贴板");
            }
        }
    }
    
    [RelayCommand]
    private void Close()
    {
        CloseRequested?.Invoke(this, EventArgs.Empty);
    }
    
    public void GenerateQRCode(string url)
    {
        try
        {
            QrCodeImage = _shareService.GenerateQRCode(url, 200);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"生成二维码失败: {ex.Message}");
        }
    }
    
    public async Task<string> CreateShareLink(string content)
    {
        return await _shareService.CreateShareLinkAsync(content);
    }
}
