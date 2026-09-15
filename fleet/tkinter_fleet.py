import tkinter as tk
import threading
from fleet import *
from time import sleep
import json
import tkinter.font as tkFont
import os
from util import play_sound, PATHS_FILE, path_format
import cef_browser
from mousemovement import mouse_movement
from dropdown import *
from tkinter import ttk
from dbconn import FleetCardVal
from mousemovement import mouse_movement
from fleet import valid_options
# tk_socket_app.py
import socket
import threading
import tkinter as tk
import sys
from hex_reader import *
import ui_theme as ui


first_time =True
HOST = "127.0.0.1"   # local only
PORT = 9000   # port for socket server
WINDOW_SIZE = "900x800"   # the form on top, the FleetCard browser below it
invalid_items = []
def start_socket_server(root):
    """Start a socket server that unhides the Tkinter window whenever a client connects."""
    
    def handle_client(conn):
        try:
            cd_path=path_format(path_data['cd'])
            # Any client connection will trigger showing the window
            if not isEmpty(cd_path) and not hasPayments(cd_path):
                
                mouse_movement(0, 4)
                sleep(1)
                if hasSalenotes(cd_path):
                    root.after(0, root.deiconify)
                else:
                    if not root.state() == "withdrawn": play_sound("error")

            else:
                if not root.state() == "withdrawn":play_sound("error")

        finally:
            conn.close()

    def server():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, PORT))
                s.listen()
                # print(f"✅ Socket server listening on {HOST}:{PORT}")
            except Exception as e:
                print("❌ Socket error:", e)
                return

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
# The browser is part of this window (cef_browser.py), get_purchase_driver fetches its driver for each card
driver_instance = None

PURCHASE_URL = "https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342"

def get_purchase_driver():
    """Open a fresh purchase form in the embedded browser, logging in again if the site logged us out.

    Call from a worker thread: the browser only loads pages while the Tk main loop is running.
    """
    driver = cef_browser.get_driver()
    driver.get(PURCHASE_URL)
    if not driver.current_url.startswith(PURCHASE_URL):
        # The FleetCard site logged us out, log back in and open the form again
        driver.get("https://fco.fleetcard.com.au/")
        login(*get_fleetcard_login(), driver)
        driver.get(PURCHASE_URL)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "(//a[contains(@class, 'tab-btn')])[5]"))
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
root = tk.Tk()
root.title("Fuelzone")
root.geometry(WINDOW_SIZE)
ui.style_root(root)
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
    root.unbind("<Tab>")
    first_time =False
    if not root.state() == "withdrawn": play_sound("notify")
    # if not driver.current_url=="https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342":
    #     driver.get("https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342")
    # for element in elements:
    #     element.pack_forget()
    for widget in root.winfo_children():
        widget.pack_forget()
    card_val_status_var = tk.StringVar()
    def check_state(result):
        if not root.state() == "withdrawn":
            print("Not Withdrawn")
            
            # result= products_filler(driver_instance, "")
            if len(result)==2:
                if result[0] == "404":
                    tk.Label(root, text="Item Not Found — choose a category below", anchor="w", **ui.notice_options("warning")).pack(fill="x", padx=16, pady=(6, 6))
                    items = result[1]
                    dropdown.dropDownMenu(tk, root, "", items, None)
        else:
            root.after(100, lambda: check_state())

    def filler_func(result):
        
        if not first_time:
            print("GOING TO THE CHECK STATE FUNCTION")
            check_state(result)    
        else:
           
            # result= products_filler(driver_instance, "")
            if len(result)==2:
                if result[0] == "404":
                        tk.Label(root, text="Item Not Found — choose a category below", anchor="w", **ui.notice_options("warning")).pack(fill="x", padx=16, pady=(6, 6))
                        items = result[1]
                        dropdown = Dropdown()
                        dropdown.dropDownMenu(tk, root, "", items)

    # Function to run form filler in a thread
    def run_form_filler():
        nonlocal driver
        global product_filler_result
        global invalid_items
        try:
            driver = get_purchase_driver()
        except Exception as e:
            print("Could not open the purchase page:", e)
            root.after(0, card_val_status_var.set, "Error: can't open the FleetCard page, see tkinter_fleet.log")
            return
        try:
            result= products_filler(driver, "")
            product_filler_result = result

            if len(result)==2:
                if result[0] == "404":
                    filler_func(result)
                
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
    status_label = ui.StatusBanner(root, textvariable=card_val_status_var)
    status_label.pack(fill="x", padx=16, pady=(10, 0))
    input_form = ui.panel(root)
    input_form.pack(fill="x", padx=16, pady=(8, 0))
    input_form.grid_columnconfigure(1, weight=1)
    odo_entry = tk.Entry(input_form, width=10, **ui.entry_options(font=ui.FONT_INPUT_COMPACT))
    button_group = tk.Frame(input_form, bg=ui.SURFACE)
    button_group.grid(row=1, column=1, sticky="se", padx=(0, 14), pady=(0, 10))
    # Close button
    
    label_var = tk.StringVar()
    # label_var.set("processing")
    label_var.set("processing")
    label = tk.Label(root, textvariable=label_var, **ui.notice_options("info", font=ui.FONT_STATUS, padx=16, pady=3))

    current_text_proc = label_var.get()
    
    def update_label_proc(iteration=0):
        dot_count = iteration % 4
        if not label_var.get()== 'Processed!' :
            label_var.set(current_text_proc + " " + ("." * dot_count))
            root.after(900, lambda: update_label_proc(iteration + 1))

    # # start the loop

    
    
    odo_submit_btn = ui.Button(button_group, text="Submit", kind="primary", width=8)
    odo_submit_btn.config(state='disabled')
    # Enter presses Submit (does nothing while the button is still disabled)
    root.bind("<Return>", lambda event: odo_submit_btn.invoke())



    
 
        
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
        def task():
            
            for w in root.winfo_children():
                w.pack_forget() 
            card_number_content(root, driver_instance)
                    
        threading.Thread(target=task).start()

    card_val_status_var.trace_add("write", lambda *args: on_status_change_msg(*args))
    
    # Process card number
    card_number_split = card_number.split('7034305')
    card_number_processed = '7034305' + card_number_split[-1][:9]
    # print("Processed card number:", card_number_processed)

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
    odo_entry.focus_set()
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
    cef_browser.show(root)

    
    submitting = threading.Event()  # blocks a second submit (e.g. Enter held down) while one is running
    def odo_submit_command(driver, odo_entry, dropdown:Dropdown):
        if submitting.is_set():
            return
        submitting.set()
        def task():
            try:
                submit_task()
            finally:
                submitting.clear()
        def submit_task():
            label.pack(pady=10, side="top")
            update_label_proc()
            if not root.state() == "withdrawn": play_sound("notify")
            error_label = tk.Label(root, text="Error: timeout", **ui.notice_options("error"))

            odo_submit(driver, odo_entry)
            result = re_enter_products(driver, card_number, dropdown.set_items())
            print("result", result)
            if not result:
                tk.Label(text='You need to select a category...', **ui.notice_options("warning")).pack()
            else:
                exp_month, exp_year = get_exp_month_year(driver)
                status = form_submit(driver)
                
                if status == "success":
                    label_var.set('Processed!')
                    root.after(0, page_change_var.set, "It has been processed")
                    # print("SUCCESS")
                 
                    # mouse_movement(3, 5)
                    # print("CARD NUMBER", card_number_processed)
                    root.withdraw()
                    redo_command(root)
                    rego=""
                    if card_val_status_var.get().split(":"):
                        rego = card_val_status_var.get().split(":")[1]
                    if db.check_db_connection:                  
                        if rego:
                            for item in valid_options:
                                    print("ITEM DETAILS", item)
                                    from datetime import datetime
                                    date_time=datetime.now()
                                    db.insert_from_pdf(card_number_processed, item[1], "complete", rego, item[2], date_time, exp_month, exp_year)
            
                else:
                    error_label.config(**ui.tone_colors("error"))
                    error_label.pack(pady=10)
                    if not root.state() == "withdrawn":play_sound("error")
                

            #####TO BE CHANGED#######

                    
           
            
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
    
    cef_browser.initialize()

    # Log in and open the purchase form in the background, the browser only loads pages once the
    # main loop runs. Don't crash if that fails, each card submit opens the purchase page again
    def open_purchase_page():
        try:
            get_purchase_driver()
        except Exception as e:
            print("Could not open the purchase page:", e)
    threading.Thread(target=open_purchase_page, daemon=True).start()

    # root.withdraw()
    # Bind Tab to submit button
    card_number_content(root, driver_instance)
    
    root.geometry(WINDOW_SIZE)
    try:
        root.mainloop()
    finally:
        cef_browser.shutdown()
    

def card_number_content(root, driver_instance):
    global first_time
        # Card entry label
    # if not driver_instance.current_url =="https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342":
    #     driver_instance.get("https://fco.fleetcard.com.au/Merchant/Transaction/Purchase/195342")

    root.geometry(WINDOW_SIZE)

    ui.show_header(root, step=1)
    card_label = tk.Label(root, text="CARD NUMBER", font=ui.FONT_CAPTION, fg=ui.TEXT_MUTED, bg=ui.BG, anchor="w")
    card_label.pack(fill="x", padx=28, pady=(24, 4))

    # Entry field
    card_entry = tk.Entry(root, width=30, **ui.entry_options())
    card_entry.pack(fill="x", padx=28, ipady=3)
    card_entry.focus_set()
    # result = products_filler(driver_instance, "")

    card_submit = ui.Button(
        root,
        text="Submit",
        kind="primary",
        command=lambda: odo_content(driver_instance, card_entry.get(), root, [card_submit, card_label, card_entry])
    )
    card_submit.pack(fill="x", padx=28, pady=(16, 0), ipady=3)
    

    db_status_show()
    cef_browser.show(root)

    root.bind("<Tab>", lambda event: card_submit.invoke())
    root.bind("<Return>", lambda event: card_submit.invoke())

if __name__ == "__main__":
        mouse_loc = path_data['mouseMovement']
        start_socket_server(root)

        def on_close():
            global first_time
            first_time = False
            root.withdraw()

            
            for w in root.winfo_children():
                w.pack_forget() 
            card_number_content(root, driver_instance)
                    


        root.protocol("WM_DELETE_WINDOW", on_close)
        main_app()
