import embedded_browser  # first: COM must be an STA on this thread before anything uses it
import tkinter as tk
import threading
from fleet import *
from time import sleep
import json
import tkinter.font as tkFont
import os
from util import play_sound, PATHS_FILE, path_format
from mousemovement import mouse_movement
from dropdown import *
from tkinter import ttk
from dbconn import FleetCardVal
from mousemovement import mouse_movement
from fleet import valid_options, get_fleetcard_login, login
# tk_socket_app.py
import socket
import threading
import tkinter as tk
import sys
import json
import atexit
import traceback
from selenium.common.exceptions import TimeoutException as SeleniumTimeout
from hex_reader import *
import ui_theme as ui
from embedded_browser import BrowserFrame, FLEET_CARD_TAB_XPATH, PURCHASE_URL


first_time =True
HOST = "127.0.0.1"   # local only
PORT = 9000   # port for socket server
invalid_items = []


def listen_for_show():
    """The socket main.bat knocks on, held exclusively: one window per machine.

    A second copy of the window would log in to FleetCard a second time and start a
    browser of its own, so it is refused here, before it starts anything. Plain
    SO_REUSEADDR would let it bind over a port that is already listening on Windows.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    listener.bind((HOST, PORT))
    listener.listen()
    return listener


def start_socket_server(root, listener):
    """Show the Tkinter window whenever a client connects to the listener.

    main.bat (main.py) sends "show" when a fleet card sale is ready at the till. The
    Infinity POS is driven first - the clicks from paths.json, on a worker thread, so
    the Tk loop keeps turning while the POS is driven - and only then is the window
    shown, in front, with the caret in its entry, where the card swipe has to land.
    """
    shows = {"serial": 0}  # bumped per "show", so a show that was overtaken drops itself

    def show_window():
        shows["serial"] += 1
        threading.Thread(target=drive_pos, args=(shows["serial"],), daemon=True).start()

    def drive_pos(serial):
        """Worker thread: the POS clicks for this sale, then the window."""
        try:
            cd_path = path_format(path_data['cd'])
            if not isEmpty(cd_path) and not hasPayments(cd_path):
                mouse_movement(0, 4)
                sleep(1)
                if not hasSalenotes(cd_path):
                    play_sound("error")
            else:
                play_sound("error")
        except Exception as error:
            print(f"POS sale check error: {error}")
        root.after(0, show_now, serial)

    def show_now(serial):
        """The POS clicks are done: the window, in front, ready for the swipe.

        Activating the POS for the clicks made it the foreground process, and Windows
        then refuses SetForegroundWindow to everyone else - Tk's focus_force is one
        such call - so the front is taken the way Windows allows
        (embedded_browser.bring_to_front).
        """
        if serial != shows["serial"]:
            return  # a newer show is on its way and shows the window itself
        root.deiconify()
        root.lift()
        root.focus_force()
        embedded_browser.bring_to_front(root)
        root.attributes("-topmost", True)
        root.after(100, lambda: root.attributes("-topmost", False))
        # deiconify fires <Map>, which puts the caret back in the entry; said again
        # here for a window that was already on screen.
        focus_input()

    def handle_client(conn):
        try:
            if conn.recv(16).strip().lower() != b"show":
                return
            root.after(0, show_window)
        except Exception as error:
            print(f"Socket show handler error: {error}")
        finally:
            conn.close()

    def server():
        with listener as s:
            while True:
                try:
                    conn, _ = s.accept()
                    threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
                except Exception as e:
                    print("❌ Accept error:", e)
                    break

    thread = threading.Thread(target=server, daemon=True)
    thread.start()




products_filler_result = None
db_connection=True
db=None
try:
    db = FleetCardVal()
except:
    db_connection=False

dropdown = Dropdown()
page_change_var = None
db_items=[]
music_path = path_format(path_data['cred'])
# The screens pass this around, but every real call goes through get_purchase_driver,
# which uses the window's own browser session (start_browser_session).
driver_instance = None

def get_purchase_driver():
    """Open a fresh purchase form in the window's browser and return a driver for it.

    The browser is the one under the Tk screens and the driver is the one this process
    attached to it - not the session in cred.json, which another copy of the window or
    a stale run could have written. If the start-up attach failed (no network for the
    chromedriver download, say) it is tried again here, for this card, so a network
    that has come back is picked up; what still fails is raised at once with its cause,
    for the screen to show, instead of being waited out with a customer at the till.
    """
    with session_lock:   # start_browser_session may still be logging in
        if embedded_driver is None:
            if browser_frame.error:
                raise RuntimeError(browser_frame.error)
            if not browser_created.wait(timeout=15):
                raise RuntimeError("the browser in the window has not been created, see tkinter_fleet.log")
            start_browser_session()
            if embedded_driver is None:
                raise RuntimeError(browser_error)
    driver = embedded_driver
    driver.get(PURCHASE_URL)
    if not driver.current_url.startswith(PURCHASE_URL):
        # The FleetCard site logged us out, log back in and open the form again
        driver.get("https://fco.fleetcard.com.au/")
        login(*get_fleetcard_login(), driver)
        driver.get(PURCHASE_URL)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, FLEET_CARD_TAB_XPATH))
    )
    return driver
# If you already fixed your path with raw string


# Open and read the JSON file
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = PATHS_FILE  # fleet/paths.json
json_path = os.path.join(current_dir, 'paths.json')
with open(file_path, "r") as f:
    path_data = json.load(f)
# Create main Tkinter root
WINDOW_SIZE = "900x720"
# Space around the page. The sides and the bottom line up with the padding the form
# panels use; the gap above it is wider, so the form of the screen on show and the
# web page underneath read as two separate things rather than one surface.
BROWSER_MARGIN = 16
BROWSER_GAP = 32

if __name__ == "__main__":
    # Before the window and its browser exist: a second copy of the window stops here.
    try:
        show_listener = listen_for_show()
    except OSError as error:
        print("Another Fuelzone window is already listening on %s:%d (%s); this one exits" % (HOST, PORT, error))
        sys.exit(1)

root = tk.Tk()
root.title("Fuelzone")
root.geometry(WINDOW_SIZE)
root.minsize(720, 480)
ui.style_root(root)

# Every screen is laid out the same way, so the browser stays put while screens come
# and go:  header | form_area + notice_area | browser | footer.  The header, footer and
# browser are built once here; only form_area and notice_area are emptied per screen.
content_frame = tk.Frame(root, bg=ui.BG)
content_frame.pack(fill="both", expand=True)
root._content_frame = content_frame
page_frame = tk.Frame(content_frame, bg=ui.BG)
page_frame.pack(fill="x")
form_area = tk.Frame(page_frame, bg=ui.BG)
form_area.pack(fill="x")
notice_area = tk.Frame(page_frame, bg=ui.BG)
notice_area.pack(fill="x")
# dropdown.py packs its category table here, under whichever form is on show.
root._screen_frame = notice_area
# The one browser (WebView2). fleet.py drives it with Selenium through this port - via
# the front door that lets chromedriver attach to it - so the form the operator sees
# under the screens is the form that is filled and submitted.
DEBUG_PORT = embedded_browser.free_port()
browser_created = threading.Event()   # the page exists in the window: chromedriver can attach
browser_ready = threading.Event()     # start_browser_session has run once, whichever way it went
session_lock = threading.RLock()
embedded_driver = None
browser_error = None


def start_browser_session():
    """Worker thread: attach chromedriver to the window's browser, log in, open the form.

    Off the Tk thread because the browser only answers Selenium while Tk pumps its
    messages, and because the first start on a machine downloads the chromedriver that
    matches the installed WebView2 runtime. Done once, by whichever thread gets here
    first: the browser's on_created, or get_purchase_driver retrying a failed start.
    cred.json is written for anything outside this process that attaches by session id
    (fleet.py); the window itself uses the driver. Then the login and the purchase form,
    with fleet.py's own login(): if that failed, get_purchase_driver notices the bounce
    and logs in again on the next card.
    """
    global embedded_driver, browser_error
    with session_lock:
        if embedded_driver is not None:
            return
        try:
            driver = embedded_browser.attach_driver(DEBUG_PORT, embedded_browser.chromedriver_path())
            with open(music_path, "w") as file:
                json.dump({"session_id": driver.session_id,
                           "executor_url": driver.service.service_url}, file, indent=4)
            embedded_driver = driver
            atexit.register(driver.service.stop)
            driver.get(embedded_browser.LOGIN_URL)
            login(*get_fleetcard_login(), driver)
            driver.get(PURCHASE_URL)
        except Exception as error:
            browser_error = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
            print("Could not start the browser session:", error)
        finally:
            browser_ready.set()
            root.after(0, focus_input)


def on_browser_created():
    browser_created.set()
    threading.Thread(target=start_browser_session, daemon=True).start()


embedded_browser.initialize(DEBUG_PORT)
browser_frame = BrowserFrame(content_frame, url=embedded_browser.LOGIN_URL, on_created=on_browser_created)
browser_frame.pack(fill="both", expand=True, padx=BROWSER_MARGIN,
                   pady=(BROWSER_GAP, BROWSER_MARGIN))
atexit.register(embedded_browser.shutdown)


# Bumped every time a screen is built, so work queued by a screen that has since been
# replaced (a slow FleetCard lookup for a card that was already closed) can drop itself.
_screen_serial = 0


def clear_screen():
    """Hide the screen on show; the header, footer and browser are shared and stay.

    Returns the serial of the screen about to be built.
    """
    global _screen_serial
    _screen_serial += 1
    for area in (form_area, notice_area):
        for widget in area.winfo_children():
            widget.pack_forget()
        # pack leaves a master at its last requested size once its slaves are gone, so an
        # emptied area keeps reserving the height of the screen before it - after a long
        # category table that is enough to squeeze the browser off screen entirely.
        area.configure(height=1)
    return _screen_serial


# ---- Keyboard focus -----------------------------------------------------------
# The browser is a child window of this same top-level window, so while it holds the
# keyboard a card swipe lands in the web page instead of the entry of the screen on
# show. Only a click in the page can give it the keyboard, and embedded_browser hands
# it straight back; each screen registers its entry here, and the caret is put back in
# it whenever a screen is built, the window is re-shown, or Tk gets the window back.
_active_entry = None


def focus_input(entry=None):
    """Put the caret in the entry of the screen on show, taking the keyboard off the page."""
    global _active_entry
    if entry is not None:
        _active_entry = entry
    target = _active_entry
    if target is None:
        return
    try:
        if not target.winfo_exists():
            return
        browser_frame.release_keyboard()  # if the page holds the Windows focus, take it back
        target.focus_set()
        # A screen being built has not mapped its entry yet, so that focus_set is only
        # deferred; say it again once the layout has settled and the entry is viewable.
        root.after_idle(_focus_if_alive, target)
    except tk.TclError:
        pass


def _focus_if_alive(target):
    try:
        if target.winfo_exists() and target is _active_entry:
            target.focus_set()
    except tk.TclError:
        pass


def _on_window_activated(_event=None):
    """We have the window back but the keyboard is still in the page: take it back."""
    if root.focus_get() is None:
        focus_input()


def _on_window_shown(event):
    """Re-shown for the next sale. The screen behind it was built while it was hidden,
    so Tk dropped the focus it was given then; put the caret back in the entry."""
    if event.widget is root:
        root.after(50, focus_input)


root.bind("<Map>", _on_window_shown, add="+")  # the browser frame listens for <Map> too
root.bind("<Activate>", lambda event: root.after(50, _on_window_activated))
root.bind("<FocusIn>", _on_window_activated)


def bind_screen_keys(submit_button, tab_submits):
    """Point Enter - and on the card screen the reader's trailing Tab - at this screen's button."""
    root.bind("<Return>", lambda event: submit_button.invoke())
    root.bind("<KP_Enter>", lambda event: submit_button.invoke())
    if tab_submits:
        root.bind("<Tab>", lambda event: submit_button.invoke())
    else:
        root.unbind("<Tab>")
import tkinter as tk
import threading
from pathlib import Path
import json
def db_status_show():
        db_label = ui.show_footer(root, db_connection)
    
def odo_content(driver, card_number, root, elements):
    global first_time
    if not card_number:
        return
    first_time =False
    if not root.state() == "withdrawn": play_sound("notify")
    # if not driver.current_url=="https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342":
    #     driver.get("https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342")
    screen = clear_screen()
    card_val_status_var = tk.StringVar()
    # Read by run_form_filler below, so it has to be set before that thread starts.
    card_number_processed = '7034305' + card_number.split('7034305')[-1][:9]
    def show_categories(result):
        """Add the category table under the odometer form; the browser stays below it."""
        if screen != _screen_serial:
            return  # this card's screen is gone, its table would land on someone else's
        if root.state() == "withdrawn":
            # Hidden window: the table would be built against a size nobody can see.
            root.after(100, show_categories, result)
            return
        if len(result) == 2 and result[0] == "404":
            tk.Label(notice_area, text="Item Not Found — choose a category below", anchor="w",
                     **ui.notice_options("warning")).pack(fill="x", padx=16, pady=(6, 6))
            # The module-level dropdown, so odo_submit_command reads back these choices.
            dropdown.dropDownMenu(tk, root, "", result[1], None)
            focus_input()

    # Function to run form filler in a thread
    def run_form_filler():
        nonlocal driver
        global product_filler_result
        global invalid_items
        try:
            driver = get_purchase_driver()
        except Exception as e:
            print("Could not open the purchase page:", e)
            root.after(0, card_val_status_var.set, "Error: %s" % e)
            return
        try:
            result= products_filler(driver, "")
            product_filler_result = result

            if len(result)==2:
                if result[0] == "404":
                    # Tk is not thread safe: build the table on the main thread.
                    root.after(0, show_categories, result)

            msg=trans_filler(driver, card_number_processed)
            # Safely update the StringVar in the main thread
            root.after(0, card_val_status_var.set, msg)
        except Exception as e:
            root.after(0, card_val_status_var.set, f"Error: {e}")
    threading.Thread(target=run_form_filler, daemon=True).start()
    # run_form_filler()
        


    page_change_var = tk.StringVar(value="")    
    # page_change_var.trace_add("write", on_status_page_change)
    card_val_status_var.set("Waiting for validation")
    current_text = card_val_status_var.get()
    iteration = 0
    
    def update_label(iteration=0):
        dot_count = iteration % 4
        if not card_val_status_var.get().startswith("Err") and not card_val_status_var.get().startswith("Rego"):
            card_val_status_var.set(current_text + " " + ("." * dot_count))
            root.after(900, lambda: update_label(iteration + 1))

    # start the loop
    update_label()
    
    ui.show_header(root, step=2)
    ui.show_footer(root, db_connection)
    status_label = ui.StatusBanner(form_area, textvariable=card_val_status_var)
    status_label.pack(fill="x", padx=16, pady=(10, 0))
    input_form = ui.panel(form_area)
    input_form.pack(fill="x", padx=16, pady=(8, 0))
    input_form.grid_columnconfigure(1, weight=1)
    odo_entry = tk.Entry(input_form, width=10, **ui.entry_options(font=ui.FONT_INPUT_COMPACT))
    button_group = tk.Frame(input_form, bg=ui.SURFACE)
    button_group.grid(row=1, column=1, sticky="se", padx=(0, 14), pady=(0, 10))
    # Close button
    
    label_var = tk.StringVar()
    # label_var.set("processing")
    label_var.set("processing")
    label = tk.Label(notice_area, textvariable=label_var, **ui.notice_options("info", font=ui.FONT_STATUS, padx=16, pady=3))

    current_text_proc = label_var.get()
    
    def update_label_proc(iteration=0):
        dot_count = iteration % 4
        if label_var.get().startswith(current_text_proc):  # still processing
            label_var.set(current_text_proc + " " + ("." * dot_count))
            root.after(900, lambda: update_label_proc(iteration + 1))

    # # start the loop

    
    
    odo_submit_btn = ui.Button(button_group, text="Submit", kind="primary", width=8)
    odo_submit_btn.config(state='disabled')
    # Enter presses Submit (does nothing while the button is still disabled)
    bind_screen_keys(odo_submit_btn, tab_submits=False)



    
 
        
    def on_status_change_msg(*args):
        enable_button()
    def on_status_change_bool(*args):
        enable_button()
    def enable_button():
        
        if card_val_status_var.get().startswith('Rego'):
            odo_submit_btn.config(state="normal")  # enable properly
            odo_submit_btn.config(command=lambda: odo_submit_command(driver, odo_entry.get(), dropdown))
        if card_val_status_var.get().startswith('Err'):
            odo_submit_btn.config(state="disabled")  # disable otherwise
            
        if card_val_status_var.get().startswith('Err'):
            if not root.state() == "withdrawn": play_sound("error")
    def redo_command(root):
        # Back to the card screen; Tk widgets may only be touched on the main thread.
        root.after(0, card_number_content, root, driver_instance)

    card_val_status_var.trace_add("write", lambda *args: on_status_change_msg(*args))
    

    def hide_window():
        # root.withdraw()
        # redo_command(root)
        global first_time
        first_time = False
        root.withdraw()
        redo_command(root)

    odo_label = tk.Label(input_form, text="ODOMETER", font=ui.FONT_CAPTION, fg=ui.TEXT_MUTED, bg=ui.SURFACE)
    odo_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(8, 3))
    odo_entry.grid(row=1, column=0, sticky="w", padx=(14, 0), pady=(0, 10))
    focus_input(odo_entry)
    odo_submit_btn.pack(side="left", padx=(0, 8))
    odo_submit_btn.config(font=ui.FONT_BUTTON)
    redo_btn = ui.Button(
        button_group,
        text="Close",
        command=hide_window,  # <-- remove the ()
        kind="secondary",
        width=6
    )
    redo_btn.config(font=ui.FONT_BUTTON)
    redo_btn.pack(side="right")

    
    submitting = threading.Event()  # blocks a second submit (e.g. Enter held down) while one is running
    error_label = tk.Label(notice_area, text="Error: timeout", **ui.notice_options("error"))

    # Everything Tk here runs on the Tk thread through root.after; the worker thread only
    # drives the browser and the database. A Tk call from a worker is marshalled to the
    # Tk thread and blocks until it is served, and the one block that still made such
    # calls - the start of the submit - is where the second sale's Submit was seen to
    # hang before its first Selenium call.
    def show_processing():
        label.pack(pady=10, side="top")
        update_label_proc()

    def show_failure(text, tone="error"):
        label.pack_forget()
        label_var.set("")  # stops the dots
        error_label.config(text=text, **ui.tone_colors(tone))
        error_label.pack(pady=10)

    def show_success():
        label_var.set('Processed!')
        page_change_var.set("It has been processed")
        root.withdraw()
        redo_command(root)

    def odo_submit_command(driver, odo_entry, dropdown:Dropdown):
        if submitting.is_set():
            return
        submitting.set()
        # Read on the Tk thread, before the worker starts: the category choices and the
        # rego live in Tk variables.
        items = dropdown.set_items()
        rego = ""
        if card_val_status_var.get().split(":"):
            rego = card_val_status_var.get().split(":")[1]

        def task():
            try:
                submit_task()
            finally:
                submitting.clear()

        def submit_task():
            root.after(0, show_processing)
            play_sound("notify")
            try:
                odo_submit(driver, odo_entry)
                result = re_enter_products(driver, card_number, items)
                print("result", result)
                if not result:
                    root.after(0, show_failure, 'You need to select a category...', "warning")
                    return
                exp_month, exp_year = get_exp_month_year(driver)
                status = form_submit(driver)
            except Exception as error:
                # FleetCard not accepting the transaction ends here: form_submit waits 20 s
                # for the receipt page and raises. The operator has to be told, and Submit
                # is theirs again once `submitting` clears.
                traceback.print_exc()
                text = "Error: timeout" if isinstance(error, SeleniumTimeout) else "Error: %s" % error
                root.after(0, show_failure, text)
                play_sound("error")
                return
            if status != "success":
                root.after(0, show_failure, "Error: timeout")
                play_sound("error")
                return
            root.after(0, show_success)
            if db.check_db_connection:
                if rego:
                    for item in valid_options:
                            print("ITEM DETAILS", item)
                            from datetime import datetime
                            date_time=datetime.now()
                            db.insert_from_pdf(card_number_processed, item[1], "complete", rego, item[2], date_time, exp_month, exp_year)

        threading.Thread(target=task).start()


import json


# Path to the Music folder JSON file

def write_driver_session(driver):
    session_id = driver.session_id
    executor_url = driver.command_executor._url
    # Save details for later use
    with open("driver_session.json", "w") as f:
        json.dump({"session_id": session_id, "executor_url": executor_url}, f)
    # print("Saved session:", session_id, executor_url)

def main_app():
    # sleep(5)
    # root.withdraw()
    
    # mouse_movement(0, 2)
    """
    Main app GUI with card entry and submit button.
    """
    

    # root.withdraw()
    # Bind Tab to submit button
    card_number_content(root, driver_instance)
    root.mainloop()
    

def card_number_content(root, driver_instance):
    global first_time
        # Card entry label
    # if not driver_instance.current_url =="https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342":
    #     driver_instance.get("https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342")

    clear_screen()
    root.geometry(WINDOW_SIZE)

    ui.show_header(root, step=1)
    card_label = tk.Label(form_area, text="CARD NUMBER", font=ui.FONT_CAPTION, fg=ui.TEXT_MUTED, bg=ui.BG, anchor="w")
    card_label.pack(fill="x", padx=28, pady=(24, 4))

    # Entry field
    card_entry = tk.Entry(form_area, width=30, **ui.entry_options())
    card_entry.pack(fill="x", padx=28, ipady=3)

    card_submit = ui.Button(
        form_area,
        text="Submit",
        kind="primary",
        command=lambda: submit_card_number(card_entry.get())
    )
    card_submit.pack(fill="x", padx=28, pady=(16, 0), ipady=3)
    

    db_status_show()

    bind_screen_keys(card_submit, tab_submits=True)
    focus_input(card_entry)

    def submit_card_number(card_number):
        odo_content(driver_instance, card_number, root, [card_submit, card_label, card_entry])

if __name__ == "__main__":
        mouse_loc = path_data['mouseMovement']
        start_socket_server(root, show_listener)

        def on_close():
            global first_time
            first_time = False
            root.withdraw()
            root.after(0, card_number_content, root, driver_instance)


        root.protocol("WM_DELETE_WINDOW", on_close)
        main_app()
