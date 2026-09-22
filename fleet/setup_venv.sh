#!/usr/bin/env bash
# Create .venv in this folder and install requirements.txt (Linux)
# The embedded browser is Windows-only (WebView2), so the window does not run here;
# this script stays for working on fleet.py, which drives a browser of its own.
set -e
cd "$(dirname "$0")"

# The same range as requirements.txt and setup_venv.bat (pythonnet's), checked here so
# the install does not stop at pythonnet with nothing to say which Python was wrong.
if ! python3 -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 14) else 1)' 2>/dev/null; then
    echo "Python 3.10-3.14 is needed; python3 here is: $(python3 --version 2>&1)"
    exit 1
fi
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Warning: tkinter is missing, so the app window can't open."
    echo "On Debian/Ubuntu install it with: sudo apt install python3-tk"
fi

python3 -m venv --clear .venv
.venv/bin/pip install -r requirements.txt
echo
echo "Done. Activate with: source .venv/bin/activate"
