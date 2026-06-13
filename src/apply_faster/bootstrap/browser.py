from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen


class BrowserSessionError(RuntimeError):
    pass


@dataclass
class BrowserSession:
    playwright: Any
    browser: Any

    def detach(self) -> None:
        self.playwright.stop()


@contextmanager
def attach_browser_session(cdp_url: str) -> Iterator[BrowserSession]:
    sync_api = import_module("playwright.sync_api")
    sync_playwright = sync_api.sync_playwright
    playwright = sync_playwright().start()
    browser: Any | None = None
    try:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=30_000)
        yield BrowserSession(playwright=playwright, browser=browser)
    except Exception as error:
        raise BrowserSessionError(
            f"Failed to attach to Chrome via CDP: {error}"
        ) from error
    finally:
        try:
            playwright.stop()
        except Exception:
            pass


_CHROME_NAMES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)

_PLATFORM_PATHS = {
    "Darwin": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "Windows": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ),
}


def find_chrome() -> str:
    for name in _CHROME_NAMES:
        path = shutil.which(name)
        if path:
            return path
    system = platform.system()
    candidates = _PLATFORM_PATHS.get(system, ())
    if isinstance(candidates, str):
        candidates = (candidates,)
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    raise BrowserSessionError(
        "Could not find Chrome or Chromium. "
        "Install Google Chrome or pass --cdp-url to connect to an existing session."
    )


def launch_chrome(
    port: int = 9222,
    url: str = "https://www.linkedin.com/jobs/collections/recommended",
    bind_all: bool = False,
) -> subprocess.Popen[bytes]:
    chrome = find_chrome()
    args = [
        chrome,
        f"--remote-debugging-port={port}",
        "--user-data-dir=/tmp/chrome-debug",
        "--profile-directory=Default",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--new-window",
        url,
    ]
    if bind_all:
        args.insert(2, "--remote-debugging-address=0.0.0.0")
    return subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def resolve_cdp_url(
    host: str = "127.0.0.1", port: int = 9222, timeout: float = 15.0
) -> str:
    endpoint = f"http://{host}:{port}/json/version"
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(endpoint, timeout=2) as resp:
                data = json.loads(resp.read())
            ws_url: str = data["webSocketDebuggerUrl"]
            return ws_url.replace("127.0.0.1", host)
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise BrowserSessionError(
        f"Chrome debugger did not respond at {host}:{port} within {timeout}s: {last_error}"
    )


@contextmanager
def launch_browser_session(
    host: str = "127.0.0.1", port: int = 9222
) -> Iterator[BrowserSession]:
    process = launch_chrome(port)
    try:
        cdp_url = resolve_cdp_url(host=host, port=port)
        with attach_browser_session(cdp_url) as session:
            yield session
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def cdp_host_from_env() -> str:
    return os.environ.get("CDP_HOST", "127.0.0.1")


def cdp_port_from_env() -> int:
    return int(os.environ.get("CDP_PORT", "9222"))


def get_all_pages(browser: Any) -> list[Any]:
    pages: list[Any] = []
    for context in browser.contexts:
        pages.extend(context.pages)
    return pages


def is_valid_linkedin_jobs_page_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc in {"linkedin.com", "www.linkedin.com"}
        and parsed.path.startswith("/jobs")
    )


def is_valid_linkedin_job_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc in {"linkedin.com", "www.linkedin.com"}
        and parsed.path.startswith("/jobs/view/")
    )


def get_first_linkedin_jobs_page(browser: Any) -> Any | None:
    for page in get_all_pages(browser):
        if is_valid_linkedin_jobs_page_url(page.url):
            return page
    return None


def open_review_tab(results_page: Any) -> Any:
    return results_page.context.new_page()
