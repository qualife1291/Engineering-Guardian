@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
echo.
echo Engineering Guardian - Windows Native
echo This launcher only reads source; the local virtual environment is created beside the launcher.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_windows.ps1"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo Startup failed. See docs\WINDOWS_SETUP_VI.md for troubleshooting.
  pause
)
exit /b %RESULT%
