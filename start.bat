@echo off
setlocal

:: Set title for launcher window
title SUPADSP - Smart City Platform Launcher

:: Change directory to repository root
cd /d "%~dp0"

echo ====================================================================
echo        SUPADSP - Hyderabad Smart City AI Platform Launcher
echo ====================================================================
echo.

:: 1. Verify Python availability
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python 3.10+ and ensure 'Add Python to PATH' is checked.
    pause
    exit /b 1
)

:: 2. Verify Node.js / npm availability
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm was not found in PATH.
    echo Please install Node.js v18+ from https://nodejs.org/
    pause
    exit /b 1
)

:: 3. Ensure .env exists
if not exist ".env" (
    if exist ".env.example" (
        echo [*] .env not found. Creating .env from .env.example...
        copy ".env.example" ".env" >nul
    )
)

:: 4. Ensure frontend dependencies are installed
if not exist "frontend\node_modules" (
    echo [*] Frontend node_modules not found. Running npm install...
    cd frontend
    call npm install
    cd /d "%~dp0"
)

:: 5. Activate virtual environment if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: 6. Set project root in PYTHONPATH
set PYTHONPATH=%CD%

echo [*] Launching Supervisor Gateway (Port 8000)...
start "SUPADSP - Supervisor Gateway (Port 8000)" cmd /k "title SUPADSP - Supervisor Gateway (Port 8000) && echo Starting Supervisor Gateway on http://127.0.0.1:8000 ... && python -m uvicorn backend.supervisor.main:app --host 127.0.0.1 --port 8000 --reload"

echo [*] Launching Pollution Agent (Port 8002)...
start "SUPADSP - Pollution Agent (Port 8002)" cmd /k "title SUPADSP - Pollution Agent (Port 8002) && echo Starting Pollution Agent on http://127.0.0.1:8002 ... && python -m uvicorn backend.agents.pollution_agent.main:app --host 127.0.0.1 --port 8002 --reload"

echo [*] Launching Frontend Vite Dev Server (Port 3000)...
start "SUPADSP - Frontend (Port 3000)" cmd /k "title SUPADSP - Frontend (Port 3000) && cd frontend && echo Starting Frontend on http://localhost:3000 ... && npm run dev"

echo.
echo ====================================================================
echo  All services have been launched in dedicated terminal windows:
echo.
echo   * Frontend Dashboard:   http://localhost:3000
echo   * Supervisor Gateway:   http://localhost:8000  (Docs: http://localhost:8000/docs)
echo   * Pollution Agent API:  http://localhost:8002  (Docs: http://localhost:8002/docs)
echo.
echo  To stop all services, run: .\stop.bat or close the individual windows.
echo ====================================================================
echo.
