from __future__ import annotations

import argparse
from collections.abc import Sequence

from .bootstrap.browser import (
    BrowserSessionError,
    attach_browser_session,
    get_all_pages,
    get_first_linkedin_jobs_page,
    launch_browser_session,
)
from .bootstrap.run import execute_run

LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs/collections/recommended/"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="applai",
        description="Standalone Python rewrite of the LinkedIn Application Review CLI.",
    )
    parser.add_argument(
        "--cdp-url",
        default=None,
        help="Chrome DevTools Protocol WebSocket URL for an already running Chrome session. "
        "If omitted, Chrome is launched automatically.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9222,
        help="Remote debugging port when auto-launching Chrome (default: 9222).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.cdp_url:
            with attach_browser_session(args.cdp_url) as session:
                execute_run(session)
        else:
            with launch_browser_session(args.port) as session:
                input(
                    "\nChrome launched. Log in to LinkedIn, "
                    "then press Enter to continue..."
                )
                if not get_first_linkedin_jobs_page(session.browser):
                    pages = get_all_pages(session.browser)
                    if pages:
                        pages[0].goto(LINKEDIN_JOBS_URL, wait_until="domcontentloaded")
                execute_run(session)
    except BrowserSessionError as error:
        parser.exit(status=1, message=f"{error}\n")
    except RuntimeError as error:
        parser.exit(status=1, message=f"{error}\n")
    except KeyboardInterrupt:
        print("\nSession cancelled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
