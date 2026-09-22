"""The WebView2 SDK the window hosts the browser with, fetched into fleet/webview2.

The SDK is two files: the .NET assembly embedded_browser drives the browser through and
the native loader it finds the runtime with. They are binaries, so they stay out of git
and are fetched from NuGet by setup_venv.bat (and by embedded_browser itself if they
are missing), with the version pinned here so every install hosts the same SDK. The
browser itself is not fetched: it is Windows' own Evergreen WebView2 runtime, which
updates with Edge, and browser_driver fetches the chromedriver that matches it.

    python webview2_sdk.py
"""
import os
import tempfile
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

SDK_VERSION = "1.0.2903.40"
PACKAGE_URL = ("https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/%s/"
               "microsoft.web.webview2.%s.nupkg" % (SDK_VERSION, SDK_VERSION))
SDK_DIR = Path(__file__).resolve().parent / "webview2"
# What is taken out of the package (a zip), and the name it gets in sdk_dir.
SDK_FILES = {"lib/net462/Microsoft.Web.WebView2.Core.dll": "Microsoft.Web.WebView2.Core.dll",
             "runtimes/win-x64/native/WebView2Loader.dll": "WebView2Loader.dll",
             "LICENSE.txt": "LICENSE.txt"}
REQUIRED = ("Microsoft.Web.WebView2.Core.dll", "WebView2Loader.dll")


def ensure_sdk(sdk_dir=SDK_DIR):
    """Fetch the SDK into sdk_dir unless its two DLLs are already there.

    Each file lands through a temporary file and a rename, so a window starting while
    the setup script is still writing never loads half a DLL; a .part left by a fetch
    that was cut short is removed before the next one. Offline, the error names what is
    missing and where to get it, since this runs at the window's first import.
    """
    sdk_dir = Path(sdk_dir)
    if all((sdk_dir / name).exists() for name in REQUIRED):
        return
    try:
        with urllib.request.urlopen(PACKAGE_URL, timeout=120) as response:
            package = response.read()
    except OSError as error:
        raise RuntimeError("The WebView2 SDK %s is not in %s and could not be downloaded (%s); run "
                           "fleet\\setup_venv.bat on a connected machine" % (SDK_VERSION, sdk_dir, error)) from error
    sdk_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(package)) as bundle:
        for member, name in SDK_FILES.items():
            for stale in sdk_dir.glob(name + ".*.part"):
                stale.unlink(missing_ok=True)
            handle, partial = tempfile.mkstemp(prefix=name + ".", suffix=".part", dir=sdk_dir)
            try:
                with os.fdopen(handle, "wb") as out:
                    out.write(bundle.read(member))
                os.replace(partial, sdk_dir / name)
            except BaseException:
                Path(partial).unlink(missing_ok=True)
                raise
    print("Downloaded WebView2 SDK %s to %s" % (SDK_VERSION, sdk_dir))


if __name__ == "__main__":
    ensure_sdk()
