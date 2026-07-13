@echo off
chcp 65001 >nul
echo ========================================
echo Windows Desktop Build Script
echo ========================================
echo.

cd VoiceRecognitionDisplay

echo [1/3] Cleaning project...
dotnet clean

echo.
echo [2/3] Restoring dependencies...
dotnet restore

echo.
echo [3/3] Publishing Windows executable...
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Executable Location:
dir /b /s bin\Release\net8.0\win-x64\publish\*.exe 2>nul
if errorlevel 1 echo No executable found - check errors above
echo.

pause
