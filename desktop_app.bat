@echo off
REM Start tkinter_fleet.py through tkinter.vbs, which runs it hidden with the project venv
REM and writes its output to fleet\tkinter_fleet.log (pythonw started with "start" loses that output)
start "" wscript.exe "%~dp0tkinter.vbs"

REM Exit immediately
exit
