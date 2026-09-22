"""The real app against the mock FleetCard site, one browser - shared by the app checks.

Importing this module imports tkinter_fleet.py as-is, with the REAL embedded browser
(WebView2), pointed at fixtures: the mock site's pages, mock credentials, the POS fixture
files, a scratch cred.json and PDF folder, a recording stand-in for the database, and no
sound. The app's own worker thread then attaches the runtime's chromedriver to the
window's browser through the front door, logs in with fleet.py's login(), and opens the
purchase form. Nothing here opens fco.fleetcard.com.au, and the real cred.json is not
touched.

A check is a list of steps run inside the app's mainloop; a step returns True to be run
again on the next tick. Selenium must never be called from a step - the browser only
answers while the Tk thread pumps messages - so read-backs go through on_worker().

Run the checks from PowerShell, not Git Bash (see the Checks section of the README).
"""
import ctypes
import ctypes.wintypes
import json
import os
import platform
import sys
import tempfile
import threading
import tkinter as tk
import traceback
from pathlib import Path

FLEET_DIR = Path(__file__).resolve().parent.parent
MOCK_DIR = FLEET_DIR / "tests" / "mock_fleetcard"
SCRATCH = Path(tempfile.mkdtemp(prefix="app_check_"))
sys.path.insert(0, str(FLEET_DIR))
os.chdir(SCRATCH)  # anything the app writes relative to its cwd stays out of the project

# ---- point the app at fixtures, before it is imported ---------------------------------
import embedded_browser  # noqa: E402  (first: it puts COM in an STA before the CLR loads)
import fleet  # noqa: E402

# SCENARIO=timeout opens a purchase form whose Submit does nothing, as a rejected
# transaction leaves the real form where it is.
SCENARIO = os.environ.get("SCENARIO", "success")
embedded_browser.LOGIN_URL = (MOCK_DIR / "login.html").as_uri()
embedded_browser.PURCHASE_URL = (MOCK_DIR / "purchase.html").as_uri() + (
    "?fail=1" if SCENARIO == "timeout" else "")
fleet.path_data = dict(fleet.path_data,
                       cd=str(MOCK_DIR / "sale.CD2"), lr=str(MOCK_DIR / "sale.LR"),
                       pdfDir=str(SCRATCH / "pdfs"))  # save_pdf_from_url makedirs this

CRED = SCRATCH / "cred.json"

import tkinter_fleet as app  # noqa: E402

app.music_path = str(CRED)  # cred.json to scratch: never repoint a live window's session
app.PURCHASE_URL = embedded_browser.PURCHASE_URL
# release_keyboard does nothing unless the window is in front, and whether a test window
# can take the front depends on what else the desktop is doing. The caret bug it once hid
# was in Tk's own focus handling, which runs the same either way - so make it believe it
# is in front, and its logic is exercised on every run, deterministically.
embedded_browser.window_is_foreground = lambda widget: True
app.get_fleetcard_login = lambda: ("mock-user", "mock-pass")
app.play_sound = lambda kind: None


class RecordingDb:
    """Stands in for dbconn.FleetCardVal: keeps what the app would write to Mongo."""

    def __init__(self):
        self.inserts = []

    def check_db_connection(self):
        return True

    def insert_from_pdf(self, card_number, fuel_type, type, rego, price, datetime, exp_month, exp_year):
        self.inserts.append(dict(card_number=card_number, fuel_type=fuel_type, type=type, rego=rego,
                                 price=price, datetime=datetime, exp_month=exp_month, exp_year=exp_year))


app.db = RecordingDb()
app.db_connection = True

import webbrowser  # noqa: E402

webbrowser.open = lambda *args, **kwargs: None  # form_submit opens the saved PDF

import time

T0 = time.time()


def timed(name, function):
    """Wrap a driver-facing phase so the log says how long it took."""
    def wrapper(*args, **kwargs):
        started = time.time()
        try:
            return function(*args, **kwargs)
        finally:
            print("  TIME  %-20s %5.1fs  (at %5.1fs)" % (name, time.time() - started, time.time() - T0), flush=True)
    return wrapper


for _phase in ("login", "get_purchase_driver", "products_filler", "trans_filler", "odo_submit",
               "re_enter_products", "get_exp_month_year", "form_submit"):
    setattr(app, _phase, timed(_phase, getattr(app, _phase)))

_real_invoke = app.ui.Button.invoke


def _traced_invoke(self):
    """Every Submit press, as the root <Return> binding delivers it: state and command."""
    print("  INVOKE %-8s state=%s command=%s  (at %5.1fs)" % (
        self.cget("text"), self.cget("state"), "set" if self.cget("command") else "NONE",
        time.time() - T0), flush=True)
    return _real_invoke(self)


app.ui.Button.invoke = _traced_invoke
_real_thread_start = threading.Thread.start


def _traced_thread_start(self):
    print("  THREAD start %s  (at %5.1fs)" % (getattr(self, "_target", None), time.time() - T0), flush=True)
    return _real_thread_start(self)


threading.Thread.start = _traced_thread_start

LINES = fleet.sale_lines()  # surcharge + the .CD2 lines, as products_filler builds them
EXPECTED_ROWS = " ~ ".join("%s|%s|%s" % (l["description"], l["quantity"], l["subaftertax"]) for l in LINES)

failures = []
state = {}
user32 = ctypes.windll.user32 if platform.system() == "Windows" else None
if user32 is not None:
    user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
    user32.GetAncestor.restype = ctypes.wintypes.HWND
    user32.GetParent.restype = ctypes.wintypes.HWND
    user32.GetParent.argtypes = [ctypes.wintypes.HWND]


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("   -> " + detail) if detail else ""))
    if not ok:
        failures.append(name)


def mapped(widget, kinds):
    """Every visible widget of these types under `widget`; pack_forget'd ones are out."""
    found = []
    for child in widget.winfo_children():
        if isinstance(child, kinds) and child.winfo_ismapped():
            found.append(child)
        found.extend(mapped(child, kinds))
    return found


def entries():
    return mapped(app.page_frame, tk.Entry)


def buttons():
    return mapped(app.page_frame, app.ui.Button)


def notices():
    """The text of every notice on show under the form, variables resolved."""
    texts = []
    for label in mapped(app.notice_area, tk.Label):
        var = label.cget("textvariable")
        texts.append(app.root.getvar(var) if var else label.cget("text"))
    return texts


def status_text():
    banner = mapped(app.page_frame, app.ui.StatusBanner)
    return app.root.getvar(banner[0].cget("textvariable")) if banner else ""


def on_worker(key, work):
    """Run Selenium work off the Tk thread and park the result in state[key]."""
    state.pop(key, None)

    def run():
        try:
            state[key] = work(app.embedded_driver)
        except Exception:
            state[key] = {"error": traceback.format_exc()}
    threading.Thread(target=run, daemon=True).start()


def read_form(driver):
    """The form, read back through the same browser the operator is looking at."""
    get = lambda js: driver.execute_script("return " + js)
    return {"url": driver.current_url,
            "rows": get("window.productRows()"),
            "sales": get("document.getElementById('salesNumber').value"),
            "card": get("document.getElementById('cardNumber').value"),
            "ticked": get("document.getElementById('confirmCard').checked"),
            "rego": get("document.getElementById('Rego').value")}


# ---- where the Windows keyboard is, sampled while Selenium fills the form -------------
keyboard = {"samples": 0, "in_page": 0, "not_in_front": 0}


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.DWORD), ("flags", ctypes.wintypes.DWORD),
                ("hwndActive", ctypes.wintypes.HWND), ("hwndFocus", ctypes.wintypes.HWND),
                ("hwndCapture", ctypes.wintypes.HWND), ("hwndMenuOwner", ctypes.wintypes.HWND),
                ("hwndMoveSize", ctypes.wintypes.HWND), ("hwndCaret", ctypes.wintypes.HWND),
                ("rcCaret", ctypes.wintypes.RECT)]


def focus_hwnd():
    """Where the Windows keyboard is, whichever process owns that window.

    GetFocus() only knows this thread's own windows; the browser's input window belongs
    to msedgewebview2.exe, so GetFocus() would answer NULL exactly when the page has the
    keyboard and the count would be blind when it matters.
    """
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    user32.GetGUIThreadInfo(0, ctypes.byref(info))
    return info.hwndFocus or 0


def our_window_is_foreground():
    return user32.GetForegroundWindow() == user32.GetAncestor(app.root.winfo_id(), 2)


def bring_to_front():
    """Take the front back without synthesising input: a process that is not the
    foreground process is refused SetForegroundWindow unless it attaches to the
    foreground window's input thread for the call."""
    ours = user32.GetAncestor(app.root.winfo_id(), 2)
    front = user32.GetForegroundWindow()
    if front and front != ours:
        front_thread = user32.GetWindowThreadProcessId(front, None)
        our_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(front_thread, our_thread, True)
        try:
            user32.SetForegroundWindow(ours)
        finally:
            user32.AttachThreadInput(front_thread, our_thread, False)
    else:
        user32.SetForegroundWindow(ours)


def watch_keyboard():
    """Sample where the Windows keyboard is - only while this window is the foreground
    window, or the sample would be of whatever other window has the keyboard."""
    if user32 is not None:
        hwnd = focus_hwnd()
        if hwnd and not our_window_is_foreground():
            keyboard["not_in_front"] += 1
        elif hwnd:
            keyboard["samples"] += 1
            walker, browser_hwnd = hwnd, app.browser_frame.winfo_id()
            for _ in range(8):
                if walker == browser_hwnd:
                    keyboard["in_page"] += 1
                    break
                walker = user32.GetParent(walker)
                if not walker:
                    break
    if app.root.winfo_exists():
        app.root.after(100, watch_keyboard)


def check_keyboard_stayed_in_tk(label):
    if keyboard["samples"] == 0:
        print("  SKIP  %s: another window was in front for all %d ticks, nothing to sample"
              % (label, keyboard["not_in_front"]))
    else:
        check(label, keyboard["in_page"] == 0,
              "%d of %d samples in the page (%d ticks skipped, window not in front)"
              % (keyboard["in_page"], keyboard["samples"], keyboard["not_in_front"]))


# ---- the session and one card, as steps ----------------------------------------------
def wait_for_session():
    if not app.browser_ready.is_set():
        return True
    print("\n--- the window's own browser session ---")
    check("the app attached chromedriver to the browser in the window", app.embedded_driver is not None)
    saved = json.loads(CRED.read_text())
    check("cred.json points at that session, for get_purchase_driver and anyone else",
          saved.get("session_id") == app.embedded_driver.session_id
          and saved.get("executor_url") == app.embedded_driver.service.service_url, json.dumps(saved))
    check("the operator sees the purchase form in the window",
          app.browser_frame.current_url() == embedded_browser.PURCHASE_URL, str(app.browser_frame.current_url()))
    on_worker("session", lambda d: d.current_url)
    if user32 is not None:
        # Best effort only; never synthesise a click, it would land in whatever window is
        # really in front. Keyboard checks skip themselves if this failed.
        bring_to_front()


def check_driver_sees_it():
    if "session" not in state:
        return True
    check("it logged in with fleet.py's login() and opened the purchase form, in that same browser",
          state["session"] == embedded_browser.PURCHASE_URL, str(state["session"]))


def card_screen():
    print("\n--- card screen ---")
    app.root.deiconify()
    app.card_number_content(app.root, None)


def swipe_card(swipe):
    """A step that swipes this card: what the reader types, Submit as its trailing Tab."""
    def step():
        check("the caret is in the card box", app.root.focus_lastfor() is entries()[0])
        print("\n--- swipe %s: the real screens fill the real form ---" % swipe)
        keyboard["samples"] = keyboard["in_page"] = keyboard["not_in_front"] = 0
        state["swipe"] = swipe
        # what odo_content derives from the swipe and trans_filler types into the form
        state["card"] = "7034305" + swipe.split("7034305")[-1][:9]
        state.pop("form", None)
        entries()[0].insert(0, swipe)
        buttons()[0].invoke()
    step.__name__ = "swipe_card"
    return step


def wait_for_rego():
    labels = [b.cget("text") for b in buttons()]
    submit = [b for b in buttons() if b.cget("text") == "Submit"]
    if "Close" not in labels or not submit or str(submit[0].cget("state")) != "normal":
        return True  # odo screen not up yet, or products_filler/trans_filler still running
    print("\n--- odometer screen, once trans_filler has the rego ---")
    check("Submit is enabled once trans_filler has the rego", True)
    check("the status banner shows the rego FleetCard answered with",
          status_text().startswith("Rego is: MOCK123"), repr(status_text()))
    check("the caret is in the odometer box", app.root.focus_lastfor() is entries()[0],
          "caret on %s" % (app.root.focus_lastfor(),))
    check_keyboard_stayed_in_tk("the Windows keyboard never went into the page while the form was filled")
    on_worker("form", read_form)


def check_form():
    if "form" not in state:
        return True
    form = state["form"]
    if "error" in form:
        check("the form could be read back", False, form["error"].strip().splitlines()[-1])
        return
    print("--- the form, read back through the browser the operator is looking at ---")
    check("every line from the .CD2 is on the form, with quantity and amount",
          form["rows"] == EXPECTED_ROWS, form["rows"])
    check("the sales number from the .LR is on the form", form["sales"] == "0320330", form["sales"])
    check("the processed card number is on the form, as trans_filler types it",
          form["card"] == state["card"], form["card"])
    check("the check-card box is ticked", form["ticked"] is True)
    check("the rego is in the form's own Rego box", form["rego"] == "MOCK123", form["rego"])


SESSION_STEPS = [wait_for_session, check_driver_sees_it, card_screen, swipe_card("70343051234567890"),
                 wait_for_rego, check_form]


# ---- the runner ------------------------------------------------------------------------
def run(steps, tries=int(os.environ.get("CHECK_TRIES") or 1200)):
    """Run the steps inside the app's mainloop; exit 1 if any check failed.

    `tries` is the retry budget per waiting step, at 100 ms each: 1200 is two minutes.
    A sale took about 20 s over CEF's chromedriver 2.40 and the first one more, so a
    minute was tight; the TIME lines in the log say what each phase actually takes.
    """
    remaining = list(steps)

    def pump_steps():
        if not remaining:
            return finish()
        step = remaining[0]
        if not hasattr(step, "tries"):
            print("  STEP  %-40s (at %5.1fs, window %s)" % (step.__name__, time.time() - T0, app.root.state()), flush=True)
        try:
            again = step()
        except Exception:
            traceback.print_exc()
            failures.append("exception in " + step.__name__)
            again = False
        if again:
            step.tries = getattr(step, "tries", 0) + 1
            if step.tries < tries:
                app.root.after(100, pump_steps)
                return
            failures.append("timed out waiting in " + step.__name__)
            print("  while waiting (at %5.1fs): status %r, notices %s, window %s, threads %s"
                  % (time.time() - T0, status_text(), notices(), app.root.state(),
                     [t.name for t in threading.enumerate() if t is not threading.main_thread()]))
        remaining.pop(0)
        app.root.after(300, pump_steps)

    def finish():
        print("\n%s  (%d failed)" % ("ALL CHECKS PASSED" if not failures else "FAILED", len(failures)))
        for name in failures:
            print("  - " + name)
        app.browser_frame.close_browser()
        app.root.after(300, app.root.quit)

    app.root.after(500, watch_keyboard)
    app.root.after(500, pump_steps)
    app.root.mainloop()
    try:
        app.root.destroy()
    except tk.TclError:
        pass
    embedded_browser.shutdown()
    # shutdown() removes the user-data folder on a daemon thread once the runtime has
    # let go of it; give it a moment so the test leaves nothing behind.
    user_data = embedded_browser.USER_DATA_PARENT / ("pid-%d" % os.getpid())
    for _ in range(20):
        if not user_data.exists():
            break
        time.sleep(0.25)
    sys.exit(1 if failures else 0)
