"""Walk the real app against the mock FleetCard pages: one browser, driven by Selenium.

tkinter_fleet.py is imported as-is with the REAL embedded browser (see app_harness for
what is pointed at fixtures). The app's own worker thread attaches the runtime's
chromedriver to the window's browser, logs in with fleet.py's login(), and opens the
purchase form. A
card is swiped through the real screens - odo_content -> get_purchase_driver ->
products_filler -> trans_filler - all of it in the browser under the form, and the form
is read back through that same browser. tests/odometer_check.py carries on from here.

Safe to run next to a live window: nothing opens fco.fleetcard.com.au and the real
cred.json is not touched. Run it from PowerShell.

    fleet/.venv/Scripts/python.exe tests/app_session_check.py
"""
from app_harness import SESSION_STEPS, run

run(SESSION_STEPS)
