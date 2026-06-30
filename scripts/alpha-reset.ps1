$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not installed or is not available in PATH."
    exit 1
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Compose is not available."
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is installed, but the Docker daemon is not running."
    exit 1
}

if (($args.Count -lt 1) -or ($args[0] -ne "--yes")) {
    Write-Host "This will stop Booker Tee and delete local alpha database, uploads, and cached app environment."
    Write-Host "Run this command only if you want a clean local alpha start:"
    Write-Host ""
    Write-Host "  .\scripts\alpha-reset.ps1 --yes"
    exit 1
}

Write-Host "Resetting Booker Tee alpha local data..."
docker compose down --volumes --remove-orphans
Write-Host "Local alpha data was removed. Start again with .\scripts\alpha-up.ps1"
