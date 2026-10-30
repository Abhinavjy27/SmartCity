@echo off
setlocal

title SUPADSP - Stop Services

echo ====================================================================
echo        SUPADSP - Stopping Frontend and Backend Services
echo ====================================================================
echo.

for %%P in (8000 8002 3000) do (
    for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /r /c:":%%P .*LISTENING"') do (
        echo [*] Stopping process %%a on port %%P...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo [*] All SUPADSP services on ports 8000, 8002, and 3000 stopped.
echo.
