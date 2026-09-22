"""The FleetCard site embedded in the Fuelzone window (cefpython3 / Chromium 66).

The browser is a child window of the Tk window, so the form sits under the Tk screens
instead of in a second window. It is the ONLY browser: fleet.py drives it with Selenium
through the remote-debugging port it opens (chromedriver 2.40, the driver for this
Chromium, lives in fleet/drivers), so what the operator sees is the form that is filled
and submitted. Nothing is copied or mirrored into it.

It must never hold the keyboard. The card reader is a keyboard wedge, so anything typed
while the page has the Windows focus lands in the web page instead of the Tk entry. Two
things keep the keyboard in Tk:

* the browser refuses native focus for every source (KeepKeyboardInTk.OnSetFocus).
  Selenium still types into the page - it reaches the renderer directly - so the page
  never needs it, and the operator has no reason to click into it: the Tk form is where
  they type;
* release_keyboard() takes the Windows focus back after the browser is created and after
  each page load (the two moments CEF grabs it regardless) and puts the caret back where
  the operator was typing.
"""
import ctypes
import platform
import socket
import tkinter as tk

from cefpython3 import cefpython as cef

import ui_theme as ui

LOGIN_URL = "https://fco.fleetcard.com.au/"
PURCHASE_URL = "https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342"
# The purchase form keeps its Fleet Card tab behind nested tables; fleet.py waits on it.
FLEET_CARD_TAB_XPATH = "(//a[contains(@class, 'tab-btn')])[5]"

SWP_NOMOVE = 0x0002
GA_ROOT = 2


def free_port():
    """A TCP port nothing is listening on, for the browser's remote-debugging server.

    A fixed port would collide with a second copy of the window or a test run, and CEF
    fails silently when its port is taken - chromedriver then has nothing to attach to.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def initialize(remote_debugging_port):
    """Start CEF. Call once, before the first CefBrowserFrame is drawn.

    Software compositing: the page is a form, so the GPU buys it nothing, and a GPU
    swap chain in a child window has to be re-synced on every move and resize of the
    window around it, which is what makes dragging an embedded browser feel sticky.
    The Chrome this app used to drive ran the same site with --disable-gpu.
    """
    cef.Initialize(settings={"log_severity": cef.LOGSEVERITY_ERROR,
                             "remote_debugging_port": remote_debugging_port},
                   switches={"disable-gpu": "", "disable-gpu-compositing": ""})


def attach_driver(remote_debugging_port, chromedriver_path):
    """A Selenium driver for the browser in the window.

    chromedriver attaches to the running browser instead of launching one. It speaks
    the old wire protocol unless asked for W3C, and selenium 4 needs W3C. Only call this
    from a worker thread: the browser answers only while the Tk thread pumps CEF.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:%d" % remote_debugging_port)
    options.add_experimental_option("w3c", True)
    return webdriver.Chrome(service=Service(str(chromedriver_path)), options=options)


def window_is_foreground(widget):
    """True while the window this widget lives in is the foreground window."""
    if platform.system() != "Windows":
        return True
    try:
        user32 = ctypes.windll.user32
        return user32.GetAncestor(widget.winfo_id(), GA_ROOT) == user32.GetForegroundWindow()
    except Exception:
        return True


def pump(root, interval_ms=10):
    """Give CEF a slice of the Tk main loop; Tk and Chromium share this one thread."""
    cef.MessageLoopWork()
    if root.winfo_exists():
        root.after(interval_ms, pump, root, interval_ms)


class CefBrowserFrame(tk.Frame):
    """The page, filling whatever room the screen on show leaves under its form."""

    MIN_HEIGHT = 260

    def __init__(self, master, url=LOGIN_URL, on_created=None):
        super().__init__(master, bg=ui.BG, bd=0, highlightthickness=0, height=self.MIN_HEIGHT)
        self.url = url
        self.browser = None
        self._on_created = on_created
        self.bind("<Configure>", self._on_configure)
        # Moving the window never reaches a child widget as <Configure>, so on its own
        # this frame would never hear about a move - and CEF wants to be told about every
        # one or the page lags behind the frame while it is dragged. The root window does
        # get <Configure> for a move; cefpython's Tk example hooks it there for this.
        self.winfo_toplevel().bind("<Configure>", self._on_window_configure, add="+")

    # ---- lifecycle -------------------------------------------------------------
    def _on_configure(self, _event=None):
        if self.browser is None:
            if self.winfo_width() > 1 and self.winfo_height() > 1:
                self._create_browser()
            return
        self.browser.NotifyMoveOrResizeStarted()
        if platform.system() == "Windows":
            ctypes.windll.user32.SetWindowPos(
                self.browser.GetWindowHandle(), 0, 0, 0,
                self.winfo_width(), self.winfo_height(), SWP_NOMOVE
            )

    def _on_window_configure(self, event):
        if self.browser is not None and event.widget is self.winfo_toplevel():
            self.browser.NotifyMoveOrResizeStarted()

    def _create_browser(self):
        window_info = cef.WindowInfo()
        window_info.SetAsChild(self.winfo_id(), [0, 0, self.winfo_width(), self.winfo_height()])
        self.browser = cef.CreateBrowserSync(window_info)
        self.browser.SetClientHandler(KeepKeyboardInTk(self))
        self.browser.LoadUrl(self.url)
        self.after(300, self.release_keyboard)
        if self._on_created is not None:
            self._on_created()

    def close_browser(self):
        if self.browser is not None:
            browser, self.browser = self.browser, None
            browser.CloseBrowser(True)

    # ---- keyboard --------------------------------------------------------------
    def release_keyboard(self):
        """Hand the keyboard back to the box the operator was typing in.

        CEF takes the Windows keyboard focus when the browser is created and again on
        every page load. SetFocus(False) makes it let go, and also makes Tk's focus_force
        reach Windows at all - Tk never saw the focus leave, so on its own it treats the
        call as a no-op. focus_force parks it on the top level, off whatever the operator
        was typing in, so the widget that had the caret is noted first and given it back.

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
        if self.browser is not None:
            try:
                self.browser.SetFocus(False)
            except Exception as error:
                print("Could not release the browser keyboard focus:", error)
        try:
            toplevel.focus_force()
            if typing_in is not None and typing_in is not toplevel:
                typing_in.focus_set()
        except tk.TclError:
            pass


class KeepKeyboardInTk:
    """Focus and load callbacks for one CefBrowserFrame."""

    def __init__(self, frame):
        self._frame = frame

    def OnSetFocus(self, browser, source, **_kwargs):
        """The page never gets the native keyboard, whatever asks for it.

        Selenium focuses elements to type into them, and in CEF that asks the browser
        window for the Windows focus - which would take the operator's keystrokes into
        the page. Refusing it costs nothing: Selenium types through the renderer.
        """
        return True

    def OnLoadEnd(self, browser, frame, *_args, **_kwargs):
        if frame.IsMain():
            self._frame.after(0, self._frame.release_keyboard)