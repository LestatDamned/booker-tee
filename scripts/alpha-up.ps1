$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$Detach = $false
if (($args.Count -ge 1) -and (($args[0] -eq "--detach") -or ($args[0] -eq "-d"))) {
    $Detach = $true
}
elseif ($args.Count -ge 1) {
    Write-Host "Usage: .\scripts\alpha-up.ps1 [--detach]"
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not installed or is not available in PATH."
    Write-Host "Install Docker Desktop, start it, then run this command again."
    exit 1
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Compose is not available."
    Write-Host "Install a recent Docker Desktop version with Compose support."
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is installed, but the Docker daemon is not running."
    Write-Host "Start Docker Desktop, wait until it is ready, then run this command again."
    exit 1
}

if (-not (Test-Path ".env.example")) {
    Write-Host ".env.example was not found. Run this script from a complete Booker Tee checkout."
    exit 1
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created local .env from .env.example."
}

New-Item -ItemType Directory -Force -Path "var/uploads" *> $null

if ($env:BOOKER_TEE_APP_PORT) {
    $appPort = $env:BOOKER_TEE_APP_PORT
}
else {
    $appPort = "8000"
    $envLine = Get-Content ".env" | Where-Object { $_ -match "^BOOKER_TEE_APP_PORT=" } | Select-Object -Last 1
    if ($envLine) {
        $appPort = $envLine.Split("=", 2)[1]
    }
}
$appPort = $appPort.Trim().Trim("`"").Trim("'")

$runningServices = docker compose ps --services --status running
$appAlreadyRunning = $runningServices -contains "app"

if (-not $appAlreadyRunning) {
    $client = [System.Net.Sockets.TcpClient]::new()
    $portInUse = $false
    try {
        $connect = $client.ConnectAsync("127.0.0.1", [int]$appPort)
        if ($connect.Wait(300) -and $client.Connected) {
            $portInUse = $true
        }
    }
    catch {
        $portInUse = $false
    }
    finally {
        $client.Dispose()
    }
    if ($portInUse) {
        Write-Host "Port $appPort is already in use."
        Write-Host "Stop the other app or choose another port, for example:"
        Write-Host ""
        Write-Host '  $env:BOOKER_TEE_APP_PORT = "8010"; .\scripts\alpha-up.ps1'
        Write-Host '  $env:BOOKER_TEE_APP_PORT = "8010"; .\scripts\alpha-up.ps1 --detach'
        exit 1
    }
}

Write-Host "Starting Booker Tee alpha locally..."
Write-Host "Open http://127.0.0.1:$appPort after Docker finishes building."

if ($Detach) {
    docker compose up --build --detach
    Write-Host "Waiting for Booker Tee healthcheck..."
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try {
            Invoke-WebRequest -Uri "http://127.0.0.1:$appPort/health" -UseBasicParsing -TimeoutSec 2 *> $null
            Write-Host "Booker Tee is ready: http://127.0.0.1:$appPort"
            Write-Host "Stop it with .\scripts\alpha-down.ps1"
            exit 0
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    Write-Host "The app started, but /health did not respond in time."
    Write-Host "Check logs with: docker compose logs app"
    exit 1
}

Write-Host "Press Ctrl+C in this terminal to stop the app."
docker compose up --build
