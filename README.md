# Fleet

Desktop helper for taking FleetCard payments at a Fuelzone site. It reads the current sale from Infinity POS, fills in the **Fleet Card Pay** form on the FleetCard merchant site (fco.fleetcard.com.au) using a Selenium-controlled Chrome, saves the PDF receipt, and records the card in MongoDB.

## How it works

Two programs run side by side:

| Program | Started by | What it does |
| --- | --- | --- |
| `fleet/fleet.py` | `fleet.vbs` | Opens Chrome (chromedriver on port `9595`), logs in to the FleetCard site and saves the browser session to `cred.json`. Leave it running. |
| `fleet/tkinter_fleet.py` | `tkinter.vbs` or `desktop_app.bat` | The Fuelzone window. Attaches to the Chrome session from `cred.json` and listens on `127.0.0.1:9000`. |

`main.bat` (runs `fleet/main.py`) tells the window to show itself. The window only appears when the POS cart (`1.CD2`) has items, has no payment yet, and has sale notes. Otherwise it plays the error sound.

A sale then goes like this:

1. **Card number**: swipe or type the card, then press Tab or Enter. The app opens a fresh Fleet Card Pay form and fills in the receipt number (from `1.LR`), the card number and the products from the cart. A 2.55% merchant surcharge line is added.
2. **Odometer**: once the site returns the vehicle rego, type the odometer and press Enter or Submit. If a cart item doesn't match a FleetCard category, pick one from the dropdown first.
3. The transaction is submitted, the PDF receipt is saved to `pdfDir` and opened, and the card details are written to the `shared.fleetcard` collection in MongoDB.

## Requirements

- Windows with Google Chrome installed (Selenium downloads a matching chromedriver automatically)
- Python 3.12+ with tkinter (tick "tcl/tk and IDLE" in the Python installer)
- Infinity POS on the same machine
- A FleetCard merchant login and access to the MongoDB server

## Setup

1. Create the virtual environment and install packages:

   ```bat
   fleet\setup_venv.bat
   ```

   On Linux use `fleet/setup_venv.sh` (POS clicks and alert sounds are skipped there).

2. Create `fleet/.env` from the example and fill in the real values:

   ```bat
   copy fleet\.env.example fleet\.env
   ```

   | Variable | Used for |
   | --- | --- |
   | `MONGODB_URI` | MongoDB connection string |
   | `FLEETCARD_USER` / `FLEETCARD_PASS` | FleetCard merchant site login |

   `.env` is git-ignored. Never commit it.

3. Set the file locations in `paths.json`. The app uses `C:\paths.json` when it exists, otherwise `fleet/paths.json`.

   | Key | Meaning |
   | --- | --- |
   | `cred` | Where `fleet.py` saves the browser session (`cred.json`) |
   | `pdfDir` | Folder for saved PDF receipts |
   | `cd` | Infinity POS cart file, e.g. `C:\InfinityPOS\1.CD2` |
   | `lr` | Infinity POS last receipt file, e.g. `C:\InfinityPOS\1.LR` |
   | `mouseMovement` | List of `{"x": ..., "y": ...}` screen points clicked in the Infinity POS window before the form opens |

4. The merchant ID is part of `PURCHASE_URL` in `fleet/tkinter_fleet.py`. Change it there for a different site.

## Running

1. Start `fleet.vbs` and wait for Chrome to finish logging in.
2. Start `tkinter.vbs` (or `desktop_app.bat`).
3. Run `main.bat` when a fleet card sale is ready in the POS.

Both scripts run hidden and use `fleet/.venv` when it exists. Output goes to `fleet/fleet.log`, `fleet/tkinter_fleet.log` and `fleet/main.log`.

## Building executables

PyInstaller isn't in `requirements.txt`, so install it first:

```bat
cd fleet
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller tkinter_fleet.spec
.venv\Scripts\pyinstaller fleet.spec
```

The executables are written to `fleet/dist`. Put `.env` next to the `.exe` files.

## Troubleshooting

- **"Error: can't reach the FleetCard browser, is fleet.py running?"** Start `fleet.vbs`. If you restart it, the window picks up the new browser on the next card, so there's no need to restart the window.
- **The window doesn't appear.** Check that the POS sale has items, no payment yet, and sale notes, and that `tkinter_fleet.py` is running (nothing else may be using port 9000).
- **Chrome won't start.** Another program may be using port 9595. Close old `chromedriver.exe` processes and start `fleet.vbs` again.
- **Anything else.** Check the log files in `fleet/`.

## Project layout

```
fleetCard/
├── fleet.vbs, tkinter.vbs      hidden launchers for fleet.py and tkinter_fleet.py
├── desktop_app.bat, main.bat   start the window / show it for the current sale
└── fleet/
    ├── fleet.py                Chrome start-up, FleetCard login and form-filling helpers
    ├── tkinter_fleet.py        the Fuelzone window (card and odometer screens)
    ├── dropdown.py             category picker for unmatched cart items
    ├── ui_theme.py             colours, fonts and styled widgets
    ├── dbconn.py               MongoDB access (reads .env)
    ├── hex_reader.py           parses the Infinity POS cart file (1.CD2)
    ├── readLR.py               reads the next receipt number from 1.LR
    ├── mousemovement.py        clicks in the Infinity POS window
    ├── util.py                 session attach, PDF download, paths and sounds
    ├── main.py                 sends "show" to the running window
    ├── paths.json              file locations (see Setup)
    ├── .env.example            template for .env
    └── *.spec                  PyInstaller build files
```
