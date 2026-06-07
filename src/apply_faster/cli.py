from __future__ import annotations

import argparse
from collections.abc import Sequence

from .bootstrap.browser import BrowserSessionError, attach_browser_session
from .bootstrap.run import execute_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="applai",
        description="Standalone Python rewrite of the LinkedIn Application Review CLI.",
    )
    parser.add_argument(
        "--cdp-url",
        required=True,
        help="Chrome DevTools Protocol WebSocket URL for an already running Chrome session.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        with attach_browser_session(args.cdp_url) as session:
            execute_run(session)
    except BrowserSessionError as error:
        parser.exit(status=1, message=f"{error}\n")
    except RuntimeError as error:
        parser.exit(status=1, message=f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
