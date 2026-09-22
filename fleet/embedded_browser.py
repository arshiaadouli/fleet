"""The FleetCard site embedded in the Fuelzone window (Microsoft Edge WebView2).

The browser is Windows' own Evergreen WebView2 runtime, hosted as a child of the Tk
window through the WebView2 Core SDK (pythonnet), so the form sits under the Tk screens
instead of in a second window. It is the ONLY browser: fleet.py drives it with Selenium
through the remote-debugging port it opens. chromedriver refuses that port by name
("unrecognized Chrome version: Edg/..."), so it is pointed at a FrontDoor that answers
/json/version as Chrome and relays the rest (devtools_front_door). The chromedriver of
the runtime's major is fetched on first use (browser_driver). What the operator sees is
the form that is filled and submitted; nothing is copied or mirrored into it.

It must never hold the keyboard. The card reader is a keyboard wedge, so anything typed
while the page has the Windows focus lands in the web page instead of the Tk entry -
and trans_filler appends to what is there. Only a mouse click in the page moves the
Windows focus into WebView2: not its creation, not a page load, not the page's own
focus(), not Selenium (it types through DevTools). So the operator keeps the mouse - the
form is taller than the frame and they scroll it - and the one moment the page can take
the keyboard is handled:

* the controller's GotFocus fires the moment a click takes the focus; the handler hands
  it straight back with user32.SetFocus, before it even returns, and Tk then puts the
  caret back where the operator was typing (release_keyboard). The keys typed between
  the click and the hand-back would land in the page, and the hand-back waits for the
  Tk loop to turn: a few milliseconds idle, tens while a screen or the category table
  is built (the check measures it with the loop held for 200 ms), never the length of a
  sound - util.play_sound no longer blocks the loop - so a swipe cannot follow a click
  that fast;
* PAGE_TAKES_MOUSE = False is the locked-down alternative for a till where nobody
  should touch the page: mouse input to the frame is disabled (EnableWindow), no click
  reaches the browser, the focus can never leave Tk, and the page cannot be scrolled.

Three rules the hosting stands on, each learned from a crash or a hang:

* import order. COM must be a single-threaded apartment on the Tk thread before the
  CLR is loaded, or .NET makes the thread MTA and WebView2 cannot be created; so this
  module calls CoInitializeEx before `import clr`, and tkinter_fleet imports this module
  before anything else. WebView2Loader.dll is found through PATH (the SDK's P/Invoke
  resolves it there), so the SDK folder goes on PATH before the CLR loads the assembly;
* a .NET event handler (GotFocus, NewWindowRequested, ...) runs on the Tk thread INSIDE
  Tcl_DoOneEvent. It may only make ctypes calls and queue.put: any tkinter call in it
  leaves _tkinter's tcl_tstate NULL and the next Tcl-to-Python callback aborts the
  process (PyEval_RestoreThread). Handlers read what they need from the event args at
  once and queue the Tk work, which a timer drains; their bodies are wrapped because an
  exception escaping a handler is swallowed by COM and would never be seen;
* the Tk thread never blocks in .NET. A Task completes through a window message this
  thread has to pump, so reading .Result before IsCompleted deadlocks - and pythonnet
  holds the GIL meanwhile, so the Selenium worker freezes with it. Tasks are polled from
  the Tk loop, and Selenium is only ever called from a worker thread: the browser
  answers chromedriver only while Tk pumps messages.
"""
import ctypes
import ctypes.wintypes as wt
import os
import queue
import shutil
import socket
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path

# STA before the CLR exists on this thread (rule one). S_OK or S_FALSE (already an STA)
# is fine; RPC_E_CHANGED_MODE means something made the Tk thread MTA first.
_hr = ctypes.windll.ole32.CoInitializeEx(None, 2)
if _hr not in (0, 1):
    raise RuntimeError("COM is already initialised as MTA on this thread (0x%08x); import "
                       "embedded_browser before anything that uses COM" % (_hr & 0xffffffff))

FLEET_DIR = Path(__file__).resolve().parent
SDK_DIR = FLEET_DIR / "webview2"
DRIVERS_DIR = FLEET_DIR / "drivers"
if not all((SDK_DIR / name).exists() for name in ("Microsoft.Web.WebView2.Core.dll", "WebView2Loader.dll")):
    import webview2_sdk
    webview2_sdk.ensure_sdk(SDK_DIR)
os.environ["PATH"] = str(SDK_DIR) + os.pathsep + os.environ.get("PATH", "")

import clr  # noqa: E402

clr.AddReference(str(SDK_DIR / "Microsoft.Web.WebView2.Core.dll"))
clr.AddReference("System.Drawing")
from System import IntPtr  # noqa: E402
from System.Drawing import Rectangle  # noqa: E402
from System.Threading import ApartmentState, Thread as DotNetThread  # noqa: E402
from Microsoft.Web.WebView2.Core import CoreWebView2Environment, CoreWebView2EnvironmentOptions  # noqa: E402

if DotNetThread.CurrentThread.GetApartmentState() != ApartmentState.STA:
    raise RuntimeError("the CLR did not join the STA on the Tk thread; WebView2 cannot be hosted")

import browser_driver  # noqa: E402
import ui_theme as ui  # noqa: E402
from devtools_front_door import FrontDoor  # noqa: E402

LOGIN_URL = "https://fco.fleetcard.com.au/"
PURCHASE_URL = "https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342"
# The purchase form keeps its Fleet Card tab behind nested tables; fleet.py waits on it.
FLEET_CARD_TAB_XPATH = "(//a[contains(@class, 'tab-btn')])[5]"
# True: the operator can click and scroll in the page, and a click's focus is handed
# back as soon as the Tk loop turns. False: the page is display-only (no scrolling) and
# the focus can never leave Tk.
PAGE_TAKES_MOUSE = True
USER_DATA_PARENT = Path(os.environ["LOCALAPPDATA"]) / "Fuelzone" / "FleetCard" / "webview2"

GA_ROOT = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_ACCESS_DENIED = 5
STILL_ACTIVE = 259

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.SetFocus.restype = wt.HWND
user32.SetFocus.argtypes = [wt.HWND]
user32.GetAncestor.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetForegroundWindow.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, wt.LPDWORD]
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.EnableWindow.argtypes = [wt.HWND, wt.BOOL]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
kernel32.CloseHandle.argtypes = [wt.HANDLE]

# One browser per process.
_environment_task = None
_door = None
_user_data = None
_frame = None


def free_port():
    """A TCP port nothing is listening on, for the browser's remote-debugging server.

    A fixed port would collide with a second copy of the window or a test run, and the
    browser fails silently when its port is taken - chromedriver then has nothing to
    attach to.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def initialize(remote_debugging_port):
    """Start the runtime's environment. Call once, before the first BrowserFrame is drawn.

    The runtime is checked for first, so a machine without it fails with a message
    before any window opens. The user-data folder is per process: WebView2 shares one
    browser process per folder and refuses a second process that opens the folder with
    different browser arguments, and every start has a different debugging port. The
    FleetCard login is redone every start anyway, so no profile needs to persist; dead
    processes' folders are swept here, a live process's folder never (removing a
    profile in use corrupts that instance).
    """
    global _environment_task, _door, _user_data
    if _environment_task is not None:
        # The sweep below would remove this process's own live profile.
        raise RuntimeError("initialize() has already been called; one browser per process")
    browser_driver.webview2_runtime_version()
    _user_data = USER_DATA_PARENT / ("pid-%d" % os.getpid())
    _sweep_dead_profiles()
    _user_data.mkdir(parents=True, exist_ok=True)
    _door = FrontDoor(remote_debugging_port)
    if _door.port == remote_debugging_port:
        # The port meant for the browser was handed to the door; the door still holds
        # it, so the next one cannot get it.
        taken, _door = _door, FrontDoor(remote_debugging_port)
        taken.stop()
    _door.start()
    options = CoreWebView2EnvironmentOptions()
    options.AdditionalBrowserArguments = "--remote-debugging-port=%d" % remote_debugging_port
    _environment_task = CoreWebView2Environment.CreateAsync(None, str(_user_data), options)


def _process_alive(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ctypes.get_last_error() == ERROR_ACCESS_DENIED   # there, but not ours to ask
    try:
        code = wt.DWORD()
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _sweep_dead_profiles():
    if not USER_DATA_PARENT.is_dir():
        return
    for folder in USER_DATA_PARENT.glob("pid-*"):
        try:
            pid = int(folder.name[4:])
        except ValueError:
            continue
        if pid == os.getpid() or not _process_alive(pid):
            shutil.rmtree(folder, ignore_errors=True)


def chromedriver_path():
    """The chromedriver for the installed runtime. Worker thread only: the first call on
    a machine downloads it (about 24 MB) into fleet/drivers."""
    return browser_driver.chromedriver_for_runtime(DRIVERS_DIR)


def attach_driver(remote_debugging_port, chromedriver_path):
    """A Selenium driver for the browser in the window.

    chromedriver attaches to the running browser instead of launching one, through the
    front door in front of remote_debugging_port. Only call this from a worker thread:
    the browser answers chromedriver only while the Tk thread pumps messages.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    if _door is None or _door.target_port != remote_debugging_port:
        raise RuntimeError("initialize(%d) has not been called" % remote_debugging_port)
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:%d" % _door.port)
    return webdriver.Chrome(service=Service(str(chromedriver_path)), options=options)


def window_is_foreground(widget):
    """True while the window this widget lives in is the foreground window."""
    try:
        return user32.GetAncestor(widget.winfo_id(), GA_ROOT) == user32.GetForegroundWindow()
    except Exception:
        return True


def bring_to_front(widget):
    """Make the window this widget lives in the foreground window, keyboard included.

    After the POS has been clicked the POS is the foreground process, and Windows
    refuses SetForegroundWindow to every other process - Tk's focus_force is one such
    call, so on its own the window only rises in the z-order while the card swipe still
    goes to the POS. Attached to the foreground window's input thread, the call is
    allowed: the documented way round the rule, with no input synthesised.
    """
    try:
        ours = user32.GetAncestor(widget.winfo_id(), GA_ROOT)
    except tk.TclError:
        return
    front = user32.GetForegroundWindow()
    if not front or front == ours:
        user32.SetForegroundWindow(ours)
        return
    front_thread = user32.GetWindowThreadProcessId(front, None)
    our_thread = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(front_thread, our_thread, True)
    try:
        user32.SetForegroundWindow(ours)
    finally:
        user32.AttachThreadInput(front_thread, our_thread, False)


def shutdown():
    """Close the browser, the door, and remove this process's user-data folder.

    The runtime exits a moment after the controller is closed and holds the folder
    until then, so the removal retries on a daemon thread and gives up quietly: the
    next start sweeps what is left.
    """
    if _frame is not None:
        _frame.close_browser()
    if _door is not None:
        _door.stop()
    if _user_data is not None:
        threading.Thread(target=_remove_user_data, args=(_user_data,), daemon=True).start()


def _remove_user_data(folder):
    for _ in range(20):
        shutil.rmtree(folder, ignore_errors=True)
        if not folder.exists():
            return
        time.sleep(0.25)


class BrowserFrame(tk.Frame):
    """The page, filling whatever room the screen on show leaves under its form."""

    MIN_HEIGHT = 260

    def __init__(self, master, url=LOGIN_URL, on_created=None):
        global _frame
        super().__init__(master, bg=ui.BG, bd=0, highlightthickness=0, height=self.MIN_HEIGHT)
        self.url = url
        self.controller = None
        self.error = None   # why the browser could not be created, for whoever waits on it
        self._closed = False
        self._creating = False
        self._queue = queue.SimpleQueue()   # .NET handlers put, _drain runs, on the Tk loop
        self._on_created = on_created
        self._focus_hwnd = None
        _frame = self
        self.bind("<Configure>", self._on_configure)
        # A move never reaches a child widget as <Configure>; the top level does get one,
        # and WebView2 places its dropdown windows from what it is told about the move.
        # Hidden after every sale and shown for the next: the browser is told, as
        # WebView2 asks, or the page can come back blank.
        toplevel = self.winfo_toplevel()
        toplevel.bind("<Configure>", self._on_window_configure, add="+")
        toplevel.bind("<Map>", lambda event: self._on_window_visibility(event, True), add="+")
        toplevel.bind("<Unmap>", lambda event: self._on_window_visibility(event, False), add="+")

    # ---- lifecycle -------------------------------------------------------------
    def _on_configure(self, _event=None):
        if self.controller is not None:
            self.controller.Bounds = Rectangle(0, 0, self.winfo_width(), self.winfo_height())
        elif (not self._creating and not self._closed and _environment_task is not None
              and self.winfo_width() > 1 and self.winfo_height() > 1):
            self._creating = True
            self._await(_environment_task, self._environment_ready)

    def _environment_ready(self, environment):
        if self._closed:
            return   # closed while the environment was starting: no controller to build
        self._await(environment.CreateCoreWebView2ControllerAsync(IntPtr(self.winfo_id())),
                    self._controller_ready)

    def _controller_ready(self, controller):
        if self._closed:
            controller.Close()
            return
        # Where Tk parks the Windows focus for this window; an int, so the GotFocus
        # handler needs no Tk call to hand the keyboard back.
        self._focus_hwnd = self.winfo_toplevel().winfo_id()
        self.controller = controller
        controller.Bounds = Rectangle(0, 0, self.winfo_width(), self.winfo_height())
        controller.IsVisible = True
        controller.GotFocus += self._on_got_focus
        web = controller.CoreWebView2
        # A form and nothing else: no menus, tools, zoom, autofill (the site has a field
        # called cardNumber, which autofill takes for a credit card), password bubbles
        # or touch gestures (a swipe would navigate back mid-sale). Each of those is a
        # window of its own that could take the keyboard with no hand-back.
        for setting in ("AreDefaultContextMenusEnabled", "AreDevToolsEnabled",
                        "AreBrowserAcceleratorKeysEnabled", "IsZoomControlEnabled",
                        "IsStatusBarEnabled", "IsGeneralAutofillEnabled",
                        "IsPasswordAutosaveEnabled", "IsPinchZoomEnabled",
                        "IsSwipeNavigationEnabled"):
            setattr(web.Settings, setting, False)
        web.NewWindowRequested += self._on_new_window
        web.DownloadStarting += self._on_download_starting
        if not PAGE_TAKES_MOUSE:
            user32.EnableWindow(self.winfo_id(), False)
        web.Navigate(self.url)
        self.after(20, self._drain)
        if self._on_created is not None:
            self._on_created()

    def _on_window_configure(self, event):
        if self.controller is not None and event.widget is self.winfo_toplevel():
            self.controller.NotifyParentWindowPositionChanged()

    def _on_window_visibility(self, event, visible):
        if self.controller is not None and event.widget is self.winfo_toplevel():
            self.controller.IsVisible = visible
            if visible:
                self.controller.NotifyParentWindowPositionChanged()

    def _await(self, task, then):
        """Run then(task.Result) from the Tk loop once the .NET Task is done (rule three)."""
        def poll():
            try:
                if not task.IsCompleted:
                    if self.winfo_exists():
                        self.after(20, poll)
                    return
                if task.IsFaulted or task.IsCanceled:
                    self.error = "WebView2 could not be created: %s" % (
                        task.Exception.GetBaseException() if task.IsFaulted else "cancelled")
                    print(self.error)
                else:
                    then(task.Result)
            except Exception:
                traceback.print_exc()
        self.after(20, poll)

    def _drain(self):
        try:
            while True:
                try:
                    work = self._queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    work()
                except Exception:
                    traceback.print_exc()
        finally:
            if not self._closed and self.winfo_exists():
                self.after(20, self._drain)

    def current_url(self):
        return self.controller.CoreWebView2.Source if self.controller is not None else None

    def close_browser(self):
        self._closed = True
        controller, self.controller = self.controller, None
        if controller is not None:
            controller.Close()

    # ---- .NET event handlers: ctypes and queue.put only (rule two) ----------------
    def _on_got_focus(self, _sender, _args):
        """Only a click in the page fires this: hand the keyboard back before the
        handler returns, then let Tk put the caret back where it was."""
        try:
            user32.SetFocus(self._focus_hwnd)
            self._queue.put(self.release_keyboard)
        except Exception:
            traceback.print_exc()

    def _on_new_window(self, _sender, args):
        """One browser: a link that wants a new window opens in this one instead."""
        try:
            args.Handled = True
            uri = args.Uri
            self._queue.put(lambda: self.controller is not None and self.controller.CoreWebView2.Navigate(uri))
        except Exception:
            traceback.print_exc()

    def _on_download_starting(self, _sender, args):
        """No download from the page: the receipt PDF is fetched by util.save_pdf_from_url.
        Handled alone only hides the bubble while the file still lands in Downloads."""
        try:
            args.Cancel = True
            args.Handled = True
        except Exception:
            traceback.print_exc()

    # ---- keyboard --------------------------------------------------------------
    def release_keyboard(self):
        """Hand the keyboard back to the box the operator was typing in.

        Tk saw the focus leave for the browser's window, so focus_force reaches Windows;
        it parks the focus on the top level, off whatever the operator was typing in, so
        the widget that had the caret is noted first and given it back.

        The caret is only given back to a widget that is still viewable. When a screen is
        rebuilt, the widget that last had it is the OLD screen's entry, just unpacked and
        never to map again; Tk defers focus for a widget it cannot show, and that stale
        deferral swallowed the focus the new screen then asked for, leaving the caret on
        the window itself and the odometer keystrokes going nowhere. The screen that is
        being built puts the caret where it wants it (focus_input).

        Skipped entirely unless we are the foreground window: there is no keyboard to
        take while the operator is in another application.
        """
        if not window_is_foreground(self):
            return
        toplevel = self.winfo_toplevel()
        typing_in = toplevel.focus_lastfor()
        if typing_in is not None and not typing_in.winfo_ismapped():
            typing_in = None
        try:
            toplevel.focus_force()
            if typing_in is not None and typing_in is not toplevel:
                typing_in.focus_set()
        except tk.TclError:
            pass
