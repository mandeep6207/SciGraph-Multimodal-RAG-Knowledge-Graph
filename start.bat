@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo                      STARTING THE BRAIN SERVICE
echo ======================================================================

cd /d "%~dp0"

:: 1. Ensure required directories exist
if not exist "data\rag_storage" mkdir "data\rag_storage"
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\output" mkdir "data\output"

:: 2. Check virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
    pause
    exit /b 1
)

:: 3. Check for Ollama
set "OLLAMA_NUM_PARALLEL=2"
set "OLLAMA_MAX_LOADED_MODELS=2"
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\Ollama;!PATH!"
)
where ollama >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] Checking Ollama service...
    curl -s http://127.0.0.1:11434/api/version >nul 2>nul
    if !ERRORLEVEL! neq 0 (
        echo [INFO] Starting Ollama in the background (parallel slots=4)...
        start "" /b ollama serve >nul 2>&1
        timeout /t 2 /nobreak >nul
    ) else (
        echo [INFO] Ollama service is active.
    )
) else (
    echo [INFO] Ollama CLI not in PATH. Ensure your LLM provider is running.
)

:: 4. Start The Brain via Uvicorn
echo [INFO] Starting FastAPI application on http://127.0.0.1:8100 ...
echo [INFO] Frontend UI available at: http://127.0.0.1:8100/
echo.

".venv\Scripts\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8100

pause
