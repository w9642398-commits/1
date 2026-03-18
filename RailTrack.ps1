#!/usr/bin/env pwsh
<#
.SYNOPSIS
    RailTrack - One-click launcher for Windows PowerShell
.DESCRIPTION
    Automatically creates venv, installs dependencies, and launches the app.
    Just run: .\RailTrack.ps1
#>

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "RailTrack - Railway Geometry Design"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  RailTrack - Uruchamianie aplikacji" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- Check Python ---
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[BLAD] Python nie jest zainstalowany." -ForegroundColor Red
    Write-Host "Pobierz z https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host 'Podczas instalacji zaznacz "Add Python to PATH"' -ForegroundColor Yellow
    Read-Host "Nacisnij Enter aby zamknac"
    exit 1
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

# --- Create venv ---
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$venvPip = Join-Path $projectRoot ".venv\Scripts\pip.exe"
$depsMarker = Join-Path $projectRoot ".venv\.deps_installed"

if (-not (Test-Path $venvPython)) {
    Write-Host "[1/3] Tworzenie srodowiska wirtualnego..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[BLAD] Nie udalo sie utworzyc venv." -ForegroundColor Red
        Read-Host "Nacisnij Enter"
        exit 1
    }
    Write-Host "       Gotowe." -ForegroundColor Green
} else {
    Write-Host "[OK] Srodowisko wirtualne istnieje." -ForegroundColor Green
}

# --- Install dependencies ---
if (-not (Test-Path $depsMarker)) {
    Write-Host "[2/3] Instalowanie zaleznosci (moze zajac 2-3 minuty)..." -ForegroundColor Yellow

    $packages = @(
        "numpy", "scipy", "PySide6", "pyqtgraph",
        "ezdxf", "pandas", "openpyxl", "lxml",
        "pyyaml", "jinja2"
    )

    & $venvPip install --quiet @packages
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[BLAD] Instalacja zaleznosci nie powiodla sie." -ForegroundColor Red
        Read-Host "Nacisnij Enter"
        exit 1
    }
    "ok" | Out-File $depsMarker
    Write-Host "       Gotowe." -ForegroundColor Green
} else {
    Write-Host "[OK] Zaleznosci juz zainstalowane." -ForegroundColor Green
}

# --- Launch ---
Write-Host "[3/3] Uruchamianie RailTrack..." -ForegroundColor Cyan
Write-Host ""
& $venvPython -m railtrack

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[BLAD] Aplikacja zakonczyla sie z bledem (kod: $LASTEXITCODE)." -ForegroundColor Red
    Read-Host "Nacisnij Enter"
}
