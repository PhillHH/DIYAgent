param(
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "Aktiviere virtuelle Umgebung (.venv)" -ForegroundColor Cyan
& ".\.venv\Scripts\Activate.ps1"

Write-Host "Starte uvicorn mit Reload" -ForegroundColor Cyan
uvicorn api.main:app --host $ListenHost --port $Port --reload

