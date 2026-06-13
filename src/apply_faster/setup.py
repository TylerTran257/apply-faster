from __future__ import annotations

import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

from .bootstrap.browser import BrowserSessionError, find_chrome

_CHROME_DEB_URL = (
    "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
)


def _install_chrome_linux() -> None:
    print("Downloading Google Chrome...")
    deb_path = Path(tempfile.gettempdir()) / "google-chrome-stable.deb"
    with urlopen(_CHROME_DEB_URL) as resp:
        deb_path.write_bytes(resp.read())
    print("Installing (requires sudo)...")
    subprocess.run(
        ["sudo", "dpkg", "-i", str(deb_path)],
        check=False,
    )
    subprocess.run(
        ["sudo", "apt-get", "install", "-f", "-y"],
        check=True,
    )
    deb_path.unlink(missing_ok=True)


def _install_chrome_darwin() -> None:
    if subprocess.run(["which", "brew"], capture_output=True).returncode == 0:
        print("Installing Google Chrome via Homebrew...")
        subprocess.run(["brew", "install", "--cask", "google-chrome"], check=True)
    else:
        print(
            "Homebrew not found. Install Chrome manually:\n"
            "  https://www.google.com/chrome/\n"
        )
        sys.exit(1)


def _install_playwright() -> None:
    print("Installing Playwright browser drivers...")
    subprocess.run(
        [sys.executable, "-m", "playwright", "install"],
        check=True,
    )


def run_setup() -> None:
    try:
        path = find_chrome()
        print(f"Chrome already installed at {path}")
    except BrowserSessionError:
        system = platform.system()
        if system == "Linux":
            _install_chrome_linux()
        elif system == "Darwin":
            _install_chrome_darwin()
        else:
            print(
                "Automatic Chrome install is not supported on this platform.\n"
                "Download Chrome manually: https://www.google.com/chrome/"
            )
            sys.exit(1)

        try:
            path = find_chrome()
            print(f"Chrome installed at {path}")
        except BrowserSessionError:
            print("Chrome installation failed. Install it manually and try again.")
            sys.exit(1)

    _install_playwright()
    print("\nSetup complete. Run `applai` to start.")
