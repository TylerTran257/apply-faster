from __future__ import annotations

import time

from applai.bootstrap.browser import BrowserSession, BrowserSessionError, get_first_linkedin_jobs_page
from applai.linkedin.extractor import extract_visible_results_list
from applai.log.runtime import get_runtime_logger
from applai.record.run import RecordJobPostings


def execute_run(session: BrowserSession) -> None:
    logger = get_runtime_logger()
    print("Starting python-applai bootstrap...\n")
    print("--- Browser Connection ---\n")
    print("Connected to real browser\n")
    print("Validating readiness...")

    results_page = get_first_linkedin_jobs_page(session.browser)
    if results_page is None:
        raise BrowserSessionError("No open linkedin.com/jobs tab found")

    if not results_page.url.startswith("http"):
        print("\nAttempting recovery...")
        results_page.reload()
        time.sleep(2)
        if "linkedin.com/jobs" not in results_page.url:
            logger.log_run("bootstrap", "failure", "Not on LinkedIn jobs page")
            raise BrowserSessionError("Not on LinkedIn jobs page")

    print("\n--- Job Posting Recording ---\n")
    print("Taking snapshot of visible results list...")
    snapshot = extract_visible_results_list(results_page)
    if snapshot.posting_count == 0:
        raise RuntimeError(
            "No job postings found on the current page. Make sure you are on linkedin.com/jobs with visible results."
        )

    print(f"\nBootstrap successful! Found {snapshot.posting_count} job postings.")
    print(f"Snapshot saved to: {snapshot.path}")
    logger.log_run(
        "bootstrap",
        "success",
        f"Bootstrap completed successfully with {snapshot.posting_count} job postings",
        {"postingCount": snapshot.posting_count, "snapshotPath": str(snapshot.path)},
    )

    print("\nRecording job postings...\n")
    summary = RecordJobPostings(session.browser, results_page, snapshot.path).run()
    print("\nJob posting recording completed.")
    print(
        f"   Reviewed: {summary.reviewed_count}, Skipped: {summary.skipped_count}, Failed: {summary.failed_count}"
    )
