from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
from typing import Any


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


def get_all_pages(browser: Any) -> list[Any]:
    pages: list[Any] = []
    for context in browser.contexts:
        pages.extend(context.pages)
    return pages


def get_first_linkedin_jobs_page(browser: Any) -> Any | None:
    for page in get_all_pages(browser):
        if "linkedin.com/jobs" in page.url:
            return page
    return None


def open_review_tab(results_page: Any) -> Any:
    return results_page.context.new_page()
