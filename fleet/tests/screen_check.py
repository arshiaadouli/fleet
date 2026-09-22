"""Walk the Fuelzone screens and check the form, the buttons and the browser on each.

Safe to run while the real window is up: it never touches the live FleetCard session.
embedded_browser.BrowserFrame is swapped for a stand-in before tkinter_fleet is
imported, so no second browser starts and no second merchant login happens, and the
Selenium calls odo_content makes are stubbed so nothing navigates the operator's browser.

The steps run inside the app's own mainloop, because odo_content does its FleetCard
lookup on a worker thread and root.after() from a worker thread only works there.

    fleet\\.venv\\Scripts\\python.exe tests\\screen_check.py
"""
import ctypes
import ctypes.wintypes as wt
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback

FLEET_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, FLEET_DIR)
os.chdir(FLEET_DIR)

# A window of another process, standing in for Infinity POS: the POS clicks activate the
# POS, and what the 'show' steps have to see is this window winning the front back from
# it. Started now so it is on screen by the time those steps run; ended at the end.
POS_STANDIN = subprocess.Popen([sys.executable, "-c", "import tkinter as tk; r = tk.Tk(); "
                                "r.title('POS stand-in'); r.geometry('360x240+40+40'); r.mainloop()"])

import embedded_browser

BROWSER_HEIGHT = embedded_browser.BrowserFrame.MIN_HEIGHT


class StubBrowserFrame(tk.Frame):
    """Stands in for the browser window: same size and same calls, no WebView2."""

    def __init__(self, master, url=None, on_created=None):
        super().__init__(master, bg="#C8D4E4", height=BROWSER_HEIGHT)
        self.released = 0

    def release_keyboard(self):
        self.released += 1

    def close_browser(self):
        pass

    def current_url(self):
        return None


embedded_browser.BrowserFrame = StubBrowserFrame
embedded_browser.initialize = lambda port=None: None
embedded_browser.free_port = lambda: 0

import tkinter_fleet as app  # noqa: E402  (must follow the patches above)

app.play_sound = lambda kind: None

# Read the sale from fixture copies of the POS files rather than whatever the till
# last wrote, so the check does not depend on the state of the real hex folder.
import fleet  # noqa: E402
FIXTURES = os.path.join(FLEET_DIR, "tests", "mock_fleetcard")
for module in (fleet, app):
    module.path_data = dict(module.path_data,
                            cd=os.path.join(FIXTURES, "sale.CD2"),
                            lr=os.path.join(FIXTURES, "sale.LR"))

# CHECK_ITEMS raises the number of unknown items, to see how tall a category table the
# browser can survive underneath: the form is packed first, so the browser gives up the
# room, and this is what says whether it still has enough of it.
ITEMS = [{"id": str(n), "quantity": "%d.0" % n, "price": "%d.95" % n, "description": "Unknown"}
         for n in range(1, int(os.environ.get("CHECK_ITEMS", "2")) + 1)]


class StubDriver:
    """Enough of a driver for odo_content; the real one drives the operator's browser."""
    current_url = embedded_browser.PURCHASE_URL


app.get_purchase_driver = lambda: StubDriver()
app.products_filler = lambda driver, card: ("404", ITEMS)
app.trans_filler = lambda driver, card: "Rego: ABC 123"

failures = []
state = {}


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


def option_menus():
    return mapped(app.page_frame, tk.OptionMenu)


def headers():
    """The brand bars on show. They are shared widgets re-packed per screen, not rebuilt."""
    return [w for w in app.root.winfo_children()
            if isinstance(w, app.ui.Header) and w.winfo_ismapped()]


def footers():
    """Same story as headers: one shared bar per database state, re-packed per screen."""
    return [w for w in app.root.winfo_children()
            if isinstance(w, app.ui.StatusFooter) and w.winfo_ismapped()]


def bound(sequence):
    return bool(app.root.bind(sequence))


def screen_is_sound(label, entry_count, button_count, step=None):
    """What must hold on every screen: one form, its buttons, and the browser below it."""
    form_bottom = app.page_frame.winfo_rooty() + app.page_frame.winfo_height()
    check("%s: exactly one navbar" % label, len(headers()) == 1,
          "%d on show, steps %s" % (len(headers()), [h._step for h in headers()]))
    check("%s: exactly one footer" % label, len(footers()) == 1, "%d on show" % len(footers()))
    if step is not None:
        check("%s: the navbar is the one for this screen" % label,
              [h._step for h in headers()] == [step],
              "steps on show: %s" % [h._step for h in headers()])
    check("%s: browser is still on screen" % label, bool(app.browser_frame.winfo_ismapped()),
          "window %s, content area %dpx; form_area wants %dpx (%d packed), "
          "notice_area wants %dpx (%d packed)" % (
              app.root.geometry(), app.content_frame.winfo_height(),
              app.form_area.winfo_reqheight(),
              len([w for w in app.form_area.winfo_children() if w.winfo_manager()]),
              app.notice_area.winfo_reqheight(),
              len([w for w in app.notice_area.winfo_children() if w.winfo_manager()])))
    gap = app.browser_frame.winfo_rooty() - form_bottom
    check("%s: browser sits below the form, %dpx clear of it" % (label, app.BROWSER_GAP),
          gap == app.BROWSER_GAP, "gap is %dpx" % gap)
    below = app.browser_frame.winfo_rooty() + app.browser_frame.winfo_height()
    check("%s: browser is %dpx clear of the footer" % (label, app.BROWSER_MARGIN),
          app.content_frame.winfo_rooty() + app.content_frame.winfo_height() - below
          == app.BROWSER_MARGIN,
          "gap is %dpx" % (app.content_frame.winfo_rooty()
                           + app.content_frame.winfo_height() - below))
    check("%s: browser still has room for a page" % label, app.browser_frame.winfo_height() >= 80,
          "height %d" % app.browser_frame.winfo_height())
    check("%s: %d entry box(es), no leftovers" % (label, entry_count),
          len(entries()) == entry_count, "found %d" % len(entries()))
    check("%s: %d button(s), no leftovers" % (label, button_count),
          len(buttons()) == button_count,
          "found %s" % [b.cget("text") for b in buttons()])
    focused = app.root.focus_lastfor()
    check("%s: the caret is in the form, not in the page" % label,
          bool(entries()) and focused is entries()[0],
          "caret on %s" % (focused,))
    check("%s: the browser was told to let go of the keyboard" % label,
          app.browser_frame.released > 0)


# ---- steps ---------------------------------------------------------------------
# A step returns True to be run again on the next tick (waiting for a worker thread).

def card_screen():
    print("\n--- card screen ---")
    app.root.deiconify()
    app.card_number_content(app.root, None)


def check_card_screen():
    screen_is_sound("card screen", entry_count=1, button_count=1, step=1)
    check("card screen: Enter submits", bound("<Return>"))
    check("card screen: the reader's trailing Tab submits", bound("<Tab>"))
    state["card_entry"] = entries()[0]


def swipe_a_card():
    print("\n--- swipe a card: type it and let the reader send Tab ---")
    app.browser_frame.released = 0
    state["card_entry"].insert(0, "70343051234567890")
    app.root.event_generate("<Tab>", when="now")


def check_odometer_screen():
    if not buttons() or buttons()[0].cget("text") != "Submit":
        return True  # odo_content still building
    print("\n--- odometer screen ---")
    # The category table may already have landed; each of its rows adds 2 read-only cells.
    screen_is_sound("odometer screen", entry_count=1 + 2 * len(option_menus()), button_count=2,
                    step=2)
    check("odometer screen: Enter submits", bound("<Return>"))
    check("odometer screen: Tab does not submit an odometer", not bound("<Tab>"))
    check("odometer screen: the card box is gone", not state["card_entry"].winfo_ismapped())
    state["odo_entry"] = entries()[0]
    state["submit"] = [b for b in buttons() if b.cget("text") == "Submit"][0]
    state["close"] = [b for b in buttons() if b.cget("text") == "Close"][0]


def check_category_table():
    if not option_menus():
        return True  # the FleetCard lookup runs on a worker thread
    print("\n--- category table, on top of the odometer screen ---")
    check("a category dropdown per unknown item", len(option_menus()) == len(ITEMS),
          "found %d" % len(option_menus()))
    check("the table is above the browser",
          all(m.winfo_rooty() < app.browser_frame.winfo_rooty() for m in option_menus()))
    screen_is_sound("category screen", entry_count=1 + 2 * len(ITEMS), button_count=2, step=2)
    check("the table filled the dropdown that Submit reads back",
          app.dropdown.items == ITEMS and len(app.dropdown.selected_cat) == len(ITEMS),
          "items=%d selected_cat=%d" % (len(app.dropdown.items), len(app.dropdown.selected_cat)))
    for item in ITEMS:
        app.dropdown.selected_cat[item["id"]].set("Car Wash")
    check("a chosen category survives to set_items()",
          [i["description"] for i in app.dropdown.set_items()] == ["Car Wash"] * len(ITEMS))


def check_submit_enabled():
    if str(state["submit"].cget("state")) != "normal":
        return True  # waiting on trans_filler
    check("Submit turns on once the rego comes back", True)


def press_close():
    print("\n--- Close goes back to the card screen ---")
    app.browser_frame.released = 0
    state["close"].invoke()


def show_window_again():
    """What the POS socket does for the next sale; the app must re-arm the caret itself."""
    app.root.deiconify()


def check_back_on_card_screen():
    if len(buttons()) != 1 or buttons()[0].cget("text") != "Submit":
        return True
    screen_is_sound("card screen after Close", entry_count=1, button_count=1, step=1)
    check("card screen after Close: the odometer box is gone",
          not state["odo_entry"].winfo_ismapped())
    check("card screen after Close: the category table is gone", not option_menus())
    check("card screen after Close: the reader's Tab submits again", bound("<Tab>"))


def swipe_a_second_card():
    print("\n--- a second card must not stack a second form ---")
    app.browser_frame.released = 0
    entries()[0].insert(0, "70343059876543210")
    buttons()[0].invoke()


def check_second_odometer_screen():
    if not buttons() or len(buttons()) != 2:
        return True
    screen_is_sound("second odometer screen", entry_count=1 + 2 * len(option_menus()),
                    button_count=2, step=2)


# ---- main.bat: "show" over the socket --------------------------------------------------
# main.py connects and sends "show". The Infinity POS clicks from paths.json come FIRST,
# while the window is still hidden; then the window is shown, in front, caret in the entry.
user32 = ctypes.windll.user32 if os.name == "nt" else None
if user32 is not None:
    user32.GetForegroundWindow.restype = wt.HWND
    user32.GetAncestor.restype = wt.HWND
    user32.FindWindowW.restype = wt.HWND
    user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
pos = {"refocused": []}


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hwndActive", wt.HWND),
                ("hwndFocus", wt.HWND), ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND),
                ("hwndMoveSize", wt.HWND), ("hwndCaret", wt.HWND), ("rcCaret", wt.RECT)]


def focus_hwnd():
    """Where the Windows keyboard is, whichever process owns that window."""
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    user32.GetGUIThreadInfo(0, ctypes.byref(info))
    return info.hwndFocus or 0


def bring_to_front(hwnd):
    """Activate another process's window without synthesising input: attached to the
    foreground window's input thread, SetForegroundWindow is allowed."""
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


def describe(hwnd):
    title = ctypes.create_unicode_buffer(128)
    user32.GetWindowTextW(hwnd, title, 128)
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return "%s %r (pid %d)" % (hwnd, title.value, pid.value)


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def send_show():
    print("\n--- main.bat: 'show' over the socket, with the window hidden ---")
    app.root.withdraw()
    # An unpaid cart with items and sale notes: the case in which the POS is driven.
    app.isEmpty = lambda path: False
    app.hasPayments = lambda path: False
    app.hasSalenotes = lambda path: True
    hwnd = user32.GetAncestor(app.root.winfo_id(), 2) if user32 else None
    standin = user32.FindWindowW(None, "POS stand-in") if user32 else None

    def activate_standin():
        """On the Tk thread, as the worker's clicks are being 'made': the POS takes the front."""
        bring_to_front(standin)
        app.root.after(150, lambda: pos.__setitem__("standin_in_front", user32.GetForegroundWindow() == standin))

    def record_clicks(start, finish):
        pos["clicked"] = dict(at=time.time(), points=(start, finish),
                              viewable=app.root.winfo_viewable(), state=app.root.state(),
                              visible=bool(user32.IsWindowVisible(hwnd)) if user32 else None,
                              thread=threading.current_thread().name)
        if standin:
            app.root.after(0, activate_standin)

    app.mouse_movement = record_clicks
    real_focus_input = app.focus_input

    def counted_focus_input(*args, **kwargs):
        pos["refocused"].append(time.time())
        return real_focus_input(*args, **kwargs)

    app.focus_input = counted_focus_input
    app.root.bind("<Map>", lambda e: pos.setdefault("mapped_at", time.time())
                  if e.widget is app.root else None, add="+")
    app.PORT = free_port()  # never the live window's 9000
    app.start_socket_server(app.root, app.listen_for_show())

    def knock():
        time.sleep(0.3)
        with socket.create_connection(("127.0.0.1", app.PORT), timeout=2) as s:
            s.sendall(b"show")

    threading.Thread(target=knock, daemon=True).start()


def check_pos_driven_before_show():
    if "clicked" not in pos:
        return True
    clicked = pos["clicked"]
    check("show: the POS clicks from paths.json were made (mouse_movement(0, 4))",
          clicked["points"] == (0, 4), str(clicked["points"]))
    check("show: they were made while the window was still hidden",
          not clicked["viewable"] and clicked["state"] == "withdrawn" and "mapped_at" not in pos,
          str(clicked))
    check("show: they ran off the Tk thread, so the Tk loop kept turning",
          clicked["thread"] != "MainThread", clicked["thread"])


def check_window_shown_after_clicks():
    if "clicked" not in pos:
        check("show: the POS was driven at all", False)
        return
    refocused = [t for t in pos["refocused"] if t > pos["clicked"]["at"] + 1.0]
    if not refocused or time.time() < refocused[0] + 0.3:
        return True  # show_now follows the clicks and their second of sleep; let it land
    check("show: the window was shown only after the clicks and their second of sleep",
          "mapped_at" in pos and pos["mapped_at"] >= pos["clicked"]["at"] + 1.0,
          "clicked at %s, mapped at %s" % (pos["clicked"]["at"], pos.get("mapped_at")))
    check("show: the window is on screen with the caret in its entry",
          app.root.state() == "normal" and app.root.focus_lastfor() is entries()[0],
          "state %s, caret on %s" % (app.root.state(), app.root.focus_lastfor()))
    if not pos.get("standin_in_front"):
        print("  SKIP  show: the POS stand-in could not take the front, so whether the window takes it"
              " from the POS was not measured   -> foreground %s" % describe(user32.GetForegroundWindow()))
        return
    ours = user32.GetAncestor(app.root.winfo_id(), 2)
    # Windows parks the keyboard on the top level's own Tk window; Tk routes it to the entry.
    check("show: the window took the front from the POS, with the Windows keyboard",
          user32.GetForegroundWindow() == ours and focus_hwnd() == app.root.winfo_id(),
          "foreground %s, keyboard on %s, ours %s / %s" % (
              describe(user32.GetForegroundWindow()), describe(focus_hwnd()), ours, app.root.winfo_id()))


STEPS = [card_screen, check_card_screen, swipe_a_card, check_odometer_screen,
         check_category_table, check_submit_enabled, press_close, show_window_again,
         check_back_on_card_screen, swipe_a_second_card, check_second_odometer_screen,
         send_show, check_pos_driven_before_show, check_window_shown_after_clicks]


def pump_steps():
    if not STEPS:
        print("\n%s  (%d failed)" % ("ALL CHECKS PASSED" if not failures else "FAILED",
                                     len(failures)))
        for name in failures:
            print("  - " + name)
        app.root.quit()
        return
    step = STEPS[0]
    try:
        again = step()
    except Exception:
        traceback.print_exc()
        failures.append("exception in " + step.__name__)
        again = False
    if again:
        step.tries = getattr(step, "tries", 0) + 1
        if step.tries < 60:
            app.root.after(100, pump_steps)
            return
        failures.append("timed out waiting in " + step.__name__)
    STEPS.pop(0)
    app.root.after(200, pump_steps)


app.root.after(400, pump_steps)
app.root.mainloop()
app.root.destroy()
POS_STANDIN.terminate()
sys.exit(1 if failures else 0)
