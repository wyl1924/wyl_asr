using System;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Media.Imaging;
using QRCoder;

namespace VoiceRecognitionDisplay.Services;

public class ShareService
{
    public Func<Avalonia.Controls.TopLevel?>? TopLevelProvider { get; set; }

    public async Task<string> CreateShareLinkAsync(string content)
    {
        // 模拟创建分享链接
        // 在实际应用中，这里应该调用后端 API 上传内容并获取分享链接
        await Task.Delay(100); // 模拟网络延迟
        
        var linkId = Guid.NewGuid().ToString("N").Substring(0, 8);
        return $"https://share.example.com/{linkId}";
    }

    public Bitmap GenerateQRCode(string url, int size = 200)
    {
        try
        {
            using var qrGenerator = new QRCodeGenerator();
            using var qrCodeData = qrGenerator.CreateQrCode(url, QRCodeGenerator.ECCLevel.Q);
            using var qrCode = new PngByteQRCode(qrCodeData);
            
            var qrCodeBytes = qrCode.GetGraphic(20);
            
            using var stream = new System.IO.MemoryStream(qrCodeBytes);
            return new Bitmap(stream);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"生成二维码失败: {ex.Message}");
            throw;
        }
    }

    public async Task<bool> CopyToClipboardAsync(string text)
    {
        try
        {
            var topLevel = TopLevelProvider?.Invoke();

            if (topLevel == null)
            {
                switch (Avalonia.Application.Current?.ApplicationLifetime)
                {
                    case Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop:
                        topLevel = desktop.MainWindow;
                        break;
                    case Avalonia.Controls.ApplicationLifetimes.ISingleTopLevelApplicationLifetime singleTopLevel:
                        topLevel = singleTopLevel.GetType().GetProperty("TopLevel")?.GetValue(singleTopLevel) as Avalonia.Controls.TopLevel;
                        break;
                }
            }
                
            if (topLevel?.Clipboard != null)
            {
                await topLevel.Clipboard.SetTextAsync(text);
                return true;
            }
            return false;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"复制到剪贴板失败: {ex.Message}");
            return false;
        }
    }
}
