# Android 应用图标配置指南

## 图标要求

为"智能会议"应用准备以下尺寸的 PNG 图标：

### 必需的图标文件

将图标文件命名为 `ic_launcher.png` 并放置在对应目录：

```
Resources/
├── mipmap-mdpi/
│   └── ic_launcher.png      (48x48 像素)
├── mipmap-hdpi/
│   └── ic_launcher.png      (72x72 像素)
├── mipmap-xhdpi/
│   └── ic_launcher.png      (96x96 像素)
├── mipmap-xxhdpi/
│   └── ic_launcher.png      (144x144 像素)
└── mipmap-xxxhdpi/
    └── ic_launcher.png      (192x192 像素)
```

### 可选：圆形图标（Android 8.0+）

如果需要圆形图标，额外准备：

```
Resources/
├── mipmap-mdpi/
│   └── ic_launcher_round.png      (48x48 像素)
├── mipmap-hdpi/
│   └── ic_launcher_round.png      (72x72 像素)
├── mipmap-xhdpi/
│   └── ic_launcher_round.png      (96x96 像素)
├── mipmap-xxhdpi/
│   └── ic_launcher_round.png      (144x144 像素)
└── mipmap-xxxhdpi/
    └── ic_launcher_round.png      (192x192 像素)
```

## 图标设计建议

1. **主题**：会议相关（如麦克风、对话气泡、会议桌等）
2. **颜色**：使用品牌色，建议蓝色或绿色系
3. **风格**：简洁、现代、扁平化设计
4. **背景**：透明背景或纯色背景
5. **安全区域**：图标主体应在中心 80% 区域内

## 在线工具推荐

### 方法 1：使用在线图标生成器
- **Android Asset Studio**: https://romannurik.github.io/AndroidAssetStudio/
  - 上传一张 512x512 的图标
  - 自动生成所有尺寸
  - 下载后解压到 Resources 目录

### 方法 2：使用 AI 生成工具
- **Canva**: https://www.canva.com/
- **Figma**: https://www.figma.com/
- **Adobe Express**: https://www.adobe.com/express/

### 方法 3：使用图标库
- **Flaticon**: https://www.flaticon.com/
- **Icons8**: https://icons8.com/
- 搜索 "meeting" 或 "conference" 相关图标

## 快速生成命令（如果有 ImageMagick）

如果你有一张 512x512 的源图标 `icon_512.png`：

```bash
# 安装 ImageMagick
brew install imagemagick

# 生成所有尺寸
convert icon_512.png -resize 48x48 Resources/mipmap-mdpi/ic_launcher.png
convert icon_512.png -resize 72x72 Resources/mipmap-hdpi/ic_launcher.png
convert icon_512.png -resize 96x96 Resources/mipmap-xhdpi/ic_launcher.png
convert icon_512.png -resize 144x144 Resources/mipmap-xxhdpi/ic_launcher.png
convert icon_512.png -resize 192x192 Resources/mipmap-xxxhdpi/ic_launcher.png
```

## 配置完成后

图标文件准备好后，需要在项目文件中引用它们。
配置已自动完成，重新编译即可看到新图标。
