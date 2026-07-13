#!/bin/bash

echo "Building Subtitle Display Application..."
echo ""

# Restore dependencies
echo "[1/3] Restoring dependencies..."
dotnet restore
if [ $? -ne 0 ]; then
    echo "Failed to restore dependencies"
    exit 1
fi

# Build the project
echo ""
echo "[2/3] Building project..."
dotnet build -c Release
if [ $? -ne 0 ]; then
    echo "Failed to build project"
    exit 1
fi

# Detect OS and publish accordingly
echo ""
echo "[3/3] Publishing single-file executable..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    dotnet publish -c Release -r osx-x64 --self-contained -p:PublishSingleFile=true -p:PublishTrimmed=false
    PUBLISH_PATH="bin/Release/net8.0/osx-x64/publish/SubtitleDisplay"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    dotnet publish -c Release -r linux-x64 --self-contained -p:PublishSingleFile=true -p:PublishTrimmed=false
    PUBLISH_PATH="bin/Release/net8.0/linux-x64/publish/SubtitleDisplay"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

if [ $? -ne 0 ]; then
    echo "Failed to publish project"
    exit 1
fi

echo ""
echo "========================================"
echo "Build completed successfully!"
echo "Executable location: $PUBLISH_PATH"
echo "========================================"
echo ""
