@echo off
set "ROOT=%~dp0"
set "FLEET_DIR=%ROOT%fleet"

cd /d "%FLEET_DIR%"
start "" /b wscript.exe "%ROOT%tkinter.vbs"

REM Exit immediately
exit /b 0
