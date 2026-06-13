from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

from .browser import (
    BrowserSession,
    BrowserSessionError,
    get_first_linkedin_jobs_page,
    is_valid_linkedin_jobs_page_url,
)
from ..linkedin.extractor import (
    PostingPayload,
    extract_visible_results_list,
    write_results_snapshot,
)
from ..linkedin.normalizer import normalize_snapshot
from ..record.csv_export import export_reviewed_csv
from ..record.models import RunSummary
from ..record.runner import RecordJobPostings


@dataclass(frozen=True)
class BootstrapArtifacts:
    posting_count: int
    snapshot_path: Path


class BootstrapPresenter:
    def announce_start(self) -> None:
        print("Starting job review session...\n")
        print("--- Browser Connection ---\n")
        print("Connected to browser\n")
        print("Validating readiness...")

    def announce_recovery_attempt(self) -> None:
        print("\nAttempting recovery...")

    def announce_snapshot_capture(self) -> None:
        print("\n--- Job Review Session ---\n")
        print("Taking snapshot of visible results list...")

    def announce_bootstrap_success(
        self, posting_count: int, snapshot_path: Path
    ) -> None:
        print(f"\nSession ready! Found {posting_count} job postings.")
        print(f"Snapshot saved to: {snapshot_path}")

    def announce_recording_start(self) -> None:
        print("\nStarting job review...\n")

    def announce_recording_complete(self, summary: RunSummary) -> None:
        print("\nJob review session completed.")
        print(
            f"   Reviewed: {summary.reviewed_count}, Skipped: {summary.skipped_count}, Failed: {summary.failed_count}"
        )


def ensure_results_page_ready(results_page: Any, presenter: BootstrapPresenter) -> None:
    if not is_valid_linkedin_jobs_page_url(results_page.url):
        presenter.announce_recovery_attempt()
        results_page.reload()
        time.sleep(2)
        if not is_valid_linkedin_jobs_page_url(results_page.url):
            raise BrowserSessionError("Not on LinkedIn jobs page")


def capture_bootstrap_artifacts(results_page: Any) -> BootstrapArtifacts:
    extraction = extract_visible_results_list(results_page)
    if extraction.posting_count == 0:
        raise RuntimeError(
            "No job postings found on the current page. Make sure you are on linkedin.com/jobs with visible results."
        )
    snapshot = write_results_snapshot(extraction)
    return BootstrapArtifacts(
        posting_count=extraction.posting_count,
        snapshot_path=snapshot.path,
    )


def record_job_postings(results_page: Any, snapshot_path: Path) -> RunSummary:
    raw_postings: list[PostingPayload] = json.loads(
        snapshot_path.read_text(encoding="utf-8")
    )
    postings = normalize_snapshot(raw_postings)
    return RecordJobPostings(results_page, postings).run()


def execute_run(
    session: BrowserSession, presenter: BootstrapPresenter | None = None
) -> None:
    active_presenter = presenter or BootstrapPresenter()
    active_presenter.announce_start()

    results_page = get_first_linkedin_jobs_page(session.browser)
    if results_page is None:
        raise BrowserSessionError("No open linkedin.com/jobs tab found")

    try:
        ensure_results_page_ready(results_page, active_presenter)
    except BrowserSessionError:
        raise

    active_presenter.announce_snapshot_capture()
    artifacts = capture_bootstrap_artifacts(results_page)

    active_presenter.announce_bootstrap_success(
        artifacts.posting_count, artifacts.snapshot_path
    )

    active_presenter.announce_recording_start()
    summary = record_job_postings(results_page, artifacts.snapshot_path)
    active_presenter.announce_recording_complete(summary)

    try:
        export_reviewed_csv(summary)
    except Exception as error:
        print(f"Error: CSV export failed: {error}")
