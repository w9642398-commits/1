@echo off
title RailTrack - Railway Geometry Design
echo ============================================
echo   RailTrack - Uruchamianie aplikacji
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [BLAD] Python nie jest zainstalowany.
    echo Pobierz z https://www.python.org/downloads/
    echo Podczas instalacji zaznacz "Add Python to PATH"
    pause
    exit /b 1
)

:: Create venv if not exists
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Tworzenie srodowiska wirtualnego...
    python -m venv .venv
    if errorlevel 1 (
        echo [BLAD] Nie udalo sie utworzyc srodowiska.
        pause
        exit /b 1
    )
)

:: Install deps if marker missing
if not exist ".venv\.deps_installed" (
    echo [2/3] Instalowanie zaleznosci ^(moze zajac 2-3 minuty^)...
    .venv\Scripts\pip.exe install --quiet numpy scipy PySide6 pyqtgraph ezdxf pandas openpyxl lxml pyyaml jinja2
    if errorlevel 1 (
        echo [BLAD] Instalacja zaleznosci nie powiodla sie.
        pause
        exit /b 1
    )
    echo ok > .venv\.deps_installed
) else (
    echo [OK] Zaleznosci juz zainstalowane.
)

echo [3/3] Uruchamianie RailTrack...
echo.
.venv\Scripts\python.exe -m railtrack
if errorlevel 1 (
    echo.
    echo [BLAD] Aplikacja zakonczyla sie z bledem.
    pause
)
