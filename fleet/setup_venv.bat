@echo off
REM Create .venv in this folder and install requirements.txt (Windows)
cd /d "%~dp0"

python -c "import tkinter" 2>nul || echo Warning: tkinter is missing. Re-run the Python installer and tick "tcl/tk and IDLE".

python -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo.
echo Done. Activate with: .venv\Scripts\activate
pause
exit /b 0

:failed
echo.
echo Setup failed, see the messages above.
pause
exit /b 1
