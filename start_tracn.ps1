$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Url = "http://127.0.0.1:5173/"
$EnvFile = Join-Path $Backend ".env"
$EnvExample = Join-Path $Backend ".env.example"
$Database = Join-Path $Backend "tracn.db"
$LogDir = Join-Path $Root "logs"
$BackendOutLog = Join-Path $LogDir "backend.out.log"
$BackendErrLog = Join-Path $LogDir "backend.err.log"
$FrontendOutLog = Join-Path $LogDir "frontend.out.log"
$FrontendErrLog = Join-Path $LogDir "frontend.err.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Creating backend virtual environment..."
    python -m venv (Join-Path $Backend ".venv")
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment could not be created: $Python"
}

Write-Host "Checking backend dependencies..."
& $Python -m pip install -r (Join-Path $Backend "requirements.txt") | Out-Host

if (-not (Test-Path -LiteralPath $EnvFile) -and (Test-Path -LiteralPath $EnvExample)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
}

if (-not (Test-Path -LiteralPath (Join-Path $Frontend "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    & npm.cmd install --prefix $Frontend | Out-Host
}

if (-not (Test-Path -LiteralPath $Database)) {
    Write-Host "Creating local database..."
    & $Python -c "from app.main import app; print('database initialized')" | Out-Host
    Get-ChildItem -Path (Join-Path $Root "data\import_batches") -Filter "*.json" |
        Sort-Object Name |
        ForEach-Object {
            Write-Host "Importing $($_.Name)..."
            & $Python (Join-Path $Backend "scripts\import_teachers.py") $_.FullName | Out-Host
        }
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
    -RedirectStandardOutput $BackendOutLog `
    -RedirectStandardError $BackendErrLog `
    -WindowStyle Hidden

Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
    -WorkingDirectory $Frontend `
    -RedirectStandardOutput $FrontendOutLog `
    -RedirectStandardError $FrontendErrLog `
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
    Write-Host "TraCN did not become reachable within 25 seconds."
    Write-Host "Backend logs: $BackendOutLog ; $BackendErrLog"
    Write-Host "Frontend logs: $FrontendOutLog ; $FrontendErrLog"
    throw "TraCN startup failed. Check the log files above."
}

Start-Process $Url
Write-Host "TraCN is running: $Url"
