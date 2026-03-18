#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build standalone RailTrack.exe (no Python required to run)
.DESCRIPTION
    Uses PyInstaller to create a single-folder distribution.
    Output: dist/RailTrack/RailTrack.exe

    Run: .\build_exe.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  RailTrack - Budowanie EXE" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$venvPip = Join-Path $projectRoot ".venv\Scripts\pip.exe"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

# Ensure venv exists
if (-not (Test-Path $venvPython)) {
    Write-Host "Najpierw uruchom RailTrack.ps1 aby utworzyc srodowisko." -ForegroundColor Red
    exit 1
}

# Install PyInstaller
Write-Host "[1/3] Instalowanie PyInstaller..." -ForegroundColor Yellow
& $venvPip install --quiet pyinstaller
Write-Host "       Gotowe." -ForegroundColor Green

# Build
Write-Host "[2/3] Budowanie pliku wykonywalnego..." -ForegroundColor Yellow
& $venvPython -m PyInstaller `
    --name "RailTrack" `
    --noconfirm `
    --clean `
    --windowed `
    --add-data "railtrack/config;railtrack/config" `
    --hidden-import "pyqtgraph" `
    --hidden-import "numpy" `
    --hidden-import "scipy" `
    --hidden-import "ezdxf" `
    --hidden-import "pandas" `
    --hidden-import "openpyxl" `
    --hidden-import "lxml" `
    --hidden-import "yaml" `
    --hidden-import "jinja2" `
    railtrack/__main__.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "[BLAD] Budowanie nie powiodlo sie." -ForegroundColor Red
    exit 1
}
Write-Host "       Gotowe." -ForegroundColor Green

# Result
$exePath = Join-Path $projectRoot "dist\RailTrack\RailTrack.exe"
Write-Host ""
Write-Host "[3/3] Plik wykonywalny gotowy:" -ForegroundColor Green
Write-Host "       $exePath" -ForegroundColor White
Write-Host ""
Write-Host "Mozesz skopiowac caly folder dist\RailTrack\ na dowolny komputer." -ForegroundColor Yellow
Write-Host "Python nie jest wymagany do uruchomienia." -ForegroundColor Yellow
