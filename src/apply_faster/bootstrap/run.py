from __future__ import annotations

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
from ..linkedin.extractor import extract_visible_results_list, write_results_snapshot
from ..log.runtime import get_runtime_logger
from ..record.models import RunSummary
from ..record.runner import RecordJobPostings


@dataclass(frozen=True)
class BootstrapArtifacts:
    posting_count: int
    snapshot_path: Path


class BootstrapPresenter:
    def announce_start(self) -> None:
        print("Starting python-applai bootstrap...\n")
        print("--- Browser Connection ---\n")
        print("Connected to real browser\n")
        print("Validating readiness...")

    def announce_recovery_attempt(self) -> None:
        print("\nAttempting recovery...")

    def announce_snapshot_capture(self) -> None:
        print("\n--- Job Posting Recording ---\n")
        print("Taking snapshot of visible results list...")

    def announce_bootstrap_success(
        self, posting_count: int, snapshot_path: Path
    ) -> None:
        print(f"\nBootstrap successful! Found {posting_count} job postings.")
        print(f"Snapshot saved to: {snapshot_path}")

    def announce_recording_start(self) -> None:
        print("\nRecording job postings...\n")

    def announce_recording_complete(self, summary: RunSummary) -> None:
        print("\nJob posting recording completed.")
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
    return RecordJobPostings(results_page, snapshot_path).run()


def execute_run(
    session: BrowserSession, presenter: BootstrapPresenter | None = None
) -> None:
    logger = get_runtime_logger()
    active_presenter = presenter or BootstrapPresenter()
    active_presenter.announce_start()

    results_page = get_first_linkedin_jobs_page(session.browser)
    if results_page is None:
        raise BrowserSessionError("No open linkedin.com/jobs tab found")

    try:
        ensure_results_page_ready(results_page, active_presenter)
    except BrowserSessionError:
        logger.log_run("bootstrap", "failure", "Not on LinkedIn jobs page")
        raise

    active_presenter.announce_snapshot_capture()
    artifacts = capture_bootstrap_artifacts(results_page)

    active_presenter.announce_bootstrap_success(
        artifacts.posting_count, artifacts.snapshot_path
    )
    logger.log_run(
        "bootstrap",
        "success",
        f"Bootstrap completed successfully with {artifacts.posting_count} job postings",
        {
            "postingCount": artifacts.posting_count,
            "snapshotPath": str(artifacts.snapshot_path),
        },
    )

    active_presenter.announce_recording_start()
    summary = record_job_postings(results_page, artifacts.snapshot_path)
    active_presenter.announce_recording_complete(summary)
