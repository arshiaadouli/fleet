import tkinter as tk
import threading
import time

def on_button_click():
    boolean_var.set(True)  # mark that first button was pressed

    # Run the string update in a thread so Tkinter doesn’t freeze
    threading.Thread(target=delayed_update, daemon=True).start()

def delayed_update():
    time.sleep(3)  # wait for 3 seconds
    string_var.set("Hello after 3 seconds!")  # update StringVar

def check_enable_second():
    """Enable second button only if both conditions are met"""
    if boolean_var.get() and string_var.get() == "Hello after 3 seconds!":
        second_button.config(state="normal")
        print("Second button enabled!")

def on_string_change(*args):

    check_enable_second()

def on_boolean_change(*args):

    check_enable_second()

root = tk.Tk()

# Variables
string_var = tk.StringVar()
boolean_var = tk.BooleanVar(value=False)

# Add listeners
string_var.trace_add("write", on_string_change)
boolean_var.trace_add("write", on_boolean_change)

# First button
first_button = tk.Button(root, text="Click Me", command=on_button_click)
first_button.pack(pady=10)

# Second button (disabled at start)
second_button = tk.Button(root, text="I appear later", state="disabled")
second_button.pack(pady=10)

# Label to show StringVar
label = tk.Label(root, textvariable=string_var, font=("Arial", 14))
label.pack(pady=20)

root.mainloop()
