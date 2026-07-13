#!/usr/bin/env python3
"""
智能会议应用图标生成器
生成所有需要的 Android 图标尺寸
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_meeting_icon(size):
    """
    创建智能会议图标
    设计：麦克风 + 对话气泡的组合
    """
    # 创建带透明背景的图像
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 定义颜色
    primary_color = (33, 150, 243, 255)  # 蓝色
    accent_color = (255, 255, 255, 255)  # 白色
    shadow_color = (0, 0, 0, 50)  # 半透明黑色阴影
    
    # 计算尺寸比例
    padding = size * 0.1
    center_x = size / 2
    center_y = size / 2
    
    # 绘制圆形背景
    bg_radius = size * 0.45
    draw.ellipse(
        [center_x - bg_radius, center_y - bg_radius, 
         center_x + bg_radius, center_y + bg_radius],
        fill=primary_color
    )
    
    # 绘制麦克风主体（圆角矩形）
    mic_width = size * 0.15
    mic_height = size * 0.25
    mic_x = center_x - mic_width / 2
    mic_y = center_y - mic_height / 2 - size * 0.05
    
    # 麦克风圆角矩形
    draw.rounded_rectangle(
        [mic_x, mic_y, mic_x + mic_width, mic_y + mic_height],
        radius=mic_width / 2,
        fill=accent_color
    )
    
    # 绘制麦克风支架
    stand_width = size * 0.03
    stand_height = size * 0.15
    stand_x = center_x - stand_width / 2
    stand_y = mic_y + mic_height
    
    draw.rectangle(
        [stand_x, stand_y, stand_x + stand_width, stand_y + stand_height],
        fill=accent_color
    )
    
    # 绘制麦克风底座
    base_width = size * 0.25
    base_height = size * 0.04
    base_x = center_x - base_width / 2
    base_y = stand_y + stand_height
    
    draw.rounded_rectangle(
        [base_x, base_y, base_x + base_width, base_y + base_height],
        radius=base_height / 2,
        fill=accent_color
    )
    
    # 绘制声波（三条弧线）
    wave_color = (255, 255, 255, 180)
    for i in range(3):
        wave_offset = (i + 1) * size * 0.08
        wave_width = size * 0.02
        
        # 左侧声波
        draw.arc(
            [mic_x - wave_offset, mic_y - wave_offset / 2,
             mic_x, mic_y + mic_height + wave_offset / 2],
            start=90, end=270,
            fill=wave_color,
            width=int(wave_width)
        )
        
        # 右侧声波
        draw.arc(
            [mic_x + mic_width, mic_y - wave_offset / 2,
             mic_x + mic_width + wave_offset, mic_y + mic_height + wave_offset / 2],
            start=270, end=90,
            fill=wave_color,
            width=int(wave_width)
        )
    
    return img

def create_simple_icon(size):
    """
    创建简化版图标（用于小尺寸）
    """
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 定义颜色
    primary_color = (33, 150, 243, 255)  # 蓝色
    accent_color = (255, 255, 255, 255)  # 白色
    
    center_x = size / 2
    center_y = size / 2
    
    # 绘制圆形背景
    bg_radius = size * 0.45
    draw.ellipse(
        [center_x - bg_radius, center_y - bg_radius, 
         center_x + bg_radius, center_y + bg_radius],
        fill=primary_color
    )
    
    # 绘制简化的麦克风图标
    mic_width = size * 0.2
    mic_height = size * 0.3
    mic_x = center_x - mic_width / 2
    mic_y = center_y - mic_height / 2
    
    # 麦克风主体
    draw.rounded_rectangle(
        [mic_x, mic_y, mic_x + mic_width, mic_y + mic_height],
        radius=mic_width / 2,
        fill=accent_color
    )
    
    # 麦克风支架（简化）
    stand_width = size * 0.04
    stand_height = size * 0.1
    stand_x = center_x - stand_width / 2
    stand_y = mic_y + mic_height
    
    draw.rectangle(
        [stand_x, stand_y, stand_x + stand_width, stand_y + stand_height],
        fill=accent_color
    )
    
    return img

def generate_android_icons():
    """
    生成所有 Android 需要的图标尺寸
    """
    # 定义图标尺寸
    icon_sizes = {
        'mipmap-mdpi': 48,
        'mipmap-hdpi': 72,
        'mipmap-xhdpi': 96,
        'mipmap-xxhdpi': 144,
        'mipmap-xxxhdpi': 192
    }
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    android_dir = os.path.join(script_dir, 'VoiceRecognitionDisplay.Android', 'Resources')
    
    print("🎨 开始生成智能会议应用图标...")
    print(f"📁 输出目录: {android_dir}")
    print()
    
    for folder, size in icon_sizes.items():
        # 创建目录
        folder_path = os.path.join(android_dir, folder)
        os.makedirs(folder_path, exist_ok=True)
        
        # 生成图标
        if size <= 72:
            # 小尺寸使用简化版
            icon = create_simple_icon(size)
        else:
            # 大尺寸使用详细版
            icon = create_meeting_icon(size)
        
        # 保存图标
        icon_path = os.path.join(folder_path, 'ic_launcher.png')
        icon.save(icon_path, 'PNG')
        
        print(f"✅ 已生成: {folder}/ic_launcher.png ({size}x{size})")
        
        # 同时生成圆形图标（相同内容）
        round_icon_path = os.path.join(folder_path, 'ic_launcher_round.png')
        icon.save(round_icon_path, 'PNG')
        print(f"✅ 已生成: {folder}/ic_launcher_round.png ({size}x{size})")
    
    print()
    print("🎉 所有图标生成完成！")
    print()
    print("📝 下一步:")
    print("1. 检查生成的图标: VoiceRecognitionDisplay.Android/Resources/mipmap-*/")
    print("2. 运行构建脚本: build-android.bat (Windows) 或 ./build-android.sh (Mac/Linux)")
    print("3. 安装新的 APK 到设备")

if __name__ == '__main__':
    try:
        generate_android_icons()
    except ImportError:
        print("❌ 错误: 需要安装 Pillow 库")
        print()
        print("请运行以下命令安装:")
        print("  pip install Pillow")
        print()
        print("或者:")
        print("  pip3 install Pillow")
    except Exception as e:
        print(f"❌ 生成图标时出错: {e}")
        import traceback
        traceback.print_exc()
