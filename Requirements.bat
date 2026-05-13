@echo off
cd /d "%~dp0"
echo Installiere Abhaengigkeiten aus requirements.txt ...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Fehler bei der Installation.
    pause
    exit /b 1
)
echo.
echo Installation abgeschlossen.
pause
