# Deploy Project to Hugging Face Docker Space
# Prerequisite: hf auth login  (https://huggingface.co/settings/tokens)

$ErrorActionPreference = "Stop"
$SpaceId = "visshva-r/SRM-ThinkLoop-Theme2"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

Write-Host "Checking Hugging Face login..."
hf auth whoami
if ($LASTEXITCODE -ne 0) {
    Write-Host "Run: hf auth login"
    exit 1
}

Write-Host "Creating Space (ignore error if it already exists)..."
hf repos create $SpaceId --type space --sdk docker --public --exist-ok

Write-Host "Setting GEMINI_API_KEY secret from local .env..."
if (-not (Test-Path ".env")) {
    Write-Host "Missing .env with GEMINI_API_KEY"
    exit 1
}
$envContent = Get-Content ".env" | Where-Object { $_ -match "^GEMINI_API_KEY=" }
$key = ($envContent -replace "^GEMINI_API_KEY=", "").Trim()
if (-not $key -or $key -like "*your_*") {
    Write-Host "Set a real GEMINI_API_KEY in .env first"
    exit 1
}
$env:GEMINI_API_KEY = $key
hf repos create $SpaceId --type space --sdk docker --public --exist-ok --secrets "GEMINI_API_KEY" 2>$null

Write-Host "Adding Hugging Face git remote..."
$hfUrl = "https://huggingface.co/spaces/$SpaceId"
git remote remove hf 2>$null
git remote add hf $hfUrl

Write-Host "Pushing to Space (this triggers the Docker build)..."
git push hf main --force

Write-Host ""
Write-Host "Done. Space URL: https://huggingface.co/spaces/$SpaceId"
Write-Host "Wait 5-10 min for build, then test GET /health and POST /v1/troubleshoot"
