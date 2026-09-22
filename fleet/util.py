from selenium.webdriver.remote.webdriver import WebDriver

def attach_to_session(executor_url: str, session_id: str) -> WebDriver:
    from selenium.webdriver.chrome.options import Options
    """
    Reconnect to an existing Selenium session using executor_url and session_id.
    """
    original_execute = WebDriver.execute

    def new_command_execute(self, command, params=None):
        if command == "newSession":
            # ✅ Selenium 4 expects "value" dict containing "sessionId"
            return {"value": {"sessionId": session_id}}
        return original_execute(self, command, params)

    WebDriver.execute = new_command_execute

    try:
        options = Options()
        driver = WebDriver(command_executor=executor_url, options=options)
        driver.session_id = session_id
    finally:
        WebDriver.execute = original_execute

    return driver


import requests
import os

def save_pdf_from_url(url: str, save_dir: str, filename: str):
    # Ensure the directory exists
    os.makedirs(save_dir, exist_ok=True)

    # Full path for saving
    file_path = os.path.join(save_dir, filename)

    # Fetch the PDF from the URL
    response = requests.get(url, stream=True)
    response.raise_for_status()  # raise error if download failed

    # Save PDF to file
    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"PDF saved to {file_path}")
    
    
    
import os
import json
import shutil
import subprocess

# paths.json in this folder holds all file locations
FLEET_DIR = os.path.dirname(os.path.abspath(__file__))
PATHS_FILE = os.path.join(FLEET_DIR, "paths.json")

def read_json():
    with open(PATHS_FILE, "r") as f:
        path_data = json.load(f)
        return path_data

def path_format(path):
    # Convert both / and \ to the current OS's separator; relative paths are relative to this folder
    path = path.replace('\\', '/').replace('/', os.sep)
    return os.path.join(FLEET_DIR, path)

WINDOWS_SOUNDS = {
    "error": r"C:\Windows\Media\Windows Critical Stop.wav",
    "notify": r"C:\Windows\Media\Windows Notify.wav",
}
LINUX_SOUNDS = {
    "error": "/usr/share/sounds/freedesktop/stereo/dialog-error.oga",
    "notify": "/usr/share/sounds/freedesktop/stereo/message.oga",
}

def play_sound(kind):
    """Play the "error" or "notify" alert sound, without waiting for it.

    The window calls this on the Tk thread. A call that blocks for the length of the
    .wav (playsound 1.2.2 slept about a second) stalls the Tk loop, and the Tk loop is
    what hands the keyboard back after a click in the embedded page: a click during
    that second followed by a card swipe would put the card number in the FleetCard
    form. winsound returns at once and plays in the background.
    """
    if os.name == "nt":
        import winsound
        winsound.PlaySound(WINDOWS_SOUNDS[kind], winsound.SND_FILENAME | winsound.SND_ASYNC)
    elif shutil.which("paplay") and os.path.exists(LINUX_SOUNDS[kind]):
        subprocess.run(["paplay", LINUX_SOUNDS[kind]])