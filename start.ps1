<#
.SYNOPSIS
    Starts The Brain - Multimodal RAG & 3D Knowledge Graph Service
#>

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "                     STARTING THE BRAIN SERVICE                       " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. Ensure required data directories exist
@("data/rag_storage", "data/uploads", "data/output") | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Path $_ -Force | Out-Null
    }
}

# 2. Check virtual environment
$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Virtual environment not found at $PythonExe" -ForegroundColor Red
    exit 1
}

# 3. Check for Ollama
$env:OLLAMA_NUM_PARALLEL = "2"
$env:OLLAMA_MAX_LOADED_MODELS = "2"
$OllamaDir = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
if (Test-Path (Join-Path $OllamaDir "ollama.exe")) {
    $env:PATH = "$OllamaDir;$env:PATH"
}
$OllamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if ($OllamaCmd) {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 2 -ErrorAction Stop
        Write-Host "[INFO] Ollama service is active." -ForegroundColor Green
    } catch {
        Write-Host "[INFO] Starting Ollama serve in background (parallel slots=4)..." -ForegroundColor Yellow
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }
} else {
    Write-Host "[INFO] Ollama not found in PATH. Ensure your configured LLM engine is running." -ForegroundColor Gray
}

# 4. Start FastAPI server via Uvicorn
Write-Host "[INFO] Launching FastAPI on http://127.0.0.1:8100 ..." -ForegroundColor Green
Write-Host "[INFO] Access Web UI at: http://127.0.0.1:8100/ or http://127.0.0.1:8100/ui/" -ForegroundColor Cyan
Write-Host ""

& $PythonExe -m uvicorn app:app --host 0.0.0.0 --port 8100
