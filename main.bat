@echo off
REM Change directory to the fleet folder next to this file
cd /d "%~dp0fleet"
REM Use the project venv when it exists, otherwise the system pythonw
set PYTHONW=pythonw.exe
if exist ".venv\Scripts\pythonw.exe" set PYTHONW=.venv\Scripts\pythonw.exe
REM Run pythonw directly (not with "start") so its output reaches main.log; main.py finishes in about a second
"%PYTHONW%" -u main.py > main.log 2>&1

REM Exit immediately
exit
