
@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    set "PYTHON=python"
) else (
    set "PYTHON=py -3.13"
)

echo Installing Windows app-build dependencies...
%PYTHON% -m pip install -r requirements-build.txt
if errorlevel 1 (
    echo Build dependency installation failed.
    exit /b 1
)

echo Building JARVIS.exe...
%PYTHON% -m PyInstaller --clean --noconfirm JARVIS.spec
if errorlevel 1 (
    echo PyInstaller build failed.
    exit /b 1
)

echo.
echo Build complete: %~dp0dist\JARVIS.exe
echo First launch will ask for your Gemini API key.
endlocal
