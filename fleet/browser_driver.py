"""The chromedriver for the WebView2 runtime that draws the FleetCard site in the window.

chromedriver refuses a browser whose major version is not its own, and the browser here
is the Evergreen WebView2 runtime, which updates itself with Edge whenever Microsoft
ships a new major. So the driver cannot be pinned in the repo the way chromedriver_2.40
was for the Chromium 66 that cefpython3 bundled: the one that matches today's runtime
may be wrong next month. Instead the runtime's version is read from the registry each
start and the chromedriver of the same major is fetched from Chrome for Testing the first
time it is needed, into fleet/drivers, next to a copy for any earlier major so a runtime
that has not rolled over yet still has its driver offline.

Only the major has to match: the build numbers never will (Edge 153 is Chromium 153 with
its own build, chromedriver 153 is Chrome's), and chromedriver only checks the major.
"""
import os
import tempfile
import winreg
import zipfile
from io import BytesIO
from pathlib import Path

import requests

WEBVIEW2_DOWNLOAD_PAGE = "https://developer.microsoft.com/microsoft-edge/webview2/"
# The Evergreen runtime's Edge Update client id; its pv value is the installed version.
WEBVIEW2_CLIENT_KEY = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_INSTALL_DIR = Path(r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application")
CHROME_FOR_TESTING = "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_%d"
CHROMEDRIVER_ZIP = "https://storage.googleapis.com/chrome-for-testing-public/%s/win64/chromedriver-win64.zip"
CHROMEDRIVER_IN_ZIP = "chromedriver-win64/chromedriver.exe"


def _registry_version(hive, access):
    try:
        with winreg.OpenKey(hive, WEBVIEW2_CLIENT_KEY, 0, winreg.KEY_READ | access) as key:
            return winreg.QueryValueEx(key, "pv")[0]
    except OSError:
        return None


def _installed_folder_version():
    if not WEBVIEW2_INSTALL_DIR.is_dir():
        return None
    versions = [folder.name for folder in WEBVIEW2_INSTALL_DIR.iterdir()
                if folder.is_dir() and folder.name.replace(".", "").isdigit()]
    return max(versions, key=lambda v: tuple(int(part) for part in v.split("."))) if versions else None


def webview2_runtime_version():
    """The installed Evergreen WebView2 runtime's version, e.g. '153.0.4234.48'.

    The machine-wide install registers in the 32-bit registry view (WOW6432Node), even
    on 64-bit Windows, so that view is asked for by name rather than trusting the
    process's own bitness to land there. A per-user install registers under HKCU. The
    version-named folder under Program Files (x86) is the fallback for a machine whose
    Edge Update entries were cleaned out but whose runtime still runs.
    """
    version = (_registry_version(winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY)
               or _registry_version(winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY)
               or _registry_version(winreg.HKEY_CURRENT_USER, 0)
               or _installed_folder_version())
    if not version:
        raise RuntimeError("The Microsoft Edge WebView2 runtime is not installed; the FleetCard "
                           "form cannot be shown without it. Install the Evergreen runtime from "
                           + WEBVIEW2_DOWNLOAD_PAGE)
    return version


def chromedriver_for_runtime(drivers_dir):
    """The chromedriver.exe for the installed runtime's major, fetched on first use.

    The download goes to a temporary file in drivers_dir and is renamed into place, so a
    second copy of the app racing for the same driver never sees a half-written exe:
    each rename installs a whole file, and the later one simply replaces an equal one.
    A download the app was closed in the middle of leaves its .part behind; it is
    removed here, before the next one, since nothing else ever would.
    """
    runtime_version = webview2_runtime_version()
    major = int(runtime_version.split(".")[0])
    drivers_dir = Path(drivers_dir)
    driver = drivers_dir / ("chromedriver_%d.exe" % major)
    if driver.exists():
        return driver

    release = requests.get(CHROME_FOR_TESTING % major, timeout=30)
    if release.status_code == 404:
        raise RuntimeError("No chromedriver has been published for WebView2 %s yet (Chrome for "
                           "Testing has no LATEST_RELEASE_%d); the form cannot be driven until "
                           "one exists." % (runtime_version, major))
    release.raise_for_status()
    driver_version = release.text.strip()

    archive = requests.get(CHROMEDRIVER_ZIP % driver_version, timeout=120)
    archive.raise_for_status()
    drivers_dir.mkdir(parents=True, exist_ok=True)
    for stale in drivers_dir.glob(driver.stem + ".*.part"):
        stale.unlink(missing_ok=True)
    handle, partial = tempfile.mkstemp(prefix=driver.stem + ".", suffix=".part", dir=drivers_dir)
    try:
        with os.fdopen(handle, "wb") as out, zipfile.ZipFile(BytesIO(archive.content)) as bundle:
            out.write(bundle.read(CHROMEDRIVER_IN_ZIP))
        os.replace(partial, driver)
    except BaseException:
        Path(partial).unlink(missing_ok=True)
        raise
    print("Downloaded chromedriver %s for WebView2 %s to %s" % (driver_version, runtime_version, driver))
    return driver
