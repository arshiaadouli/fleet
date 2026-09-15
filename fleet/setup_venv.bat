@echo off
REM Create .venv in this folder with Python 3.9 and install requirements.txt (Windows)
REM Python 3.9 because cefpython3, the browser inside the window, has no build for newer Python
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto create
.venv\Scripts\python.exe -c "import sys; sys.exit(sys.version_info[:2] != (3, 9))"
if errorlevel 1 (
    echo .venv was made with a different Python version. Close the Fuelzone window, delete the .venv folder and run this again.
    goto failed
)

:create
REM uv downloads Python 3.9 if it isn't installed; without uv, use an installed Python 3.9
where uv >nul 2>nul
if errorlevel 1 goto py_launcher
uv venv --python 3.9 --seed --allow-existing .venv
if errorlevel 1 goto failed
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
if errorlevel 1 goto failed
goto done

:py_launcher
py -3.9 -c "import tkinter" 2>nul
if errorlevel 1 (
    echo Neither uv nor Python 3.9 with tkinter was found. Install uv, see README.md, and run this again.
    goto failed
)
py -3.9 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed

:done
echo.
echo Done. Activate with: .venv\Scripts\activate
pause
exit /b 0

:failed
echo.
echo Setup failed, see the messages above.
pause
exit /b 1
