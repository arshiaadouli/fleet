"""FleetCard browser shown at the bottom of the Fuelzone window.

cefpython3 embeds a Chromium browser in a Tk frame and Selenium drives it through
chromedriver, the same way it drove a separate Chrome window before. cefpython3 66.1 is
the last release: it needs Python 3.9 and ships Chromium 66, which only chromedriver 2.40
supports, so that chromedriver is downloaded to drivers/ the first time it's needed.

Call initialize() once after tk.Tk(), show(root) at the end of every screen, get_driver()
from a worker thread (the browser only loads pages while the Tk main loop runs) and
shutdown() once the main loop has ended.
"""
import ctypes
import hashlib
import io
import os
import socket
import sys
import threading
import urllib.request
import zipfile
import tkinter as tk
from ctypes import wintypes

from cefpython3 import cefpython as cef
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

# Next to this file, or next to the .exe in a PyInstaller build (same as dbconn.py)
BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
CHROMEDRIVER = os.path.join(BASE_DIR, "drivers", "chromedriver_2.40.exe")
CHROMEDRIVER_URL = "https://chromedriver.storage.googleapis.com/2.40/chromedriver_win32.zip"
CHROMEDRIVER_SHA256 = "035e7cac5dcf1eed73f3c9d0594fe1cd3c7b578670b4e7f2cadb5b3f6d48eaf2"

# A separate handle, so these argtypes don't change user32 for pyautogui and pygetwindow
_user32 = ctypes.WinDLL("user32")
_user32.GetFocus.restype = wintypes.HWND
_user32.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
_user32.SetFocus.argtypes = [wintypes.HWND]
_user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT]
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004

_devtools_port = None
_frame = None
_browser = None
_browser_ready = threading.Event()
_driver = None
_driver_lock = threading.Lock()


def initialize():
    """Start CEF. Call once, after tk.Tk() and before the main loop."""
    global _devtools_port
    _devtools_port = _free_port()
    cef.Initialize(settings={
        # chromedriver attaches to the browser through this port
        "remote_debugging_port": _devtools_port,
        "log_file": os.path.join(BASE_DIR, "cef_debug.log"),
        "log_severity": cef.LOGSEVERITY_WARNING,
    })


def show(root):
    """Pack the browser below the current screen. Call after the screen's other widgets."""
    global _frame
    if _frame is None:
        # height=1 so the form's widgets get their space first and the browser takes the rest
        _frame = tk.Frame(root, bg="white", height=1)
        _frame.bind("<Configure>", _on_configure)
        root.bind_all("<Button-1>", lambda event: _take_back_keyboard(root), add="+")
        root.bind("<Map>", lambda event: _on_map(root, event), add="+")
    _frame.pack(side="bottom", fill="both", expand=True, pady=(16, 0))


def get_driver(timeout=60):
    """Selenium driver for the embedded browser. Call from a worker thread, not the Tk main thread.

    chromedriver starts on first use, and again if it has stopped.
    """
    global _driver
    if not _browser_ready.wait(timeout):
        raise RuntimeError("The embedded browser didn't start")
    with _driver_lock:
        if _driver is not None:
            try:
                _driver.current_url
                return _driver
            except Exception:
                _stop_driver()
        options = webdriver.ChromeOptions()
        options.debugger_address = f"127.0.0.1:{_devtools_port}"
        # Selenium 4 only speaks the W3C protocol, chromedriver 2.40 has to be told to use it
        options.add_experimental_option("w3c", True)
        # Without close_fds chromedriver inherits the browser's DevTools socket and keeps that port busy
        service = Service(executable_path=_chromedriver(), popen_kw={"close_fds": True})
        _driver = webdriver.Chrome(service=service, options=options)
        return _driver


def shutdown():
    """Stop chromedriver and CEF. Call after the Tk main loop has ended."""
    global _browser
    if _driver is not None:
        _stop_driver()
    if _browser is not None:
        _browser.CloseBrowser(True)
        _browser = None  # CEF only shuts down cleanly once no browser references are left
    cef.Shutdown()


class _FocusHandler:
    def OnSetFocus(self, source, **_):
        # Refuse focus the browser takes by itself (page loads, Selenium clicks), so card swipes keep
        # going to the Tk entries. Clicking in the page still focuses it. Same as cefpython's Tk example.
        return True


def _embed(frame):
    global _browser
    window_info = cef.WindowInfo()
    window_info.SetAsChild(frame.winfo_id(), [0, 0, frame.winfo_width(), frame.winfo_height()])
    _browser = cef.CreateBrowserSync(window_info, url="about:blank")
    _browser.SetClientHandler(_FocusHandler())
    # Creating the browser gives it the keyboard, give it back so card swipes go to the card number entry
    _take_back_keyboard(frame.winfo_toplevel())
    _message_loop_work(frame)
    _browser_ready.set()


def _message_loop_work(widget):
    cef.MessageLoopWork()
    widget.after(10, _message_loop_work, widget)


def _on_configure(event):
    if _browser is None:
        _embed(event.widget)
    else:
        _user32.SetWindowPos(_browser.GetWindowHandle(), None, 0, 0, event.width, event.height,
                             SWP_NOMOVE | SWP_NOZORDER)
        _browser.NotifyMoveOrResizeStarted()


def _on_map(root, event):
    if event.widget is root:
        # Windows hands the keyboard back to whatever had it when the window was hidden
        root.after(100, _take_back_keyboard, root)


def _take_back_keyboard(root):
    """Give the keyboard back to the Tk window if the browser has it. Tk then refocuses its own entry.

    Tk can't take the Windows keyboard focus back from the browser by itself, so after someone
    clicked in the page, clicking an entry or showing the window again wouldn't let them type.
    """
    if _browser is None:
        return
    focus = _user32.GetFocus()
    browser_hwnd = _browser.GetWindowHandle()
    if focus and (focus == browser_hwnd or _user32.IsChild(browser_hwnd, focus)):
        # Only move the Windows focus and let Tk pick the widget: focus_force() on a widget can cancel
        # the focus Tk has queued for the entry on a screen that was built while the window was hidden
        _user32.SetFocus(root.winfo_id())


def _stop_driver():
    global _driver
    try:
        _driver.service.stop()
    except Exception as e:
        print("Couldn't stop chromedriver:", e)
    _driver = None


def _chromedriver():
    """Path to chromedriver 2.40, downloading it the first time."""
    if not os.path.exists(CHROMEDRIVER):
        print("Downloading chromedriver 2.40 from", CHROMEDRIVER_URL)
        with urllib.request.urlopen(CHROMEDRIVER_URL, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != CHROMEDRIVER_SHA256:
            raise RuntimeError(f"The chromedriver downloaded from {CHROMEDRIVER_URL} doesn't match its expected checksum")
        os.makedirs(os.path.dirname(CHROMEDRIVER), exist_ok=True)
        partial = CHROMEDRIVER + ".part"
        with zipfile.ZipFile(io.BytesIO(data)) as archive, open(partial, "wb") as f:
            f.write(archive.read("chromedriver.exe"))
        os.replace(partial, CHROMEDRIVER)
    return CHROMEDRIVER


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
