from __future__ import annotations

import time
from typing import Any

from ..bootstrap.browser import open_review_tab
from .models import (
    MANUAL_CLOSE_THRESHOLD_SECONDS,
    SKIP_REASON_CLOSED_BEFORE_READY,
    SKIP_REASON_CLOSED_WITHIN_10_SECONDS,
    SKIP_REASON_DUPLICATE_URL,
    CanonicalJobIdentity,
    JobPostingInput,
    JobPostingResult,
    RunSummary,
)
from .reporting import render_run_report
from .validators import validate_posting_url

FAILURE_REASON_INVALID_URL = "invalid-url"


def _live_label(posting: JobPostingInput, index: int, total: int) -> str:
    source = posting.source or "(unknown source)"
    company = posting.company or "(unknown company)"
    title = posting.title or "(unknown title)"
    label = f"[{index + 1}/{total}] {source} | {company} | {title}"
    if not posting.company or not posting.title:
        label += f" -- {posting.url or '(no url)'}"
    return label


class RecordJobPostings:
    def __init__(self, results_page: Any, postings: list[JobPostingInput]) -> None:
        self.results_page = results_page
        self.postings = postings
        self.summary = RunSummary()
        self.seen_keys: set[str] = set()

    def capture_canonical_identity(
        self, posting: JobPostingInput
    ) -> CanonicalJobIdentity:
        return CanonicalJobIdentity(
            url=posting.url or "",
            title=posting.title,
            company=posting.company,
            source=posting.source,
        )

    def get_posting_outcome(
        self, seconds_open_after_ready: float
    ) -> tuple[str, str | None]:
        if seconds_open_after_ready < MANUAL_CLOSE_THRESHOLD_SECONDS:
            return "skipped", SKIP_REASON_CLOSED_WITHIN_10_SECONDS
        return "reviewed", None

    def record_result(
        self,
        canonical_id: CanonicalJobIdentity,
        status: str,
        reason: str | None,
    ) -> None:
        self.summary.add_result(
            JobPostingResult(canonical_id=canonical_id, status=status, reason=reason)
        )

    def return_focus_to_linkedin_results(self) -> None:
        try:
            self.results_page.bring_to_front()
            time.sleep(0.5)
            print("Focus returned to LinkedIn results tab")
        except Exception as error:
            print(f"Warning: Could not return focus to results tab: {error}")

    def process_posting(self, posting: JobPostingInput, index: int) -> None:
        canonical_id = self.capture_canonical_identity(posting)
        label = _live_label(posting, index, len(self.postings))
        print(f"\n{label}")
        if not validate_posting_url(posting):
            self.record_result(canonical_id, "failed", FAILURE_REASON_INVALID_URL)
            print("[failed]")
            return
        key = canonical_id.unique_key()
        if key is not None and key in self.seen_keys:
            self.record_result(canonical_id, "skipped", SKIP_REASON_DUPLICATE_URL)
            print("[skipped] duplicate-url")
            return
        if key is not None:
            self.seen_keys.add(key)
        assert posting.url is not None
        posting_page: Any | None = None
        try:
            posting_page = open_review_tab(self.results_page)
            if posting_page is None:
                raise RuntimeError("Could not open review tab")
            active_page = posting_page
            print(
                f"Opened job tab. Close it before the page is ready or within {MANUAL_CLOSE_THRESHOLD_SECONDS}s after it is ready to skip, or close it later to mark it as reviewed."
            )
            try:
                active_page.goto(
                    posting.url, wait_until="domcontentloaded", timeout=300_000
                )
            except Exception as error:
                if active_page.is_closed():
                    self.record_result(
                        canonical_id, "skipped", SKIP_REASON_CLOSED_BEFORE_READY
                    )
                    print("[skipped] closed-before-ready")
                    return
                self.record_result(canonical_id, "failed", str(error))
                print("[failed]")
                return
            ready_at = time.time()
            active_page.wait_for_event("close", timeout=0)
            closed_at = time.time()
            status, reason = self.get_posting_outcome(closed_at - ready_at)
            self.record_result(canonical_id, status, reason)
            print(f"[{status}]")
        except Exception as error:
            if posting_page and not posting_page.is_closed():
                try:
                    posting_page.close()
                except Exception:
                    pass
            self.record_result(canonical_id, "failed", str(error))
            print("[failed]")
        finally:
            self.return_focus_to_linkedin_results()

    def run(self) -> RunSummary:
        print(f"\nProcessing {len(self.postings)} job postings...\n")
        for index, posting in enumerate(self.postings):
            self.process_posting(posting, index)
        self.summary.finish()
        report = render_run_report(self.summary)
        print(report)
        return self.summary
