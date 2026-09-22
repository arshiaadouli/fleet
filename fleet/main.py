# controller_show.py
import os
import socket
import subprocess
import time

HOST = "127.0.0.1"
PORT = 9000
CONNECTION_ATTEMPTS = 30
CONNECTION_DELAY = 0.5


def start_desktop_app():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    desktop_app = os.path.join(project_dir, "desktop_app.bat")
    subprocess.Popen(
        ["cmd.exe", "/c", desktop_app],
        cwd=project_dir,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

for attempt in range(CONNECTION_ATTEMPTS):
    try:
        with socket.create_connection((HOST, PORT), timeout=1) as s:
            s.sendall(b"show")
        break
    except OSError as error:
        if attempt == 0:
            start_desktop_app()
        if attempt == CONNECTION_ATTEMPTS - 1:
            print(f"Unable to contact desktop app at {HOST}:{PORT}: {error}")
            raise SystemExit(1)
        time.sleep(CONNECTION_DELAY)