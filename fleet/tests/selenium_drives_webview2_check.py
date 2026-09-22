"""Proof: Selenium drives the WebView2 embedded in the Tk window - no mirror at all.

The production module does the hosting: embedded_browser.initialize opens the front door
and the runtime's environment, BrowserFrame puts the browser under a Tk entry as the
app does, attach_driver attaches the chromedriver of the runtime's major through the
door, and shutdown() takes it all down. Then the very same XPaths and calls fleet.py
makes are run against the browser in the window. If this passes, the form the operator
sees IS the form Selenium fills and submits, on Python 3.13 with no cefpython3.

Runs against the mock purchase page, so nothing touches fco.fleetcard.com.au. The
synthetic click into the page and the keystroke after it only happen while this window
is the foreground window and the window under the click point is ours - each is asked
again right before it is sent; otherwise that phase is skipped, never sent blind into
whatever else is on the desktop.

The click is the operator's, and what it does depends on embedded_browser's
PAGE_TAKES_MOUSE: with the module's default (False) the frame is disabled, so the click
never reaches the browser, GotFocus never fires and the keystroke lands in the Tk entry;
with PAGE_TAKES_MOUSE=1 in the environment the click takes the focus, the hand-back is
measured (click -> GotFocus) with the Tk thread deliberately held for 200 ms, as a
screen being built holds it, and the keystroke still has to land in the entry.

    fleet\\.venv\\Scripts\\python.exe tests\\selenium_drives_webview2_check.py
    $env:PAGE_TAKES_MOUSE='1'; ...                the page takes the mouse, hand-back measured
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
from pathlib import Path

FLEET_DIR = Path(__file__).resolve().parent.parent
MOCK_DIR = Path(__file__).resolve().parent / "mock_fleetcard"
sys.path.insert(0, str(FLEET_DIR))

import embedded_browser  # noqa: E402  (first: COM in an STA before the CLR loads)
from System.Threading import ApartmentState, Thread  # noqa: E402

if "PAGE_TAKES_MOUSE" in os.environ:
    embedded_browser.PAGE_TAKES_MOUSE = os.environ["PAGE_TAKES_MOUSE"] == "1"
MOUSE = embedded_browser.PAGE_TAKES_MOUSE

import json  # noqa: E402
import queue  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import tkinter as tk  # noqa: E402
import traceback  # noqa: E402
import urllib.request  # noqa: E402

import ui_theme as ui  # noqa: E402

failures = []
notes = []
timings = {}
state = {}


def check(name, ok, detail=""):
    line = ("  PASS  " if ok else "  FAIL  ") + name + (("   -> " + detail) if detail else "")
    notes.append(line)
    if not ok:
        failures.append(name)


def skip(name, why):
    notes.append("  SKIP  " + name + "   -> " + why)


check("the Tk thread is an STA", Thread.CurrentThread.GetApartmentState() == ApartmentState.STA)
CHROMEDRIVER = embedded_browser.chromedriver_path()
check("chromedriver for the runtime's major is in fleet/drivers", CHROMEDRIVER.exists(), str(CHROMEDRIVER))
DEBUG_PORT = embedded_browser.free_port()
USER_DATA = embedded_browser.USER_DATA_PARENT / ("pid-%d" % os.getpid())

user32 = ctypes.windll.user32
user32.GetAncestor.restype = wt.HWND
user32.GetForegroundWindow.restype = wt.HWND
user32.GetParent.restype = wt.HWND
user32.GetParent.argtypes = [wt.HWND]
user32.WindowFromPoint.restype = wt.HWND
user32.WindowFromPoint.argtypes = [wt.POINT]
user32.IsWindowEnabled.argtypes = [wt.HWND]
user32.SetProcessDPIAware()   # the app process is DPI-aware too (it imports pyautogui)
notes.append("  page takes the mouse: %s (embedded_browser.PAGE_TAKES_MOUSE)" % MOUSE)

# ---- the Tk window with the embedded browser, exactly as the app builds it ------------
root = tk.Tk()
root.title("selenium drives webview2")
root.geometry("900x600")
ui.style_root(root)
entry = tk.Entry(root, **ui.entry_options())
entry.pack(fill="x", padx=16, pady=16)
timings["t0"] = time.perf_counter()
embedded_browser.initialize(DEBUG_PORT)
frame = embedded_browser.BrowserFrame(root, url=(MOCK_DIR / "purchase.html").as_uri(),
                                      on_created=lambda: created())
frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

# .NET events reach Tk only through a queue drained by a Tk timer (embedded_browser's
# rule two); these two handlers of the test's own do nothing but put.
from_dotnet = queue.SimpleQueue()
focus_events = []   # perf_counter of each GotFocus, for the click -> GotFocus latency


def on_navigation_completed(_sender, args):
    from_dotnet.put(("loaded", args.IsSuccess))


def on_got_focus(_sender, _args):
    focus_events.append(time.perf_counter())


def created():
    """The controller is ready: the production module has applied its settings and
    started the first navigation."""
    web = frame.controller.CoreWebView2
    check("WebView2 environment created", True, "runtime %s" % web.Environment.BrowserVersionString)
    check("the frame is %s for mouse input, as PAGE_TAKES_MOUSE says" % ("enabled" if MOUSE else "disabled"),
          bool(user32.IsWindowEnabled(frame.winfo_id())) == MOUSE)
    web.NavigationCompleted += on_navigation_completed
    frame.controller.GotFocus += on_got_focus


def drain():
    while True:
        try:
            kind, value = from_dotnet.get_nowait()
        except queue.Empty:
            break
        if kind == "loaded" and "loaded" not in state:
            state["loaded"] = True
            page_loaded(value)
    if root.winfo_exists():
        root.after(20, drain)


def page_loaded(success):
    timings["first page load"] = time.perf_counter() - timings["t0"]
    check("the page loaded in the window", success)
    user32.SetForegroundWindow(user32.GetAncestor(root.winfo_id(), 2))
    entry.focus_set()
    root.after(500, lambda: threading.Thread(target=drive, daemon=True).start())
    root.after(500, watch_keyboard)


# ---- where the Windows keyboard is, sampled while Selenium fills the form -------------
keyboard_in_page = [0]
keyboard_samples = [0]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hwndActive", wt.HWND),
                ("hwndFocus", wt.HWND), ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND),
                ("hwndMoveSize", wt.HWND), ("hwndCaret", wt.HWND), ("rcCaret", wt.RECT)]


def focus_hwnd():
    """Where the Windows keyboard is, whichever process owns that window.

    GetFocus() only knows this thread's own windows; the browser's input window belongs
    to msedgewebview2.exe, so GetFocus() would answer NULL exactly when the page has the
    keyboard and the count would never see it.
    """
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    user32.GetGUIThreadInfo(0, ctypes.byref(info))
    return info.hwndFocus or 0


def our_window_is_foreground():
    return user32.GetForegroundWindow() == user32.GetAncestor(root.winfo_id(), 2)


def under_the_frame(hwnd):
    """Is this window the browser frame or one of the browser's windows inside it?"""
    for _ in range(8):
        if hwnd == frame.winfo_id():
            return True
        hwnd = user32.GetParent(hwnd)
        if not hwnd:
            return False
    return False


def watch_keyboard():
    """Sample where the Windows keyboard is, only while this window is the foreground."""
    hwnd = focus_hwnd()
    if hwnd and our_window_is_foreground():
        keyboard_samples[0] += 1
        walker, page = hwnd, frame.winfo_id()
        for _ in range(8):
            if walker == page:
                keyboard_in_page[0] += 1
                break
            walker = user32.GetParent(walker)
            if not walker:
                break
    if root.winfo_exists():
        root.after(100, watch_keyboard)


# ---- Selenium, on a worker thread: the browser answers only while Tk pumps messages ---
def drive():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import Select, WebDriverWait
    from selenium.common.exceptions import StaleElementReferenceException

    driver = None
    try:
        t = time.perf_counter()
        driver = embedded_browser.attach_driver(DEBUG_PORT, CHROMEDRIVER)
        timings["chromedriver attach"] = time.perf_counter() - t
        door = driver.caps["goog:chromeOptions"]["debuggerAddress"]
        state["door"] = door
        with urllib.request.urlopen("http://%s/json/version" % door, timeout=5) as r:
            version = json.loads(r.read().decode())
        check("GET /json/version through the front door says Chrome/",
              version.get("Browser", "").startswith("Chrome/"), version.get("Browser"))
        check("chromedriver %s attached to the embedded browser through the front door"
              % driver.caps.get("chrome", {}).get("chromedriverVersion", "").split(" ")[0],
              door.startswith("127.0.0.1:") and not door.endswith(":%d" % DEBUG_PORT),
              "session %s, browserVersion %s, debuggerAddress %s"
              % (driver.session_id, driver.caps.get("browserVersion"), door))
        check("it sees the page the window shows",
              driver.current_url.endswith("purchase.html"), driver.current_url)

        def click_through_postback(xpath):
            """Click, then wait until the page that was clicked has been replaced.

            The tab and add-item post the form back. Anything found before the reload
            lands goes stale, and a row count can even be met on the old page a moment
            before it goes. Holding the old <body> and waiting for it to go stale is
            the standard answer; products_filler's sleep(2.5) is the blunt version.
            """
            old_page = driver.find_element(By.TAG_NAME, "body")
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()
            WebDriverWait(driver, 10).until(EC.staleness_of(old_page))

        settled = WebDriverWait(driver, 10, ignored_exceptions=(StaleElementReferenceException,))

        # ---- fleet.py's own moves, verbatim XPaths ----------------------------------
        t = time.perf_counter()
        WebDriverWait(driver, 20).until(EC.presence_of_element_located(
            (By.XPATH, embedded_browser.FLEET_CARD_TAB_XPATH)))
        click_through_postback(embedded_browser.FLEET_CARD_TAB_XPATH)   # products_filler
        settled.until(lambda d: "highlight" in d.find_element(
            By.XPATH, embedded_browser.FLEET_CARD_TAB_XPATH).get_attribute("class"))
        check("clicked the Fleet Card tab (products_filler)", True)

        lines = [("Merchant Surcharge", "1", "0.93"), ("Premium Unleaded", "17.96", "29.78"),
                 ("Unleaded", "1", "3.25"), ("Unleaded", "1", "3.25")]
        # products_filler's own move: one reference, clicked once per row, no wait between.
        add_item = driver.find_element(By.XPATH, "(//fieldset//table//input)[1]")
        for _ in lines:
            add_item.click()
        WebDriverWait(driver, 10).until(lambda d: len(d.find_elements(
            By.XPATH, "//table[@id='ProductTable']//tr//select")) >= len(lines))
        for index, (desc, qty, amount) in enumerate(lines, start=1):
            row = "//table[@id='ProductTable']//tr[%d]" % index
            Select(driver.find_element(By.XPATH, row + "//select")).select_by_visible_text(desc)
            driver.find_element(By.XPATH, "(%s//input)[2]" % row).send_keys(qty)
            driver.find_element(By.XPATH, "(%s//input)[3]" % row).send_keys(amount)
        check("filled the product table with Select.select_by_visible_text + send_keys", True)

        driver.find_element(By.XPATH, "(//table//table//input)[1]").send_keys("0320330")  # trans_filler
        driver.find_element(By.XPATH, "(//table//table//input)[5]").send_keys("703430512345678")
        box = driver.find_element(By.XPATH, "(//table//table//input)[10]")
        if not box.is_selected():
            box.click()
        check("sales number, card and check box entered (trans_filler)", True)
        driver.find_element(By.XPATH, "(//table//table//input)[12]").send_keys("123456")   # odo_submit
        check("odometer entered (odo_submit)", True)
        timings["fleet.py moves"] = time.perf_counter() - t

        # ---- read the page back: is it all there, in the window the operator sees? ----
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return window.productRows()"))
        rows = driver.execute_script("return window.productRows()")
        check("every line is on the form", rows == " ~ ".join("|".join(l) for l in lines), rows)
        check("sales number is on the form",
              driver.find_element(By.ID, "salesNumber").get_attribute("value") == "0320330")
        check("card is on the form",
              driver.find_element(By.ID, "cardNumber").get_attribute("value") == "703430512345678")
        check("check box is ticked", driver.find_element(By.ID, "confirmCard").is_selected())
        check("odometer is on the form",
              driver.find_element(By.ID, "odometer").get_attribute("value") == "123456")
        # ---- the parts an implementation has to survive: sharing and re-attaching ----
        # cred.json sharing: another process attaches to the SAME session by id (util.py)
        from util import attach_to_session
        shared = attach_to_session(driver.service.service_url, driver.session_id)
        check("util.attach_to_session joins the session, as tkinter_fleet does via cred.json",
              shared.find_element(By.ID, "salesNumber").get_attribute("value") == "0320330")
        # restart / second card: a fresh chromedriver attaches again to the same browser
        driver.service.stop()
        t = time.perf_counter()
        again = embedded_browser.attach_driver(DEBUG_PORT, CHROMEDRIVER)
        timings["chromedriver re-attach"] = time.perf_counter() - t
        check("a fresh chromedriver re-attaches after the first is stopped (restart)",
              again.find_element(By.ID, "cardNumber").get_attribute("value") == "703430512345678",
              "session %s" % again.session_id)
        again.get((MOCK_DIR / "purchase.html").as_uri())   # what get_purchase_driver does per card
        WebDriverWait(again, 10).until(EC.presence_of_element_located(
            (By.XPATH, embedded_browser.FLEET_CARD_TAB_XPATH)))
        check("re-opening the purchase page for the next card works (get_purchase_driver)", True)
        driver = again
        state["driver"] = driver
        root.after(0, hide_and_show)
    except Exception:
        check("Selenium drove the embedded browser without error", False,
              traceback.format_exc().strip().splitlines()[-1])
        notes.append(traceback.format_exc())
        if driver is not None:
            try:
                driver.service.stop()   # not quit(): that would close the window's browser
            except Exception:
                pass
        root.after(0, click_into_the_page)


# ---- hidden after a sale, shown for the next: the browser must come back with it ------
def hide_and_show():
    """The app withdraws the window after every sale and deiconifies it on the next
    'show'; the frame turns the controller's IsVisible off and on with it."""
    root.withdraw()
    root.after(700, show_again)


def bring_to_front():
    """Withdrawing the window handed the foreground to whatever was behind it, and a
    process that is no longer the foreground process is refused SetForegroundWindow.
    Attaching to the foreground window's input thread for the call is the documented
    way round that; no input is synthesised."""
    ours = user32.GetAncestor(root.winfo_id(), 2)
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


def show_again():
    """As the app's show_window does it: deiconify, then take the front back."""
    root.deiconify()
    root.lift()
    root.focus_force()
    bring_to_front()
    entry.focus_set()
    root.after(700, lambda: threading.Thread(target=after_round_trip, daemon=True).start())


def after_round_trip():
    driver = state["driver"]
    try:
        with urllib.request.urlopen("http://%s/json/list" % state["door"], timeout=5) as r:
            targets = [t.get("url", "") for t in json.loads(r.read().decode())]
        check("after a withdraw/deiconify round trip /json/list still lists the page",
              any(u.endswith("purchase.html") for u in targets), str(targets))
        check("and chromedriver still answers",
              driver.execute_script("return document.title") == "Mock FleetCard purchase")
    except Exception:
        check("the withdraw/deiconify round trip left the browser answering", False,
              traceback.format_exc().strip().splitlines()[-1])
    finally:
        try:
            driver.service.stop()   # not quit(): that would close the window's browser
        except Exception:
            pass
        root.after(0, click_into_the_page)


# ---- the operator clicks into the page, then types: where does the keystroke land? ---
def click_into_the_page():
    """Only a click gives the page the Windows focus; the card reader may follow it.

    Never blind: the click and the keystroke are each only sent while our window is
    the foreground window and the window at the click point is a child of ours (the
    browser's windows belong to msedgewebview2.exe, so it is the root ancestor that has
    to be ours, not the owning process) - asked right before each of them, since
    another window can take the front in the 400 ms between the two.
    """
    ours = user32.GetAncestor(root.winfo_id(), 2)
    if not our_window_is_foreground() and "asked_front" not in state:
        # One try to get the front back, as the app does on every show; then the guard.
        state["asked_front"] = True
        bring_to_front()
        return root.after(300, click_into_the_page)
    x = frame.winfo_rootx() + frame.winfo_width() // 2
    y = frame.winfo_rooty() + 40

    def ours_at_point():
        at_point = user32.WindowFromPoint(wt.POINT(x, y))
        return our_window_is_foreground() and user32.GetAncestor(at_point, 2) == ours, at_point

    ok, at_point = ours_at_point()
    if not ok:
        state["click"] = "skipped"
        skip(CLICK_CHECK, "our window is not the foreground window, or the window at the click "
             "point is not ours (foreground %s, at point %s, ours %s); no click was sent"
             % (user32.GetForegroundWindow(), at_point, ours))
        return finish()
    # With the frame disabled, WindowFromPoint skips it and its browser windows: the click
    # is Tk's. Enabled, the browser's own window is what is under the cursor.
    check("the window at the click point is %s" % ("the browser's" if MOUSE else "Tk's, the browser being disabled"),
          under_the_frame(at_point) == MOUSE, "hwnd %s" % at_point)
    state["click"] = "sent"
    user32.SetCursorPos(x, y)
    state["clicked_at"] = time.perf_counter()
    user32.mouse_event(0x2, 0, 0, 0, 0)
    user32.mouse_event(0x4, 0, 0, 0, 0)
    if MOUSE:
        # Hold the Tk thread as a screen being built does, so the latency measured is
        # the one the hand-back has to live with, not the idle one.
        root.after(0, time.sleep, 0.2)
    root.after(400, type_z)
    root.after(900, finish)


def type_z():
    """The card reader's first key, 400 ms after the click - if it is still safe to send."""
    ours = user32.GetAncestor(root.winfo_id(), 2)
    at_point = user32.WindowFromPoint(wt.POINT(frame.winfo_rootx() + frame.winfo_width() // 2,
                                               frame.winfo_rooty() + 40))
    if not our_window_is_foreground() or user32.GetAncestor(at_point, 2) != ours:
        state["keystroke"] = "skipped"
        skip(CLICK_CHECK, "the front changed after the click (foreground %s, at point %s); "
             "no keystroke was sent" % (user32.GetForegroundWindow(), at_point))
        return
    state["keystroke"] = "sent"
    user32.keybd_event(0x5A, 0, 0, 0)
    user32.keybd_event(0x5A, 0, 2, 0)


CLICK_CHECK = ("a click in the page hands the keyboard back (controller.GotFocus -> Tk)" if MOUSE
               else "a click on the disabled page never reaches the browser: no GotFocus, keystroke in Tk")


finished = [False]


def finish():
    if finished[0]:
        return
    finished[0] = True
    if state.get("click") == "sent" and state.get("keystroke") == "sent":
        typed = entry.get().lower()   # Caps Lock or a held Shift on the desktop is not ours to control
        if MOUSE:
            latency = ("click -> GotFocus %.0f ms with the Tk thread held for 200 ms"
                       % ((focus_events[0] - state["clicked_at"]) * 1000) if focus_events else "no GotFocus")
            check(CLICK_CHECK, len(focus_events) > 0 and typed == "z",
                  "%d GotFocus event(s), entry holds %r; %s" % (len(focus_events), entry.get(), latency))
        else:
            check(CLICK_CHECK, not focus_events and typed == "z",
                  "%d GotFocus event(s), entry holds %r" % (len(focus_events), entry.get()))
        check("the caret is in the Tk entry", root.focus_get() is entry,
              "caret on %s" % (root.focus_get(),))
    elif state.get("click") == "sent":
        skip("the caret is in the Tk entry", "no keystroke was sent, so there is nothing to see")
    elif state.get("click") == "skipped":
        skip("the caret is in the Tk entry", "no click was sent, so there is nothing to see")
    if keyboard_samples[0] == 0:
        skip("the Windows keyboard never went into the page while Selenium typed",
             "our window was never the foreground window, so nothing could be sampled")
    else:
        check("the Windows keyboard never went into the page while Selenium typed",
              keyboard_in_page[0] == 0,
              "%d of %d samples in the page" % (keyboard_in_page[0], keyboard_samples[0]))
    timings["mainloop"] = time.perf_counter() - timings["t0"]
    frame.close_browser()
    root.after(1000, root.quit)


root.after(20, drain)
root.after(60000, lambda: (check("finished within 60s", False), finish()))
root.mainloop()
try:
    root.destroy()
except tk.TclError:
    pass
embedded_browser.shutdown()

for _ in range(32):   # shutdown() removes the folder on a daemon thread once the runtime lets go
    if not USER_DATA.exists():
        break
    time.sleep(0.25)
runtimes = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'msedgewebview2.exe' } "
     "| ForEach-Object { \"$($_.ProcessId) $($_.CommandLine)\" }"],
    capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
survivors = [line.split(" ", 1)[0] for line in runtimes.stdout.splitlines()
             if re.search(r"[\\/]%s(?![0-9])" % re.escape(USER_DATA.name), line)]
check("no msedgewebview2.exe with our user-data folder survives shutdown",
      not survivors, " ".join(survivors))
check("the user-data folder was removed by shutdown()", not USER_DATA.exists(), str(USER_DATA))

print("\n".join(notes))
print("\ntimings: " + ", ".join("%s %.2f s" % (k, v) for k, v in timings.items() if k != "t0"))
print("%s  (%d failed)" % ("ALL CHECKS PASSED" if not failures else "FAILED", len(failures)))
for name in failures:
    print("  - " + name)
sys.exit(1 if failures else 0)
