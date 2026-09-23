
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
from util import bring_to_front, read_json

POS_TITLE = "Infinity POS"   # part of the POS window's title


def activate_pos_window():
    """Bring the Infinity POS window to the front for the clicks; its handle, or None.

    Tk thread only (util.bring_to_front needs a message queue). None when there is no
    such window, or it will not come to the front: the click points are screen
    positions, so without the POS in front they would land on whatever else is there.
    pygetwindow's own activate() is not used: it raises whenever Windows refuses the
    front to a background process, which is every show after the first.
    """
    if os.name != "nt":
        return None
    windows = [w for w in gw.getWindowsWithTitle(POS_TITLE) if w.title]
    if not windows:
        print("No window found with title matching:", POS_TITLE)
        return None
    win = windows[0]
    if win.isMinimized:
        win.restore()
    if not bring_to_front(win._hWnd):
        print(f"The window {win.title!r} would not come to the front; the POS was not clicked")
        return None
    return win._hWnd


def mouse_movement(start, finish):
    """Click the POS at the mouseMovement points [start:finish] of paths.json.

    Only once activate_pos_window has the POS in front; any thread.
    """
    if os.name != "nt":
        print("Skipping POS clicks: Infinity POS only runs on Windows")
        return
    for point in read_json()['mouseMovement'][start:finish]:
        pyautogui.click(point['x'], point['y'])