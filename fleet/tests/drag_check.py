"""Does the embedded WebView2 follow the window while it is being dragged, and stay alive?

Drives a REAL title-bar drag with mouse input - Windows enters its modal move loop, the
same one a hand on the mouse puts it in - and looks at what the browser frame did with it.

What has to hold:
  * the window actually moved (otherwise the drag never happened and nothing was measured);
  * the ROOT window got <Configure> for the move. A move never reaches a child widget, so
    that root event is the only place the browser can be told it is moving;
  * the frame's handler for it called NotifyParentWindowPositionChanged, which is what
    WebView2 places its dropdown windows from;
  * the browser's own window still covers the frame exactly after the drag;
  * the page still answers on its DevTools port afterwards (it kept being serviced).

    fleet\\.venv\\Scripts\\python.exe tests\\drag_check.py
"""
import ctypes
import json
import os
import sys
import threading
import time
import tkinter as tk
import urllib.request
from ctypes import wintypes
from pathlib import Path

FLEET_DIR = Path(__file__).resolve().parent.parent
MOCK_DIR = FLEET_DIR / "tests" / "mock_fleetcard"
sys.path.insert(0, str(FLEET_DIR))

import embedded_browser  # noqa: E402  (first: COM in an STA before the CLR loads)
import ui_theme as ui  # noqa: E402

user32 = ctypes.windll.user32
user32.GetAncestor.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.SetProcessDPIAware()   # the app process is DPI-aware too (it imports pyautogui)
GW_CHILD = 5

counts = {"root_cfg": 0, "notified": 0}
failures = []
samples = []   # "drag start" / "drag end" / "skipped"
state = {}


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("   -> " + detail) if detail else ""))
    if not ok:
        failures.append(name)


# Count what the frame's own move handler does, on top of the raw <Configure> events.
# Patched on the class before the frame is built, because bind() takes the bound method.
_real_on_window_configure = embedded_browser.BrowserFrame._on_window_configure


def counted_on_window_configure(self, event):
    if self.controller is not None and event.widget is self.winfo_toplevel():
        counts["notified"] += 1
    _real_on_window_configure(self, event)


embedded_browser.BrowserFrame._on_window_configure = counted_on_window_configure

DEBUG_PORT = embedded_browser.free_port()
root = tk.Tk()
root.geometry("900x600+100+100")
ui.style_root(root)
entry = tk.Entry(root, **ui.entry_options())
entry.pack(fill="x", padx=16, pady=16)
embedded_browser.initialize(DEBUG_PORT)
frame = embedded_browser.BrowserFrame(root, url=(MOCK_DIR / "purchase.html").as_uri(),
                                      on_created=lambda: state.setdefault("created", time.time()))
frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
root.bind("<Configure>", lambda e: counts.__setitem__("root_cfg", counts["root_cfg"] + 1)
          if e.widget is root else None, add="+")


def page_targets():
    """The DevTools target list, read off a worker thread; the browser answers only
    while Tk pumps."""
    with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % DEBUG_PORT, timeout=5) as r:
        return [t.get("url", "") for t in json.loads(r.read().decode())]


def frame_rect():
    return (frame.winfo_rootx(), frame.winfo_rooty(),
            frame.winfo_rootx() + frame.winfo_width(), frame.winfo_rooty() + frame.winfo_height())


def browser_rect():
    """The runtime's window inside the frame (Chrome_WidgetWin_0, its direct child)."""
    child = user32.GetWindow(frame.winfo_id(), GW_CHILD)
    if not child:
        return None
    rect = wintypes.RECT()
    user32.GetWindowRect(child, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)


def wait_for_page():
    """Worker: wait until the page is listed on the DevTools port, then drag."""
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            if any(url.endswith("purchase.html") for url in page_targets()):
                state["page_up"] = True
                break
        except OSError:
            pass
        time.sleep(0.25)
    time.sleep(1.0)   # let the first paint land before the window is moved
    drag()


def describe(hwnd):
    title = ctypes.create_unicode_buffer(128)
    user32.GetWindowTextW(hwnd, title, 128)
    return "%s %r" % (hwnd, title.value)


def bring_to_front(hwnd):
    """A process that is not the foreground process is refused SetForegroundWindow;
    attaching to the foreground window's input thread for the call is the documented
    way round that. No input is synthesised."""
    front = user32.GetForegroundWindow()
    if front and front != hwnd:
        front_thread = user32.GetWindowThreadProcessId(front, None)
        our_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(front_thread, our_thread, True)
        try:
            user32.SetForegroundWindow(hwnd)
        finally:
            user32.AttachThreadInput(front_thread, our_thread, False)
    else:
        user32.SetForegroundWindow(hwnd)


def drag():
    """A real title-bar drag: button down on the title bar, 1.5 s of moving, let go.

    Never blind: the button goes down only while our window is the foreground window
    and our title bar is what is under the cursor. Both are asked for a few times, with
    the window on top as the app's own show puts it, because another program's window
    can take the front at any moment on a busy desktop - and asked once more right
    before the button goes down, with nothing in between, for the same reason.
    """
    hwnd = user32.GetAncestor(root.winfo_id(), 2)
    rect = wintypes.RECT()
    root.after(0, root.attributes, "-topmost", True)

    def ours_at_title_bar():
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        at_point = user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(rect.left + 300, rect.top + 15)), 2)
        return user32.GetForegroundWindow() == hwnd and at_point == hwnd, at_point

    def give_up(at_point):
        state["why_skipped"] = "foreground %s, at the title bar %s, ours %s" % (
            describe(user32.GetForegroundWindow()), describe(at_point), hwnd)
        samples.append("skipped")
        root.after(0, finish)

    for _ in range(6):
        bring_to_front(hwnd)
        time.sleep(0.4)
        ok, at_point = ours_at_title_bar()
        if ok:
            break
        time.sleep(0.6)
    else:
        return give_up(at_point)
    user32.SetCursorPos(rect.left + 300, rect.top + 15)
    time.sleep(0.1)
    ok, at_point = ours_at_title_bar()   # the last word, straight before the button-down
    if not ok:
        return give_up(at_point)
    state["start_geometry"] = root.geometry()
    state["cfg_before"] = counts["root_cfg"]
    state["notified_before"] = counts["notified"]
    samples.append("drag start")
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(0.15)
    for _ in range(30):
        user32.mouse_event(0x0001, 8, 4, 0, 0)  # MOUSEEVENTF_MOVE, relative
        time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
    samples.append("drag end")
    state["foreground_after"] = describe(user32.GetForegroundWindow())
    root.after(0, root.attributes, "-topmost", False)
    time.sleep(0.5)
    try:
        state["targets_after"] = page_targets()
    except OSError as error:
        state["targets_after"] = error
    root.after(0, finish)


def finish():
    if "skipped" in samples:
        print("  SKIP  could not bring the window to the front (something else is in use);"
              " the drag was not attempted, so nothing was measured   -> " + state["why_skipped"])
    else:
        check("the page was up before the drag", state.get("page_up") is True)
        check("the window was really dragged", root.geometry() != state["start_geometry"],
              "%s -> %s; foreground after the drag: %s"
              % (state["start_geometry"], root.geometry(), state["foreground_after"]))
        moves = counts["root_cfg"] - state["cfg_before"]
        check("the root window got <Configure> for the move", moves >= 10, "%d root events" % moves)
        notified = counts["notified"] - state["notified_before"]
        check("the frame told the browser about the move (NotifyParentWindowPositionChanged)",
              notified >= 10, "%d notifications" % notified)
        check("the browser's window still covers the frame exactly after the drag",
              browser_rect() == frame_rect(), "browser %s, frame %s" % (browser_rect(), frame_rect()))
        targets = state.get("targets_after")
        check("the page still answers on its DevTools port after the drag",
              isinstance(targets, list) and any(u.endswith("purchase.html") for u in targets),
              str(targets))
    print("\n%s  (%d failed)" % ("ALL CHECKS PASSED" if not failures else "FAILED", len(failures)))
    for name in failures:
        print("  - " + name)
    frame.close_browser()
    root.after(500, root.quit)


threading.Thread(target=wait_for_page, daemon=True).start()
root.after(30000, lambda: (check("finished within 30 s", False), finish()))
root.mainloop()
try:
    root.destroy()
except tk.TclError:
    pass
embedded_browser.shutdown()
user_data = embedded_browser.USER_DATA_PARENT / ("pid-%d" % os.getpid())
for _ in range(20):
    if not user_data.exists():
        break
    time.sleep(0.25)
sys.exit(1 if failures else 0)
