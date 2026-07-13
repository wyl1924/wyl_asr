# macOS Platform Assets

This folder contains macOS-specific resources for the Voice Recognition Display application.

## Icon Files

Place your macOS application icon files here:
- `app-icon.icns` - macOS icon bundle (required for proper macOS integration)

## Creating .icns Files

To create an .icns file from PNG images:

1. Create PNG files at these sizes:
   - icon_16x16.png
   - icon_32x32.png
   - icon_64x64.png
   - icon_128x128.png
   - icon_256x256.png
   - icon_512x512.png
   - icon_1024x1024.png

2. Use iconutil (built into macOS):
   ```bash
   mkdir app-icon.iconset
   # Copy your PNGs into the iconset folder with proper naming
   iconutil -c icns app-icon.iconset
   ```

## Usage

The .icns file will be used for:
- Application icon in Finder
- Dock icon
- Application bundle icon
- Window title bar icon
