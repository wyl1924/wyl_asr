@echo off
echo Building Subtitle Display Application...
echo.

REM Restore dependencies
echo [1/3] Restoring dependencies...
dotnet restore
if %errorlevel% neq 0 (
    echo Failed to restore dependencies
    pause
    exit /b %errorlevel%
)

REM Build the project
echo.
echo [2/3] Building project...
dotnet build -c Release
if %errorlevel% neq 0 (
    echo Failed to build project
    pause
    exit /b %errorlevel%
)

REM Publish single-file executable
echo.
echo [3/3] Publishing single-file executable...
dotnet publish -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -p:PublishTrimmed=false
if %errorlevel% neq 0 (
    echo Failed to publish project
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================
echo Build completed successfully!
echo Executable location: bin\Release\net8.0\win-x64\publish\SubtitleDisplay.exe
echo ========================================
echo.
pause
