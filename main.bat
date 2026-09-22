@echo off
set "ROOT=%~dp0"
cd /d "%ROOT%"

set PYTHONW=pythonw.exe
if exist "%ROOT%fleet\.venv\Scripts\pythonw.exe" set "PYTHONW=%ROOT%fleet\.venv\Scripts\pythonw.exe"
REM Run pythonw directly (not with "start") so its output reaches fleet\main.log, next to the
REM window's own log; main.py finishes in about a second
"%PYTHONW%" -u "%ROOT%fleet\main.py" > "%ROOT%fleet\main.log" 2>&1

REM Exit immediately
exit
