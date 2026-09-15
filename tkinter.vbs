' Runs fleet\tkinter_fleet.py hidden, from the fleet folder next to this file.
' Uses fleet\.venv when it exists, otherwise the system python. Output goes to fleet\tkinter_fleet.log
Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
fleetDir = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "fleet")
python = fso.BuildPath(fleetDir, ".venv\Scripts\python.exe")
If Not fso.FileExists(python) Then python = "python"
WshShell.CurrentDirectory = fleetDir
WshShell.Run "cmd /c """"" & python & """ -u tkinter_fleet.py > tkinter_fleet.log 2>&1""", 0
Set WshShell = Nothing
