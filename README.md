# Fleet

Desktop helper for taking FleetCard payments at a Fuelzone site. It reads the current sale from Infinity POS, fills in the **Fleet Card Pay** form on the FleetCard merchant site (fco.fleetcard.com.au) in a browser embedded in its own window, driven by Selenium, saves the PDF receipt, and records the card in MongoDB.

## How it works

One program, `fleet\tkinter_fleet.py` (started by `tkinter.vbs` or `desktop_app.bat`), is the Fuelzone window. The FleetCard site is shown in a browser embedded under the window's own screens: Microsoft Edge WebView2, Windows' own Edge runtime, hosted inside the window. That same browser is the one Selenium fills and submits: on start-up the window attaches chromedriver to it, saves the session to `cred.json`, logs in with the credentials from `.env` and opens the Fleet Card Pay form. The chromedriver that matches the installed runtime is fetched on first start into `fleet\drivers`. chromedriver only attaches to a browser that calls itself Chrome, so the window puts a small local "front door" in front of the browser's DevTools port that answers the version check as Chrome and passes everything else through. There is no separate Chrome window. The window listens on `127.0.0.1:9000`.

`fleet\fleet.py` holds the login and form-filling code the window uses; running it on its own (`fleet.vbs`) starts a separate Chrome the way earlier versions did. That needs Chrome installed and is not part of normal operation.

`main.bat` (runs `fleet\main.py`) tells the window to show itself, and starts it first if it is not running (up to 15 s). When the cart (`1.CD2`) has items and no payment yet, the app first clicks through the POS (the `mouseMovement` points in `paths.json`) and only then shows the window, in front, with the caret in the card box, ready for the swipe. It plays the error sound when the cart is empty, already paid, or has no sale notes; the window is shown on every `main.bat` either way. Only one window runs per machine: a second copy finds port 9000 taken and exits.

### When the POS clicks happen

The clicks at the `mouseMovement` points in `paths.json` are made only when all of this holds:

- `main.bat` (or anything else that sends `show` to port 9000) asked for the window. Starting the window, swiping a card, Close and the X never click anything.
- The POS cart file (`cd` in `paths.json`, normally `1.CD2`) has at least one item **and** no payment on it yet. An empty or already-paid cart gets the error sound instead, and no clicks.
- Windows (the POS only runs there).

They come **before** the window: it stays as it was (hidden since the last sale) until they are done. What happens, on a worker thread so the app keeps responding:

1. A window whose title contains `Infinity POS` is looked for; if found it is restored (when minimised) and brought to the front — the way Windows allows for a program that is not itself in front, so it works on every `main.bat`, not only on the first one after the window started. If no such window is found, or it will not come to the front, the log says so (`No window found with title matching: Infinity POS` / `... would not come to the front; the POS was not clicked`) and **no clicks are made**: the points are screen positions and would land on whatever else is there.
2. The first four `mouseMovement` points are clicked, in order, as absolute screen coordinates: the POS window has to sit where it was when the points were recorded, on the same screen layout and scaling. Moving the mouse into a corner of the screen during the clicks aborts the rest (pyautogui's fail-safe; the log shows `POS sale check error`).
3. After a one-second pause the sale notes are checked; a cart without them gets the error sound (the clicks have already happened).
4. Then the Fuelzone window is shown and brought to the front with the caret in the card box, ready for the swipe. That happens in every case, error sound or not — unless another `show` arrived meanwhile, in which case that one shows the window.

A sale then goes like this:

1. **Card number**: swipe or type the card, then press Tab or Enter. The app opens a fresh Fleet Card Pay form and fills in the receipt number (from `1.LR`), the card number and the products from the cart. A 2.55% merchant surcharge line is added.
2. **Odometer**: once the site returns the vehicle rego, type the odometer and press Enter or Submit. If a cart item doesn't match a FleetCard category, pick one from the dropdown first.
3. The transaction is submitted, the PDF receipt is saved to `pdfDir` and opened, and the card details are written to the `shared.fleetcard` collection in MongoDB.

## Requirements

- Windows 10 or 11 with the WebView2 Evergreen runtime. It is part of Windows 11; on Windows 10 install it from [Microsoft's WebView2 page](https://developer.microsoft.com/microsoft-edge/webview2/). Chrome is not needed
- Python 3.10-3.14 with tkinter (3.13 recommended; tick "tcl/tk and IDLE" in the Python installer). With [uv](https://docs.astral.sh/uv/) installed, `setup_venv.bat` fetches Python 3.13 itself
- Infinity POS on the same machine
- A FleetCard merchant login and access to the MongoDB server

## Setup

Run the commands below in **Command Prompt** from the `fleetCard` folder.

1. Create the virtual environment, install packages and fetch the WebView2 SDK:

   ```bat
   fleet\setup_venv.bat
   ```

   It uses `uv` when that is on the PATH and the Python launcher otherwise, needs the network (packages from PyPI, the WebView2 SDK from NuGet), and replaces an existing `fleet\.venv` when run again (one left from an older Python would keep packages the new Python cannot import).

2. Create `fleet\.env` from the example, then fill in the real values:

   ```bat
   copy fleet\.env.example fleet\.env
   notepad fleet\.env
   ```

   | Variable | Used for |
   | --- | --- |
   | `MONGODB_URI` | MongoDB connection string |
   | `FLEETCARD_USER` / `FLEETCARD_PASS` | FleetCard merchant site login |

   `.env` is git-ignored. Never commit it.

3. Set the file locations in `fleet\paths.json`:

   ```bat
   notepad fleet\paths.json
   ```

   Relative paths are relative to the `fleet` folder. Write paths with forward slashes (`C:/InfinityPOS/1.CD2`) or doubled backslashes (`C:\\InfinityPOS\\1.CD2`), because a single `\` isn't valid in JSON.

   | Key | Meaning |
   | --- | --- |
   | `cred` | Where the window saves its browser session on start-up, `cred.json` (in the `fleet` folder); the window does not read it back, `fleet.py` does |
   | `pdfDir` | Folder for saved PDF receipts, e.g. `C:/Users/user/Documents/pdfs` |
   | `cd` | Infinity POS cart file, e.g. `C:/InfinityPOS/1.CD2` |
   | `lr` | Infinity POS last receipt file, e.g. `C:/InfinityPOS/1.LR` |
   | `mouseMovement` | List of `{"x": ..., "y": ...}` screen points; the first four are clicked in the Infinity POS window when `main.bat` shows the window, before the card is swiped |

4. The merchant ID is part of `PURCHASE_URL` in `fleet\embedded_browser.py`. Change it there for a different site. The page under the screens can be scrolled with the wheel or its scrollbar; a click in it hands the keyboard straight back to the card box, so a swipe cannot land in the FleetCard form. `PAGE_TAKES_MOUSE = False` in the same file makes the page display-only (no clicking or scrolling at all) for a till where nobody should touch it.

## Running

1. Double-click `tkinter.vbs` (or `desktop_app.bat`). The window logs in to FleetCard in its own browser; the form appears under the card screen once it has. The first start on a machine also downloads the chromedriver for the installed WebView2 runtime (about 24 MB), which the log reports as `Downloaded chromedriver ...`; if `fleet\webview2` is missing (`setup_venv.bat` was not run on this machine) the window fetches the WebView2 SDK too (`Downloaded WebView2 SDK ...`). Both need the network once.
2. Run `main.bat` when a fleet card sale is ready in the POS (it starts the window if it is not running).

The launcher runs hidden and uses `fleet\.venv` when it exists. Output goes to `fleet\tkinter_fleet.log` and `fleet\main.log`. To follow a log live:

```bat
powershell Get-Content fleet\tkinter_fleet.log -Wait
```

**Close** and the window's X only hide the window (the next `main.bat` shows it again); the program keeps running. To stop it, find its process with `netstat -ano | findstr :9000` (the last column is the PID), run `taskkill /F /PID <pid>`, then start it again with `tkinter.vbs`.

## Building executables

Untested since the switch to WebView2: `tkinter_fleet.spec` bundles no data files, so the built exe would need `webview2\`, `paths.json` and the pythonnet/clr_loader hidden imports added to it first. PyInstaller isn't in `requirements.txt`, so install it first:

```bat
cd fleet
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\pyinstaller.exe tkinter_fleet.spec
.venv\Scripts\pyinstaller.exe fleet.spec
```

The executables are written to `fleet\dist`. Put `.env` next to the `.exe` files.

## Troubleshooting

- **"Error: ..." on the odometer screen right after the swipe.** The window's browser session could not be started; the banner shows the cause and `fleet\tkinter_fleet.log` has the rest (`Could not start the browser session`): usually no network for the first chromedriver download. Wrong FleetCard credentials show up as `Error: Message: ...` after about 20 s. The next card tries again; if it keeps failing, stop the window (see Running) and start it again. Two other messages appear in the same banner and are not browser problems: `Error: The entered card is invalid` (FleetCard rejected the card) and `Error: Message: ...` after about 60 s (FleetCard did not answer the card lookup; try the card again). `Error: WebView2 could not be created: ...` and `Error: No chromedriver has been published for WebView2 ... yet` do not clear on the next card: stop the window and start it again (for the second one, a newer chromedriver has to be published first; try again later).
- **`Could not record the sale in the database:` in the log.** The sale went through at FleetCard (the PDF was saved) but MongoDB did not get its record; the lines under it say why (connection, `MONGODB_URI`). The log files are UTF-8.
- **`Error: timeout` under the odometer form** about 20 s after Submit. FleetCard did not accept the transaction (or did not answer); no PDF was saved and nothing was written to MongoDB. Look at the form under the screens for FleetCard's own message, then press Submit again or Close.
- **"Another Fuelzone window is already listening"** in the log. A second copy was started while one was running; it exits and the running one carries on.
- **"The Microsoft Edge WebView2 runtime is not installed"** in the log, and no window. Install the Evergreen runtime from Microsoft's page (see Requirements) and start the window again.
- **`The WebView2 SDK ... could not be downloaded`** in the log, and no window. Run `fleet\setup_venv.bat` with the network up, then start the window again.
- **`Downloaded chromedriver ...` in the log** is normal on the first start, and again after Windows updates the WebView2 runtime to a new major version: the driver for the new version is fetched into `fleet\drivers`. It needs the network once.
- **`unrecognized Chrome version: Edg/...` in the log.** Should not happen (the window always attaches chromedriver through its front door); if it does, stop the window, start it again, and report it.
- **The window doesn't appear.** `main.bat` could not reach the window on port 9000 within 15 s (see `fleet\main.log`), and starting it failed: check `fleet\tkinter_fleet.log`. To see what's using port 9000:

  ```bat
  netstat -ano | findstr :9000
  ```

- **The wheel does not scroll the form under the screens.** Windows routes the wheel to the window under the mouse only while its setting "Scroll inactive windows when I hover over them" (Settings > Bluetooth & devices > Mouse) is on, which it is by default; the scrollbar itself can always be dragged.
- **The form under the card screen is blank or stuck.** Stop the window (see Running), then any leftover driver process, then start it again:

  ```bat
  taskkill /F /IM chromedriver_*.exe
  ```

- **Anything else.** Check the log files in the `fleet` folder.

## Checks

The scripts in `fleet\tests` run the real screens and the real embedded browser against the mock FleetCard site in `fleet\tests\mock_fleetcard`; nothing touches fco.fleetcard.com.au. Run them one at a time from **PowerShell** in the `fleet` folder, with the venv's Python (they open a window, so not from a shell that cannot bring one to the front):

```powershell
.venv\Scripts\python.exe tests\screen_check.py                     # the screens, with a stand-in browser
.venv\Scripts\python.exe tests\selenium_drives_webview2_check.py   # Selenium drives the embedded browser
.venv\Scripts\python.exe tests\app_session_check.py                # the app's own start-up and a card swipe
.venv\Scripts\python.exe tests\odometer_check.py                   # ... and the odometer, submit and a second sale
.venv\Scripts\python.exe tests\drag_check.py                       # the browser follows a real window drag
```

`$env:SCENARIO='timeout'` before `odometer_check.py` runs the sale FleetCard does not accept. `selenium_drives_webview2_check.py` measures how long a click's focus takes to come back to the window and checks that the wheel scrolls the page; `$env:PAGE_TAKES_MOUSE='0'` before it runs the display-only variant instead. Either variable stays set for the rest of the PowerShell session (`Remove-Item Env:SCENARIO` clears it). `screen_check.py` also opens a second small window, "POS stand-in", from another process, and closes it at the end. `app_harness.py` is the shared harness the app checks import, not a check itself.

## Project layout

```
fleetCard\
├── tkinter.vbs                 hidden launcher for tkinter_fleet.py (fleet.vbs: the old separate-Chrome start)
├── desktop_app.bat, main.bat   start the window / show it for the current sale
└── fleet\
    ├── fleet.py                FleetCard login and form-filling code (Selenium)
    ├── embedded_browser.py     the embedded browser (WebView2) in the window: remote debugging, keyboard stays in Tk
    ├── devtools_front_door.py  the local port chromedriver attaches to: answers the version check as Chrome, relays the rest
    ├── browser_driver.py       finds the installed WebView2 runtime and fetches the chromedriver that matches it
    ├── webview2_sdk.py         fetches the WebView2 SDK into webview2\ (run by setup_venv.bat, and by the window itself when the folder is missing)
    ├── webview2\               the WebView2 SDK, fetched, not committed
    ├── drivers\                chromedriver per runtime major, fetched on first start, not committed
    ├── tests\                  the checks (see Checks) and the mock FleetCard site
    ├── tkinter_fleet.py        the Fuelzone window (card and odometer screens)
    ├── dropdown.py             category picker for unmatched cart items
    ├── ui_theme.py             colours, fonts and styled widgets
    ├── dbconn.py               MongoDB access (reads .env)
    ├── hex_reader.py           parses the Infinity POS cart file (1.CD2)
    ├── readLR.py               reads the next receipt number from 1.LR
    ├── mousemovement.py        clicks in the Infinity POS window
    ├── util.py                 session attach, PDF download, paths and sounds
    ├── main.py                 sends "show" to the window, starting it with desktop_app.bat if it is not running
    ├── paths.json              file locations (see Setup)
    ├── setup_venv.bat          creates .venv, installs requirements.txt, fetches the WebView2 SDK
    ├── setup_venv.sh           creates .venv and installs requirements.txt on Linux, for working on fleet.py (no SDK; the window is Windows-only)
    ├── .env.example            template for .env
    ├── *.spec                  PyInstaller build files (tkinter_fleet.spec, fleet.spec; main.spec and
    │                           your_script.spec are leftovers)
    └── legacy, unused          fleetdb.py, test.py, tkactivator.py, tkinter_listen.py, utilpy, Loading_icon.gif,
                                cef_browser.py and tests\selenium_drives_cef_check.py (the cefpython3 version, cannot run now)
```
