
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

echo Building SYKE.exe...
%PYTHON% -m PyInstaller --clean --noconfirm SYKE.spec
if errorlevel 1 (
    echo PyInstaller build failed.
    exit /b 1
)

echo Packaging the compiled app without loose source files...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -LiteralPath '%~dp0dist\SYKE.exe' -DestinationPath '%~dp0dist\SYKE-Windows.zip' -Force"
if errorlevel 1 (
    echo ZIP packaging failed.
    exit /b 1
)

echo.
echo Build complete:
echo   Executable: %~dp0dist\SYKE.exe
echo   Download:   %~dp0dist\SYKE-Windows.zip
echo First launch will ask for your SYKE license, then your Gemini API key if needed.
endlocal
