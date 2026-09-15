#!/usr/bin/env bash
# Create .venv in this folder and install requirements.txt (Linux)
set -e
cd "$(dirname "$0")"

if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Warning: tkinter is missing, so the app window can't open."
    echo "On Debian/Ubuntu install it with: sudo apt install python3-tk"
fi

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo
echo "Done. Activate with: source .venv/bin/activate"
