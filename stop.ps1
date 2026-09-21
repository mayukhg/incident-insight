# Stops the Incident Insight API and cockpit started by start.ps1.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

$ApiPidFile = Join-Path $PSScriptRoot ".incident-insight-api.pid"
$WebPidFile = Join-Path $PSScriptRoot ".incident-insight-web.pid"

function Stop-TrackedProcess([string] $PidFile, [string] $Label) {
    if (-not (Test-Path $PidFile)) {
        Write-Host "No $Label PID file ($PidFile)."
        return
    }
    $procId = [int](Get-Content $PidFile | Select-Object -First 1)
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-Host "$Label process $procId is not running. Cleaning up stale PID file."
        Remove-Item -ErrorAction SilentlyContinue $PidFile
        return
    }
    Write-Host "Stopping $Label (PID $procId)..."
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $procId -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 10; $i++) {
        if (-not (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
            Remove-Item -ErrorAction SilentlyContinue $PidFile
            Write-Host "Stopped $Label."
            return
        }
        Start-Sleep -Seconds 1
    }
    Write-Host "$Label did not exit in time, forcing..."
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    Remove-Item -ErrorAction SilentlyContinue $PidFile
    Write-Host "Stopped $Label."
}

if ((-not (Test-Path $ApiPidFile)) -and (-not (Test-Path $WebPidFile))) {
    Write-Host "No PID files found — Incident Insight doesn't look like it's running via start.ps1."
    exit 0
}

Stop-TrackedProcess $WebPidFile "cockpit"
Stop-TrackedProcess $ApiPidFile "RCA API"
Write-Host "Stopped."
