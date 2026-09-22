"""Proof: Selenium drives the browser embedded in the Tk window - no mirror at all.

The embedded cefpython3 browser opens a remote-debugging port; chromedriver 2.40 (the
driver for its Chromium 66, already in fleet/drivers) attaches to it; then the very same
XPaths and calls fleet.py makes are run against it. If this passes, the second browser,
the second login and every injected script can go: the form the operator sees IS the
form Selenium fills and submits.

Runs against the mock purchase page, so nothing touches fco.fleetcard.com.au.

    fleet\\.venv\\Scripts\\python.exe tests\\selenium_drives_cef_check.py
"""
import ctypes
import os
import sys
import tempfile
import threading
import tkinter as tk
import traceback
from pathlib import Path

FLEET_DIR = Path(__file__).resolve().parent.parent
MOCK_DIR = Path(__file__).resolve().parent / "mock_fleetcard"
CHROMEDRIVER = FLEET_DIR / "drivers" / "chromedriver_2.40.exe"
DEBUG_PORT = 9223
sys.path.insert(0, str(FLEET_DIR))
os.chdir(tempfile.mkdtemp(prefix="sel_cef_"))

from cefpython3 import cefpython as cef  # noqa: E402
import ui_theme as ui  # noqa: E402

failures = []
notes = []


def check(name, ok, detail=""):
    line = ("  PASS  " if ok else "  FAIL  ") + name + (("   -> " + detail) if detail else "")
    notes.append(line)
    if not ok:
        failures.append(name)


# ---- the Tk window with the embedded browser, exactly as the app builds it ------------
root = tk.Tk()
root.title("selenium drives cef")
root.geometry("900x600")
ui.style_root(root)
entry = tk.Entry(root, **ui.entry_options())
entry.pack(fill="x", padx=16, pady=16)
frame = tk.Frame(root, bg=ui.BG, bd=0, highlightthickness=0, height=260)
frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

cef.Initialize(settings={"log_severity": cef.LOGSEVERITY_ERROR,
                         "remote_debugging_port": DEBUG_PORT})
browser = [None]


def create_browser(_event=None):
    if browser[0] is None and frame.winfo_width() > 1 and frame.winfo_height() > 1:
        info = cef.WindowInfo()
        info.SetAsChild(frame.winfo_id(), [0, 0, frame.winfo_width(), frame.winfo_height()])
        browser[0] = cef.CreateBrowserSync(info, url=(MOCK_DIR / "purchase.html").as_uri())
        browser[0].SetClientHandler(NeverTakeTheKeyboard())
        user32.SetForegroundWindow(user32.GetAncestor(root.winfo_id(), 2))
        # CEF takes the keyboard when the browser is created; the app takes it back with
        # exactly this. The question here is whether Selenium then takes it AGAIN.
        root.after(800, take_keyboard_back)
        root.after(1500, lambda: threading.Thread(target=drive, daemon=True).start())
        root.after(1500, watch_keyboard)


user32 = ctypes.windll.user32


class NeverTakeTheKeyboard:
    """The page never gets the native keyboard, whatever asks for it.

    Selenium focuses elements to type into them, and in CEF that asks the browser window
    for the Windows focus - which would take the operator's odometer keystrokes into the
    page. Refusing it here is only viable if Selenium can still type; that is what this
    proves. The operator has no reason to click into the page: the Tk form is the input.
    """

    def OnSetFocus(self, browser, source, **_kwargs):
        return True


def take_keyboard_back():
    """What cef_browser.release_keyboard does: drop the page's focus, take it for the
    window, put the caret back in the entry."""
    browser[0].SetFocus(False)
    root.focus_force()
    entry.focus_set()


keyboard_in_page = [0]
keyboard_samples = [0]


def watch_keyboard():
    """Sample where the Windows keyboard is while Selenium fills the form."""
    hwnd = user32.GetFocus()
    if hwnd:
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


frame.bind("<Configure>", create_browser)


def pump():
    cef.MessageLoopWork()
    if root.winfo_exists():
        root.after(10, pump)


root.after(10, pump)
root.deiconify()
root.lift()
entry.focus_set()


# ---- Selenium, on a worker thread: CEF answers it only while Tk pumps the loop ---------
def drive():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import Select, WebDriverWait

    driver = None
    try:
        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:%d" % DEBUG_PORT)
        # chromedriver 2.40 speaks the old wire protocol unless asked; selenium 4 needs W3C
        options.add_experimental_option("w3c", True)
        driver = webdriver.Chrome(service=Service(str(CHROMEDRIVER)), options=options)
        check("chromedriver 2.40 attached to the embedded browser", True,
              "session %s" % driver.session_id)
        check("it sees the page the window shows",
              driver.current_url.endswith("purchase.html"), driver.current_url)

        from selenium.common.exceptions import StaleElementReferenceException

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
        WebDriverWait(driver, 20).until(EC.presence_of_element_located(
            (By.XPATH, "(//a[contains(@class, 'tab-btn')])[5]")))
        click_through_postback("(//a[contains(@class, 'tab-btn')])[5]")   # products_filler
        settled.until(lambda d: "highlight" in d.find_element(
            By.XPATH, "(//a[contains(@class, 'tab-btn')])[5]").get_attribute("class"))
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
        again = webdriver.Chrome(service=Service(str(CHROMEDRIVER)), options=options)
        check("a fresh chromedriver 2.40 re-attaches after the first is stopped (restart)",
              again.find_element(By.ID, "cardNumber").get_attribute("value") == "703430512345678",
              "session %s" % again.session_id)
        again.get((MOCK_DIR / "purchase.html").as_uri())   # what get_purchase_driver does per card
        WebDriverWait(again, 10).until(EC.presence_of_element_located(
            (By.XPATH, "(//a[contains(@class, 'tab-btn')])[5]")))
        check("re-opening the purchase page for the next card works (get_purchase_driver)", True)
        driver = again
    except Exception:
        check("Selenium drove the embedded browser without error", False,
              traceback.format_exc().strip().splitlines()[-1])
        notes.append(traceback.format_exc())
    finally:
        if driver is not None:
            try:
                driver.service.stop()   # not quit(): that would close the window's browser
            except Exception:
                pass
        root.after(0, finish)


def finish():
    check("the caret never left the Tk entry", root.focus_lastfor() is entry,
          "caret on %s" % (root.focus_lastfor(),))
    check("the Windows keyboard never went into the page while Selenium typed",
          keyboard_samples[0] > 0 and keyboard_in_page[0] == 0,
          "%d of %d samples in the page" % (keyboard_in_page[0], keyboard_samples[0]))
    print("\n".join(notes))
    print("\n%s  (%d failed)" % ("ALL CHECKS PASSED" if not failures else "FAILED", len(failures)))
    for name in failures:
        print("  - " + name)
    if browser[0] is not None:
        browser[0].CloseBrowser(True)
    root.after(300, root.quit)


root.after(60000, lambda: (check("finished within 60s", False), finish()))
root.mainloop()
try:
    root.destroy()
except tk.TclError:
    pass
cef.Shutdown()
sys.exit(1 if failures else 0)
