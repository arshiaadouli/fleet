from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from httpcore import TimeoutException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import asyncio
import undetected_chromedriver as uc
from time import sleep
from selenium.webdriver.support.ui import Select
from dbconn import FleetCardVal
from hex_reader import xml_to_json
# from selenium import webdriver
from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import json
import queue 
import threading
from selenium.webdriver.chrome.service import Service
from readLR import get_receipt_no
from tkinter import ttk
# Choose your own port

headless=False
valid_options=[]
invalid_options=[]
# If you already fixed your path with raw string
import os
from util import PATHS_FILE, path_format
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = PATHS_FILE  # C:\paths.json on Windows when it exists, otherwise fleet/paths.json
json_path = os.path.join(current_dir, 'paths.json')
with open(file_path, "r") as f:
    path_data = json.load(f)
def change_headless():
    global headless
    headless = not headless
    return headless

def login(username, password, driver):
    wait = WebDriverWait(driver, 20)
    sleep(2)
    # Wait until the element is visible and enabled
    username_field = driver.find_element(By.XPATH, "(//form//input)[4]")
    password_field = driver.find_element(By.XPATH, "(//form//input)[5]")

    # username_field.clear()
    username_field.send_keys(username)

    # password_field.clear()
    password_field.send_keys(password)
    # submit = driver.find_element(By.XPATH, "(//form//input)[6]")
    password_field.send_keys(Keys.RETURN)
    sleep(3)



   
def odo_submit(driver, odo):        
        odo_input = driver.find_element(By.XPATH, "(//table//table//input)[12]")
        odo_input.clear()
        sleep(0.2)
        odo_input.send_keys(odo)

        check_input = driver.find_element(By.XPATH, "(//table//table//input)[10]")
        if not check_input.is_selected():
            check_input.click()
        

def form_submit(driver):
    # (//input[@type='submit'])[2]
    old_url = driver.current_url
    submit_input = driver.find_element(By.XPATH, "(//input[@type='submit'])[2]")
    submit_input.click()
    current_url = driver.current_url

    
    WebDriverWait(driver, 20).until(EC.url_changes(old_url))
    current_url = driver.current_url

    if current_url.startswith("https://fco.fleetcard.com.au/Merchant/Transaction/Purchase"):
        return "error"  
    
    else:
        id = current_url.split("uni_txn_id=")[1]
        pdf_icon = driver.find_element(By.XPATH, "(//table)[2]//tbody//tr[1]//a")
        pdf_link = pdf_icon.get_attribute("href")
        # pdf_link.click()
        from util import save_pdf_from_url
        print("PDFLINK", pdf_link)
        try:
            # email_msg= driver.find_element(By.CLASS_NAME, "perrornotification")
            # if email_msg.text.startswith("failed"):
            # save_pdf_from_url(pdf_link, path_format(path_data['pdfDir']), f'{id}.pdf')
            save_pdf_from_url(pdf_link, path_format(path_data['pdfDir']), f'{id}.pdf')
            print("pdf has been saved")
            import webbrowser

            webbrowser.open(f"{path_format(path_data['pdfDir'])}/{id}.pdf")
        except Exception as e:
            print(e)
            
        return "success"
            


def make_driver_headless(driver, headless=True):
    if driver is None:
        print("Driver is not running!")
        return
    

    # Quit current driver
    driver.quit()
    new_driver = None
    # Restart driver in headless mode
    if headless:
        new_driver = driver_start_up()
    else:
        new_driver = driver_start_up(False)
        
    # driver=driver_start_up(headless)
    driver_login(new_driver)
    input("enter something")
        
def get_today_date():
        # Get today's date
    today = datetime.today()

    # Format as yyyy:mm:dd
    formatted_date = today.strftime("%d/%m/%Y")

    return formatted_date


def driver_start_up(headless=True):
    # global headless
    chrome_options = Options()
    # if headless==True:
        # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--log-level=3")
    # chrome_options.add_argument("--headless=new")  # run Chrome in headless mode
    # chrome_options.add_argument("--disable-gpu")   # optional, recommended for headless
    chrome_options.add_argument("--window-size=640,1000")  # ensures full layout
    # chrome_options.add_argument("--no-sandbox")    # for Linux compatibility
    chrome_options.add_argument("--disable-gpu")  # Disable GPU hardware acceleration
    chrome_options.add_argument("--no-sandbox")   # Disable the sandbox (use cautiously)
    chrome_options.add_argument("--disable-software-rasterizer")  # Disable software rasterizer
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("detach", True)
    from time import sleep
    # chrome_options.add_argument("--headless")  # optional
    service = Service(port=9595)
    driver = webdriver.Chrome(options=chrome_options, service=service)

    return driver
    
from pathlib import Path
def get_fleetcard_login():
    # .env is loaded when dbconn is imported
    fleetcard_user = os.getenv("FLEETCARD_USER")
    fleetcard_pass = os.getenv("FLEETCARD_PASS")
    if not fleetcard_user or not fleetcard_pass:
        raise RuntimeError("FLEETCARD_USER and FLEETCARD_PASS must be set in .env (see .env.example)")
    return fleetcard_user, fleetcard_pass

def driver_login(driver):
    fleetcard_user, fleetcard_pass = get_fleetcard_login()
    driver.get("https://fco.fleetcard.com.au/")
    print("Session ID:", driver.session_id)
    session_data = {
    "session_id": driver.session_id,
    "executor_url": "http://localhost:9595"
    }
    music_path = Path(path_format(path_data['cred']))
        # Save to JSON file
    music_path.write_text(json.dumps(session_data, indent=4))
    # driver.execute_script("document.body.style.zoom='30%'")
    
    login(fleetcard_user, fleetcard_pass, driver)
    
def driver_main():
    q = queue.Queue()

    def start_driver():
        driver=driver_start_up()
        driver_login(driver)
        # no sleep, just exit thread → browser remains open (detach=True)


    print("Driver started and logged in. Session info saved to session.json")

def re_enter_products(driver, card_number, items):
    # new_cats = []
    # new_cats.append(k[1].get() for k in items)
    if not items:
        return True
    if not invalid_options:
        return True
    print("ITEMS", items)
    # print("CATS", new_cats)
    check_input = driver.find_element(By.XPATH, "(//table//table//input)[10]")
    if not check_input.is_selected():
        check_input.click()
    for i in range(len(items)):
        
        if not items[i]['description'] == 'Select': 
            select_element = driver.find_element(By.XPATH, f"//table[@id='ProductTable']//tr[{items[i]['id']}]//select")
            select = Select(select_element)
            select.select_by_visible_text(items[i]['description'])
            
            qty = driver.find_element(By.XPATH, f"(//table[@id='ProductTable']//tr[{items[i]['id']}]//input)[2]")
            qty.clear()
            qty.send_keys(items[i]['quantity'])
            amount = driver.find_element(By.XPATH, f"(//table[@id='ProductTable']//tr[{items[i]['id']}]//input)[3]")
            amount.clear()
            amount.send_keys(items[i]['price'])
            try:
                valid_options.append([card_number, items[i]['description'],  items[i]['subaftertax']])
            except:
                valid_options.append([card_number, items[i]['description'],  items[i]['subaftertax']])
                
        else:
            return False
        
    return True
        


    

def get_exp_month_year(driver):
    exp_month = driver.find_element(By.XPATH, "((//table//table)[5]//tr//input)[1]")
    exp_year = driver.find_element(By.XPATH, "((//table//table)[5]//tr//input)[2]")
    return [exp_month.get_attribute("value"), exp_year.get_attribute("value")]


def products_filler(driver, card_number):
    global invalid_options
    invalid_options=[]
    tab_btn = driver.find_element(By.XPATH, "(//a[contains(@class, 'tab-btn')])[5]")
    tab_btn.click()
    
    # print("card_number", card_number)

    add_item_btn = driver.find_element(By.XPATH, "(//fieldset//table//input)[1]")
    sleep(2.5)
    cart_products = xml_to_json(path_format(path_data['cd']))
    print("cart products", cart_products)
    for _ in range(len(cart_products)+1):
        add_item_btn.click()
    
    
    products = driver.find_elements(By.XPATH, "//tr[contains(@class, 'editorRows') ]")
    
    total_cost = 0
    for item in cart_products:
        total_cost += float(item['subaftertax'])
    print('total cost', total_cost)
    product_form_helper = [{'description': 'Merchant Surcharge', 'quantity':'1', 'subaftertax':str(round(2.55 * total_cost / 100, 2))}]
    
    for item in cart_products:
        product_form_helper.append(item)
        
    print("product form helper", product_form_helper)
    # fleet_card = FleetCardVal()
    options = ["Accessories", "Car Wash", "Engine Oil", "Ethanol Blend", "LPG", "Other", "Repair / Maintenance", "Roadside Assistance", "Super", "Tyres"]

    # valid_options=[]
    for i in range(len(product_form_helper)):
        print("PRODUCTS FROM HELPER", product_form_helper)
        try:

            tr_index=i+1
            select_element = driver.find_element(By.XPATH, f"//table[@id='ProductTable']//tr[{tr_index}]//select")
            select = Select(select_element)
            select.select_by_visible_text(product_form_helper[i]['description'])
            
            qty = driver.find_element(By.XPATH, f"(//table[@id='ProductTable']//tr[{tr_index}]//input)[2]")
            qty.send_keys(product_form_helper[i]['quantity'])
            amount = driver.find_element(By.XPATH, f"(//table[@id='ProductTable']//tr[{tr_index}]//input)[3]")
            amount.send_keys(product_form_helper[i]['subaftertax'])
            
            # fleet_card.add_fleet_card(card_number, product_form_helper[i]['description'])
            valid_options.append([card_number, product_form_helper[i]['description'], product_form_helper[i]['subaftertax']])
        except:
            invalid_options.append({"id":i+1, 
                                    "description": product_form_helper[i]['description'], 
                                    "price":product_form_helper[i]['subaftertax'], 
                                    "quantity":product_form_helper[i]['quantity']
                                })
            
    if invalid_options:
        return ["404", invalid_options]         
    return ["200", valid_options]
        
    


def trans_filler(driver, card_number):
    sales_number = get_receipt_no(path_format(path_data['lr']))


    sales_number_input = driver.find_element(By.XPATH, "(//table//table//input)[1]")
    sales_number_input.send_keys(str(sales_number))
    
    card_number_input = driver.find_element(By.XPATH, "(//table//table//input)[5]")
    card_number_input.send_keys(card_number)
    
    check_input = driver.find_element(By.XPATH, "(//table//table//input)[10]")
    if not check_input.is_selected():
        check_input.click()

    
    # sleep(20)
    
    
    
    
    alerts = driver.find_elements(
    By.XPATH, "(//table[1]//tr[5]//span[1])[4]"
    )
    
    error_message=False
    input_text=False
    msg= ''
    wait = WebDriverWait(driver, 60)

    try:
        element = WebDriverWait(driver, 60).until(
            lambda d: next(
                (el for el in d.find_elements(By.XPATH, "(//table[1]//tr[5]//span)[4]") if el.text != ''),
                None
            ) or next(
                (el for el in d.find_elements(By.ID, "Rego") if el.get_attribute("value")),
                None
            )
        )
        if element:
            if element.tag_name == "span":
                print("Error message appeared")
                msg = "Error: The entered card is invalid"
            elif element.tag_name == "input":
                print("Input has value:", element.get_attribute("value"))
                print("The card is valid")
                msg = f"Rego is: {element.get_attribute('value')}"
        else:
            print("No element found with the desired condition within 60 seconds")

    except TimeoutException:
        if not check_input.is_selected():
            check_input.click()

    return msg

if __name__ == "__main__":

    # driver=driver_start_up()
    # driver_login(driver)
    # input()

        get_fleetcard_login()  # stop before opening Chrome if the login is missing from .env
        driver=driver_start_up()
        driver_login(driver)
        input("enter something")
        





















