@echo off
echo ========================================
echo 安装 Android 工作负载
echo ========================================
echo.
echo 此脚本需要管理员权限
echo 请确保以管理员身份运行此脚本
echo.
pause

echo.
echo [1/3] 检查当前已安装的工作负载...
dotnet workload list

echo.
echo [2/3] 安装 Android 工作负载...
echo 这可能需要几分钟时间，请耐心等待...
dotnet workload install android

echo.
echo [3/3] 验证安装...
dotnet workload list

echo.
echo ========================================
echo ✅ 安装完成！
echo ========================================
echo.
echo 现在可以运行 build-android.bat 来构建APK了
echo.

pause
