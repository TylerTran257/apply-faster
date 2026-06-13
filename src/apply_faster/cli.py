from __future__ import annotations

import argparse
import subprocess
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
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Start a job review session.")
    run_parser.add_argument(
        "--cdp-url",
        default=None,
        help="Chrome DevTools Protocol WebSocket URL for an already running Chrome session. "
        "If omitted, Chrome is launched automatically.",
    )
    run_parser.add_argument(
        "--port",
        type=int,
        default=9222,
        help="Remote debugging port when auto-launching Chrome (default: 9222).",
    )

    subparsers.add_parser("setup", help="Install Chrome and Playwright browser drivers.")
    subparsers.add_parser("serve", help="Start the web UI server on port 3000.")

    parser.add_argument(
        "--cdp-url",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9222,
        help=argparse.SUPPRESS,
    )

    return parser


def _run(args: argparse.Namespace) -> int:
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
        print(f"Error: {error}")
        return 1
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1
    except KeyboardInterrupt:
        print("\nSession cancelled.")
    return 0


def _setup() -> int:
    from .setup import run_setup

    run_setup()
    return 0


def _serve() -> int:
    from .bootstrap.browser import (
        cdp_port_from_env,
        is_local_environment,
        launch_chrome,
    )
    from .web.server import start_server

    chrome_process = None
    if is_local_environment():
        port = cdp_port_from_env()
        print(f"Launching Chrome on port {port}...")
        chrome_process = launch_chrome(port=port)
        print("Chrome launched. Log in to LinkedIn, then open http://localhost:3000")

    try:
        start_server()
    finally:
        if chrome_process is not None:
            chrome_process.terminate()
            try:
                chrome_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome_process.kill()
                chrome_process.wait()

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "setup":
        return _setup()
    if args.command == "serve":
        return _serve()

    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
