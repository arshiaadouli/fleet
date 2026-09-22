import tkinter as tk
from fleet import path_format, re_enter_products
import json
import os
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from util import attach_to_session
import ui_theme as ui

class Dropdown:
    def __init__(self):
            self.clicked = ""
            self.items=[]
            self.selected_cat={}
    def set_clicked(self, new_click):
            self.clicked = new_click

    def dropDownMenu(self, tk:tk, root, card_number, items, changed_cats=None):
        self.items=items
        self.clicked = tk.BooleanVar(value=False)
        def attach():
            current_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(current_dir, 'paths.json')
            with open(json_path, "r") as f:
                path_data = json.load(f)
            music_path = path_format(path_data['cred'])
            with open(music_path, "r") as file:
                data = json.load(file)
            # Replace with printed values
            executor_url = data['executor_url']
            session_id = data['session_id']
            
            return attach_to_session(executor_url, session_id)

        # The table belongs to the screen area, under the form and above the browser;
        # packing it straight onto root would drop it below the browser and survive the
        # move back to the card screen.
        screen = getattr(root, "_screen_frame", root)
        frame_label = ui.panel(screen)
        # No padding below: the gap down to the browser is the window's own margin, so
        # the table must not add a second one on top of it.
        frame_label.pack(fill="x", padx=16)
        frame_label.grid_columnconfigure(0, weight=1)

        for column, (title, anchor) in enumerate((('Category', "w"), ('Quantity', "e"), ('Price', "e"))):
            tk.Label(frame_label, text=title.upper(), font=ui.FONT_CAPTION, fg=ui.TEXT_MUTED, bg=ui.SURFACE_ALT,
                     anchor=anchor, padx=12, pady=3).grid(row=0, column=column, sticky="ew")

        options = ["Select", "Accessories", "Car Wash", "Engine Oil", "Ethanol Blend", "LPG", "Other", "Repair / Maintenance", "Roadside Assistance", "Super", "Tyres"]

        # Grow for the rows, but never past the screen or the window leaves the desktop
        # and the form and browser above the table go with it.
        height = root.winfo_height()
        width = root.winfo_width()
        new_height = min(height + 50 * len(items) + 50, root.winfo_screenheight() - 80)
        root.geometry(f"{width}x{new_height}")
        result = {}

        # self.selected_cat={}
        # print("ITEMS", items)
        for item in items:
            id = item['id']
            if changed_cats:
                self.selected_cat[id] = changed_cats[id]
            else:
                self.selected_cat[id] = tk.StringVar()
        for item in items:
            id = item['id']
            # selected_cat[id] = tk.StringVar()
            # print("ITEM", item)
            result[id] = item
            selected = self.selected_cat[id]
            if selected.get():
                selected.set(self.selected_cat[id].get())
            else:
                selected.set("Select")
            def on_change(*args):
                self.selected_cat[id].set(selected.get())
                
            # Trace the variable for change:
            
            selected.trace_add("write", on_change)
            qty_var = tk.StringVar(value=str(item['quantity']))
            price_var = tk.StringVar(value=str(item['price']))
            
            table_row = 2 * len(result) - 1
            frame_input = tk.Frame(frame_label, bg=ui.BORDER, height=1)
            frame_input.grid(row=table_row, column=0, columnspan=3, sticky="ew")
            dropdown = tk.OptionMenu(frame_label, selected, *options)
            ui.style_option_menu(dropdown)
            dropdown.grid(row=table_row + 1, column=0, sticky="w", padx=(10, 6), pady=3)
            entry_qty = tk.Entry(frame_label, textvariable=qty_var, state="disabled", **ui.readonly_cell_options())
            entry_qty.grid(row=table_row + 1, column=1, sticky="e", padx=(6, 12))
            entry_price = tk.Entry(frame_label, textvariable=price_var, state="disabled", **ui.readonly_cell_options())
            entry_price.grid(row=table_row + 1, column=2, sticky="e", padx=(6, 12))
            ui.mark_choice(dropdown, selected)
            selected.trace_add("write", lambda *args, menubutton=dropdown, variable=selected: ui.mark_choice(menubutton, variable))
            
        
    def set_items(self):
        validated_items = self.items
        if validated_items==[]:
             return False
        # print("SELECTED_CATS", self.selected_cat)
        for i in range(len(validated_items)):
            # print(i)
            id = validated_items[i]['id']
            correct_cat = self.selected_cat[id].get()
            validated_items[i]['description'] =correct_cat
        return validated_items
                   

            
            
            
            

        
            
            


# import tkinter as tk
# from fleet import path_format, re_enter_products
# import json
# import os
# from selenium.webdriver.remote.webdriver import WebDriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from util import attach_to_session

# class Dropdown:
#     def __init__(self):
#             self.clicked = ""
#             self.items=[]
#     def set_clicked(self, new_click):
#             self.clicked = new_click

#     def dropDownMenu(self, tk:tk, root, card_number, items):
#         self.items=items
#         self.clicked = tk.BooleanVar(value=False)
#         def attach():
#             current_dir = os.path.dirname(os.path.abspath(__file__))
#             json_path = os.path.join(current_dir, 'paths.json')
#             with open(json_path, "r") as f:
#                 path_data = json.load(f)
#             music_path = path_format(path_data['cred'])
#             with open(music_path, "r") as file:
#                 data = json.load(file)
#             # Replace with printed values
#             executor_url = data['executor_url']
#             session_id = data['session_id']
            
#             return attach_to_session(executor_url, session_id)

#         frame_label = tk.Frame(root)
#         frame_label.pack(fill="both", expand=True)


#         tk.Label(frame_label, text='Category').pack(padx=40, side="left")
#         tk.Label(frame_label, text='Quantity').pack(padx=40, side="left")
#         tk.Label(frame_label, text='Price').pack(padx=50, side="left")

#         options = ["Accessories", "Car Wash", "Engine Oil", "Ethanol Blend", "LPG", "Other", "Repair / Maintenance", "Roadside Assistance", "Super", "Tyres"]
#         def submit_command(invalid_items, selected_cats):
#             self.clicked.set(True)
#             validated_items = invalid_items
#             # print("SELECTED_CATS", list(selected_cats))
#             for i in range(len(validated_items)):
#                 # print(i)
#                 id = validated_items[i]['id']
#                 correct_cat = selected_cats[i][1].get()
#                 validated_items[i]['description'] =correct_cat
                
#             # print("INVALID_ITEMS", invalid_items)
#             status = re_enter_products(attach(), card_number, validated_items)
        
#         height = root.winfo_height()
#         width = root.winfo_width()
#         new_height= height+ 50*len(items)+50
#         root.geometry(f"{width}x{new_height}")
#         result = {}
#         selected_cat={}
#         for item in items:
#             id = item['id']
#             selected_cat[id] = tk.StringVar()
#         for item in items:
#             id = item['id']
#             # selected_cat[id] = tk.StringVar()
#             # print("ITEM", item)
#             result[id] = item
#             selected = selected_cat[id]
#             selected.set("Accessories")
#             def on_change(*args):
#                 selected_cat[id].set(selected.get())

#             # Trace the variable for changes
#             selected.trace_add("write", on_change)
#             qty_var = tk.StringVar(value=str(item['quantity']))
#             price_var = tk.StringVar(value=str(item['price']))

#             frame_input = tk.Frame(root)
#             dropdown = tk.OptionMenu(frame_input, selected, *options)
#             dropdown.pack(padx=10, side="left")
#             entry_qty = tk.Entry(frame_input, textvariable=qty_var, state="disabled")
#             entry_qty.pack(padx=10, side="left")
#             entry_price = tk.Entry(frame_input, textvariable=price_var, state="disabled")
#             entry_price.pack(padx=10, side="left")
#             frame_input.pack(fill="both", expand=True)
            

#         tk.Button(root, command=lambda:submit_command(items, list(selected_cat.items())), text="submit", width=15, height=2).pack(padx=20, pady=20)
    
