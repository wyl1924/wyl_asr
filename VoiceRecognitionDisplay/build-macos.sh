#!/bin/bash

echo "========================================"
echo "macOS Desktop Build Script"
echo "========================================"
echo ""

cd VoiceRecognitionDisplay

echo "[1/3] Cleaning project..."
dotnet clean

echo ""
echo "[2/3] Restoring dependencies..."
dotnet restore

echo ""
echo "[3/3] Publishing macOS application..."
dotnet publish -c Release -r osx-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true

echo ""
echo "========================================"
echo "Build Complete!"
echo "========================================"
echo ""
echo "Application Location:"
find bin/Release/net8.0/osx-x64/publish -name "VoiceRecognitionDisplay" -o -name "VoiceRecognitionDisplay.app" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "No application found - check errors above"
fi
echo ""

# Make executable
chmod +x bin/Release/net8.0/osx-x64/publish/VoiceRecognitionDisplay 2>/dev/null

echo "To run the application:"
echo "  ./bin/Release/net8.0/osx-x64/publish/VoiceRecognitionDisplay"
echo ""
