# Starts Incident Insight: FastAPI + DuckDB RCA engine and the TanStack cockpit.
# Usage: ./start.ps1 [-Port 8080] [-ApiPort 8000] [-HostAddress 127.0.0.1]
param(
    [int] $Port = 8080,
    [int] $ApiPort = 8000,
    [string] $HostAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

foreach ($envFile in @((Join-Path $PSScriptRoot "backend\.env"), (Join-Path $PSScriptRoot ".env"))) {
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { return }
            $pair = $line.Split("=", 2)
            [System.Environment]::SetEnvironmentVariable($pair[0].Trim(), $pair[1].Trim().Trim('"').Trim("'"), "Process")
        }
    }
}

$ApiPidFile = Join-Path $PSScriptRoot ".incident-insight-api.pid"
$WebPidFile = Join-Path $PSScriptRoot ".incident-insight-web.pid"
$ApiLogFile = Join-Path $PSScriptRoot ".incident-insight-api.log"
$WebLogFile = Join-Path $PSScriptRoot ".incident-insight-web.log"

function Test-PidRunning([string] $PidFile) {
    if (-not (Test-Path $PidFile)) { return $false }
    $procId = [int](Get-Content $PidFile | Select-Object -First 1)
    return $null -ne (Get-Process -Id $procId -ErrorAction SilentlyContinue)
}

if ((Test-PidRunning $ApiPidFile) -or (Test-PidRunning $WebPidFile)) {
    Write-Host "Incident Insight looks like it is already running. Run ./stop.ps1 first if you want to restart it."
    exit 0
}
Remove-Item -ErrorAction SilentlyContinue $ApiPidFile, $WebPidFile

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js is required but was not found on PATH. Install it from https://nodejs.org (v18+)."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Error "Python 3 is required but was not found on PATH. Install Python 3.9+ from https://www.python.org."
}

$pkgRunner = "npm"
if ((Get-Command bun -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $PSScriptRoot "bun.lock"))) {
    $pkgRunner = "bun"
}

if (-not (Test-Path (Join-Path $PSScriptRoot "node_modules"))) {
    Write-Host "Installing frontend dependencies with $pkgRunner (first run only)..."
    if ($pkgRunner -eq "bun") { bun install } else { npm install }
}

$venvPython = Join-Path $PSScriptRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating backend/.venv and installing Python dependencies (first run only)..."
    & $python.Source -m venv (Join-Path $PSScriptRoot "backend\.venv")
    & $venvPython -m pip install --upgrade pip | Out-Null
    & $venvPython -m pip install -r (Join-Path $PSScriptRoot "backend\requirements.txt")
}

$env:ANALYTICAL_API_URL = "http://${HostAddress}:${ApiPort}"

Write-Host "Starting RCA API on http://${HostAddress}:${ApiPort} ..."
$api = Start-Process -FilePath $venvPython -ArgumentList @("-m", "uvicorn", "main:app", "--app-dir", "backend", "--host", $HostAddress, "--port", "$ApiPort") -RedirectStandardOutput $ApiLogFile -RedirectStandardError $ApiLogFile -PassThru -WindowStyle Hidden
Set-Content -Path $ApiPidFile -Value $api.Id

$apiReady = $false
for ($i = 0; $i -lt 90; $i++) {
    if ($api.HasExited) {
        Write-Error "RCA API failed to start. See $ApiLogFile"
    }
    try {
        $null = Invoke-WebRequest -Uri "http://${HostAddress}:${ApiPort}/api/health" -UseBasicParsing -TimeoutSec 2
        $apiReady = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $apiReady) {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    Remove-Item -ErrorAction SilentlyContinue $ApiPidFile
    Write-Error "RCA API did not become healthy in time. See $ApiLogFile"
}

Write-Host "Starting cockpit on http://${HostAddress}:${Port} ..."
if ($pkgRunner -eq "bun") {
    $web = Start-Process -FilePath "bun" -ArgumentList @("run", "dev", "--host", $HostAddress, "--port", "$Port") -RedirectStandardOutput $WebLogFile -RedirectStandardError $WebLogFile -PassThru -WindowStyle Hidden
} else {
    $web = Start-Process -FilePath "npm" -ArgumentList @("run", "dev", "--", "--host", $HostAddress, "--port", "$Port") -RedirectStandardOutput $WebLogFile -RedirectStandardError $WebLogFile -PassThru -WindowStyle Hidden
}
Set-Content -Path $WebPidFile -Value $web.Id

$webReady = $false
for ($i = 0; $i -lt 45; $i++) {
    if ($web.HasExited) {
        Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
        Write-Error "Cockpit failed to start. See $WebLogFile"
    }
    if (Select-String -Path $WebLogFile -Pattern "ready in|Local:" -Quiet -ErrorAction SilentlyContinue) {
        $webReady = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $webReady) {
    & (Join-Path $PSScriptRoot "stop.ps1")
    Write-Error "Cockpit did not report ready in time. See $WebLogFile"
}

Write-Host "Incident Insight is running."
Write-Host "  RCA API:  http://${HostAddress}:${ApiPort}/api/health   (PID $($api.Id), log $ApiLogFile)"
Write-Host "  Cockpit:  http://${HostAddress}:${Port}                  (PID $($web.Id), log $WebLogFile)"
Write-Host "Stop with: ./stop.ps1"
