$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Url = "http://127.0.0.1:5173/"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Backend virtual environment was not found: $Python"
}

foreach ($port in 8000, 5173) {
    Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -and $_ -ne $PID } |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

Start-Process -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $Backend `
    -WindowStyle Hidden

Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
    -WorkingDirectory $Frontend `
    -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds(25)
do {
    Start-Sleep -Milliseconds 700
    try {
        $backendOk = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
        $frontendOk = (Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    }
    catch {
        $backendOk = $false
        $frontendOk = $false
    }
} until (($backendOk -and $frontendOk) -or (Get-Date) -gt $deadline)

if (-not ($backendOk -and $frontendOk)) {
    throw "TraCN did not become reachable within 25 seconds."
}

Start-Process $Url
Write-Host "TraCN is running: $Url"
