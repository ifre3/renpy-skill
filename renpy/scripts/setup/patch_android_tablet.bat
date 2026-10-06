@echo off
chcp 65001 >nul
title 安卓平板模式打包工具

echo ════════════════════════════════════════════
echo   安卓平板模式打包工具
echo ════════════════════════════════════════════
echo.
echo 请选择操作：
echo   [1] 应用补丁（强制平板模式）
echo   [2] 恢复原始逻辑
echo   [3] 查看状态
echo   [0] 退出
echo.

set /p choice="请输入数字 (0-3): "

if "%choice%"=="1" (
    echo.
    python "%~dp0patch_android_tablet.py" apply
    echo.
    echo 补丁已应用，请重新打包 APK。
    pause
) else if "%choice%"=="2" (
    echo.
    python "%~dp0patch_android_tablet.py" restore
    echo.
    pause
) else if "%choice%"=="3" (
    echo.
    python "%~dp0patch_android_tablet.py" status
    echo.
    pause
) else if "%choice%"=="0" (
    exit /b
) else (
    echo 无效输入，请重新运行。
    pause
)