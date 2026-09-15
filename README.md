# Fleet

Desktop helper for taking FleetCard payments at a Fuelzone site. It reads the current sale from Infinity POS, fills in the **Fleet Card Pay** form on the FleetCard merchant site (fco.fleetcard.com.au) in a browser at the bottom of the Fuelzone window, saves the PDF receipt, and records the card in MongoDB.

## How it works

`fleet\tkinter_fleet.py` (started by `tkinter.vbs` or `desktop_app.bat`) is the Fuelzone window. Its lower part is a Chromium browser from [cefpython3](https://github.com/cztomczak/cefpython) that Selenium drives through chromedriver, so you can watch the form being filled in and click in the page when needed. When the window starts, it logs in to the FleetCard site and opens the Fleet Card Pay form. It also listens on `127.0.0.1:9000`.

`main.bat` (runs `fleet\main.py`) asks the window to show itself. If the POS cart (`1.CD2`) has items and no payment yet, the app clicks the `mouseMovement` points in Infinity POS, then shows the window if the sale has sale notes. Otherwise nothing happens, except that the error sound plays if the window is already open.

A sale then goes like this:

1. **Card number**: swipe or type the card, then press Tab or Enter. The app opens a fresh Fleet Card Pay form and fills in the next receipt number (from `1.LR`), the card number and the products from the cart. A 2.55% merchant surcharge line is added.
2. **Odometer**: once the site returns the vehicle rego, type the odometer and press Enter or Submit. If a cart item doesn't match a FleetCard category, pick one from the dropdown first.
3. The transaction is submitted, the PDF receipt is saved to `pdfDir` and opened, and the card details are written to the `shared.fleetcard` collection in MongoDB. The window hides and goes back to the card number screen, ready for the next sale.

To cancel on the odometer screen, press **Close**. The window hides without submitting, and the next card opens a fresh form.

## Requirements

- Windows 10 or 11. Chrome isn't needed, the browser comes with cefpython3.
- Python 3.9 with tkinter, because cefpython3's last release (66.1) has no build for newer Python. `setup_venv.bat` gets it through [uv](https://docs.astral.sh/uv/), or uses Python 3.9 from the `py` launcher if uv isn't installed.
- Internet access the first time the window starts, to download chromedriver 2.40 into `fleet\drivers`
- Infinity POS on the same machine
- A FleetCard merchant login and access to the MongoDB server

cefpython3 is no longer maintained. Its browser is Chromium 66 from 2018 and Python 3.9 no longer gets security fixes, so only use the browser for the FleetCard site.

## Setup

Run the commands below in **Command Prompt** from the `fleetCard` folder.

1. Install uv (skip this if `uv --version` already works):

   ```bat
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   Then open a new Command Prompt in the `fleetCard` folder so `uv` is found.

2. Create the virtual environment and install packages. uv downloads Python 3.9 if it isn't installed:

   ```bat
   fleet\setup_venv.bat
   ```

   If `fleet\.venv` was made with another Python version, the script stops. [Stop the window](#stopping-the-window), delete the old environment and run the script again:

   ```bat
   rmdir /s /q fleet\.venv
   fleet\setup_venv.bat
   ```

3. Create `fleet\.env` from the example, then fill in the real values:

   ```bat
   copy fleet\.env.example fleet\.env
   notepad fleet\.env
   ```

   | Variable | Used for |
   | --- | --- |
   | `MONGODB_URI` | MongoDB connection string |
   | `FLEETCARD_USER` / `FLEETCARD_PASS` | FleetCard merchant site login |

   `.env` is git-ignored. Never commit it.

4. Set the file locations in `fleet\paths.json`:

   ```bat
   notepad fleet\paths.json
   ```

   Relative paths are relative to the `fleet` folder. Write paths with forward slashes (`C:/InfinityPOS/1.CD2`) or doubled backslashes (`C:\\InfinityPOS\\1.CD2`), because a single `\` isn't valid in JSON.

   | Key | Meaning |
   | --- | --- |
   | `cred` | Where `fleet.py` saves its browser session when it's run on its own, which needs Google Chrome. The window doesn't use it |
   | `pdfDir` | Folder for saved PDF receipts, e.g. `C:/Users/user/Documents/pdfs` |
   | `cd` | Infinity POS cart file, e.g. `C:/InfinityPOS/1.CD2` |
   | `lr` | Infinity POS last receipt file, e.g. `C:/InfinityPOS/1.LR` |
   | `mouseMovement` | List of `{"x": ..., "y": ...}` screen points clicked in order in the Infinity POS window when `main.bat` finds a sale. Only the first four are used |

5. The merchant ID is part of `PURCHASE_URL` in `fleet\tkinter_fleet.py`. Change it there for a different site. The window size, `WINDOW_SIZE`, is in the same file.

## Running

1. Double-click `tkinter.vbs` (or run `desktop_app.bat`). The window opens and logs in to the FleetCard site in the browser at the bottom.
2. Run `main.bat` when a fleet card sale is ready in the POS.

Start the window only once. A second copy can't listen on port 9000, so `main.bat` never shows it.

`tkinter.vbs` runs without a console window, and `main.bat` shows one briefly. Both use `fleet\.venv` when it exists. Output goes to `fleet\tkinter_fleet.log` and `fleet\main.log`, and browser warnings to `fleet\cef_debug.log`. To follow a log live:

```bat
powershell Get-Content fleet\tkinter_fleet.log -Wait
```

### Stopping the window

Closing the window, with the X or the Close button, only hides it. To stop the app, for example after changing `.env` or `paths.json`, or before deleting `fleet\.venv`, run:

```bat
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*tkinter_fleet.py*' } | ForEach-Object { taskkill /F /T /PID $_.ProcessId 2>$null }"
```

This also stops the browser and chromedriver processes the window started. Start it again with `tkinter.vbs`.

## Building executables

`tkinter_fleet.spec` hasn't been updated for cefpython3 yet (it doesn't collect cefpython3's browser files or `paths.json`), so run the window from `fleet\.venv` for now. Once the spec is updated, the build steps are:

```bat
cd fleet
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\pyinstaller.exe tkinter_fleet.spec
```

The executable is written to `fleet\dist`. Put `.env` next to the `.exe` file.

## Troubleshooting

- **"Error: can't open the FleetCard page, see tkinter_fleet.log"** Check `fleet\tkinter_fleet.log`. The first start needs internet access to download chromedriver 2.40. The page is opened again for every card, so there's no need to restart the window.
- **The window doesn't appear.** Check that the POS sale has items, no payment yet, and sale notes, and that `tkinter_fleet.py` is running. To see what's using port 9000:

  ```bat
  netstat -ano | findstr :9000
  ```

- **The footer says "Database offline".** `MONGODB_URI` in `fleet\.env` is missing or isn't a valid connection string. Fix it, then [stop](#stopping-the-window) and start the window. Until then, sales still go through on the FleetCard site but aren't recorded in MongoDB. The footer doesn't check that the server can be reached, so if sales aren't recorded while it says "Database online", look for MongoDB errors in `fleet\tkinter_fleet.log`.
- **The window won't start or the browser stays blank.** Check `fleet\tkinter_fleet.log` and `fleet\cef_debug.log`. `No module named ...` means `fleet\.venv` is missing or incomplete, so run `fleet\setup_venv.bat`. `Python version not supported` means `fleet\.venv` isn't Python 3.9. Delete it and run `fleet\setup_venv.bat` again (see Setup).
- **A card swipe went into the web page.** Click the card number or odometer box, then swipe again.
- **Anything else.** Check the log files in the `fleet` folder.

## Project layout

```
fleetCard\
├── tkinter.vbs                 hidden launcher for tkinter_fleet.py
├── desktop_app.bat, main.bat   start the window / show it for the current sale
└── fleet\
    ├── tkinter_fleet.py        the Fuelzone window (card and odometer screens)
    ├── cef_browser.py          the browser at the bottom of the window and its Selenium driver
    ├── fleet.py                FleetCard login and form-filling helpers
    ├── dropdown.py             category picker for unmatched cart items
    ├── ui_theme.py             colours, fonts and styled widgets
    ├── dbconn.py               MongoDB access (reads .env)
    ├── hex_reader.py           parses the Infinity POS cart file (1.CD2)
    ├── readLR.py               reads the next receipt number from 1.LR
    ├── mousemovement.py        clicks in the Infinity POS window
    ├── util.py                 session attach, PDF download, paths and sounds
    ├── main.py                 sends "show" to the running window
    ├── paths.json              file locations (see Setup)
    ├── requirements.txt        Python packages, installed by setup_venv.bat
    ├── setup_venv.bat          creates .venv with Python 3.9 and installs requirements.txt
    ├── .env.example            template for .env
    ├── drivers\                chromedriver 2.40, downloaded on first start
    └── *.spec                  PyInstaller build files
```
