$ErrorActionPreference = "Continue"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$checks = @(
    @{ Name = "Frontend"; Url = "http://127.0.0.1:5173/" },
    @{ Name = "Backend"; Url = "http://127.0.0.1:8000/api/health" }
)

Write-Host "TraCN diagnostic check"
Write-Host "Project: $Root"

foreach ($check in $checks) {
    try {
        $response = Invoke-WebRequest -Uri $check.Url -UseBasicParsing -TimeoutSec 5
        Write-Host "$($check.Name): OK $($response.StatusCode) $($check.Url)"
    }
    catch {
        Write-Host "$($check.Name): NOT REACHABLE $($check.Url)"
        Write-Host "  $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "Ports:"
Get-NetTCPConnection -LocalPort 5173,8000 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,State,OwningProcess |
    Format-Table -AutoSize

Write-Host ""
Write-Host "If either service is not reachable, run:"
Write-Host "  D:\TraCN\start_tracn.cmd"
