
import os
import time
import ctypes
# These drive the Infinity POS window, which only exists on Windows
if os.name == "nt":
    import pyautogui
    import pygetwindow as gw
def temp():
    ctypes.windll.user32.BlockInput(True)
    def temp():
        
        # Replace with part of your app's window title
        app_title = "Infinity POS"  # Example: "Chrome", "Visual Studio Code", etc.

        # Get all matching windows
        windows = [w for w in gw.getWindowsWithTitle(app_title) if w.title]

        if windows:
            win = windows[0]  # Take the first match
            if win.isMinimized:
                print(f"Restoring minimized window: {win.title}")
                win.restore()  # Restore if minimized

            win.activate()  # Bring to front
            print(f"Activated window: {win.title}")
        else:
            print("No window found with title matching:", app_title)
        time.sleep(1)
        try:
            pyautogui.click(610, 440)

            pyautogui.click(487, 97)

            pyautogui.click(532, 150)
            pyautogui.click(500, 32)
            pyautogui.click(440, 280)

        except KeyboardInterrupt:
            print("\nTracking stopped.")
        ctypes.windll.user32.BlockInput(False)
from util import read_json
def mouse_movement(start, finish):
    if os.name != "nt":
        print("Skipping POS clicks: Infinity POS only runs on Windows")
        return
    # Replace with part of your app's window title
    app_title = "Infinity POS"  # Example: "Chrome", "Visual Studio Code", etc.

    # Get all matching windows
    windows = [w for w in gw.getWindowsWithTitle(app_title) if w.title]

    if windows:
        win = windows[0]  # Take the first match
        if win.isMinimized:
            print(f"Restoring minimized window: {win.title}")
            win.restore()  # Restore if minimized

        win.activate()  # Bring to front
        print(f"Activated window: {win.title}")
    else:
        print("No window found with title matching:", app_title)
    time.sleep(0.1)
    data = read_json()
    for i in range(len(data['mouseMovement'][start:finish])):
        pyautogui.click(data['mouseMovement'][i]['x'], data['mouseMovement'][i]['y'])
        # time.sleep(4)
        # print(data['mouseMovement'][i]['x'], data['mouseMovement'][i]['y'])


# mouse_movement(0, 2)