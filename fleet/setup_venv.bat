@echo off
REM Create .venv in this folder with Python 3.13, install requirements.txt and fetch the
REM WebView2 SDK (Windows). uv is used when it is on PATH, the python.org launcher otherwise.
REM An existing .venv is replaced (--clear): one left from an older Python keeps packages
REM built for that Python, which pip would count as installed and the new Python cannot import.
cd /d "%~dp0"

where uv >nul 2>nul
if not errorlevel 1 goto with_uv

set "PYTHON="
py -3.13 -c "import sys" >nul 2>nul && set "PYTHON=py -3.13"
if not defined PYTHON python3.13 -c "import sys" >nul 2>nul && set "PYTHON=python3.13"
if not defined PYTHON python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 14) else 1)" >nul 2>nul && set "PYTHON=python"
if not defined PYTHON (
    echo No Python 3.10-3.14 was found. Install Python 3.13 from python.org, tick "tcl/tk and IDLE",
    echo or install uv ^(https://docs.astral.sh/uv/^) and run this script again.
    goto failed
)
%PYTHON% -c "import tkinter" 2>nul || echo Warning: tkinter is missing. Re-run the Python installer and tick "tcl/tk and IDLE".

%PYTHON% -m venv --clear .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
goto sdk

:with_uv
uv venv --clear --python 3.13 --seed .venv
if errorlevel 1 goto failed
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -c "import tkinter" 2>nul || echo Warning: tkinter is missing from this Python; the app window cannot open without it.

:sdk
.venv\Scripts\python.exe webview2_sdk.py
if errorlevel 1 (
    echo The WebView2 SDK could not be fetched from NuGet. Check the network and run this script again.
    goto failed
)

echo.
echo Done. Activate with: .venv\Scripts\activate
pause
exit /b 0

:failed
echo.
echo Setup failed, see the messages above.
pause
exit /b 1
