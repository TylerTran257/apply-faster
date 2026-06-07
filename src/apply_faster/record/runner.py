from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import time
from typing import Any

from ..bootstrap.browser import is_valid_linkedin_job_url, open_review_tab
from ..linkedin.extractor import PostingPayload
from ..log.runtime import get_runtime_logger
from .application_log import ApplicationLog
from .models import (
    MANUAL_CLOSE_THRESHOLD_SECONDS,
    SKIP_REASON_CLOSED_BEFORE_READY,
    SKIP_REASON_CLOSED_WITHIN_10_SECONDS,
    SKIP_REASON_DUPLICATE_URL,
    ApplicationLogEntry,
    CanonicalJobIdentity,
    JobPostingResult,
    RunSummary,
)
from .reporting import render_run_report


class RecordJobPostings:
    def __init__(self, results_page: Any, snapshot_path: Path) -> None:
        self.results_page = results_page
        self.snapshot_path = snapshot_path
        self.snapshot_data: list[PostingPayload] = json.loads(
            snapshot_path.read_text(encoding="utf-8")
        )
        self.summary = RunSummary()
        self.run_id = f"run-{int(time.time() * 1000)}"
        self.application_log = ApplicationLog(self.run_id)
        self.logger = get_runtime_logger()

    def capture_canonical_identity(
        self, posting_data: PostingPayload
    ) -> CanonicalJobIdentity:
        return CanonicalJobIdentity(
            url=posting_data["url"],
            title=posting_data["title"],
            company=posting_data["company"],
        )

    def get_posting_outcome(
        self, seconds_open_after_ready: float
    ) -> tuple[str, str | None]:
        if seconds_open_after_ready < MANUAL_CLOSE_THRESHOLD_SECONDS:
            return "skipped", SKIP_REASON_CLOSED_WITHIN_10_SECONDS
        return "reviewed", None

    def finalize_posting_outcome(
        self,
        canonical_id: CanonicalJobIdentity,
        posting_data: PostingPayload,
        log_entry: ApplicationLogEntry,
        status: str,
        reason: str | None,
        duration_ms: int,
    ) -> None:
        details: dict[str, object] = {
            "canonicalId": asdict(canonical_id),
            "postingUrl": posting_data["url"],
            "runId": self.run_id,
            "durationMs": duration_ms,
        }
        if reason is not None:
            details["reason"] = reason
        if status == "skipped":
            self.logger.log_run(
                "skip",
                "logged",
                f"Skipping {canonical_id.display_name()}: {reason}",
                details,
            )
        elif status == "reviewed":
            self.application_log.mark_as_processed(str(posting_data["url"]))
            self.logger.log_run(
                "review", "logged", f"Reviewed {canonical_id.display_name()}", details
            )
        else:
            self.logger.log_run(
                "review",
                "failure",
                f"Failed {canonical_id.display_name()}: {reason}",
                details,
            )
        self.summary.add_result(
            JobPostingResult(canonical_id=canonical_id, status=status, reason=reason)
        )
        self.application_log.complete_posting(log_entry, status, reason)

    def return_focus_to_linkedin_results(self) -> None:
        try:
            self.results_page.bring_to_front()
            time.sleep(0.5)
            print("Focus returned to LinkedIn results tab")
        except Exception as error:
            print(f"Warning: Could not return focus to LinkedIn results: {error}")

    def process_posting(self, posting_data: PostingPayload, index: int) -> None:
        canonical_id = self.capture_canonical_identity(posting_data)
        print(
            f"\n[{index + 1}/{len(self.snapshot_data)}] Processing: {canonical_id.display_name()}"
        )
        log_entry = self.application_log.start_posting(canonical_id)
        if self.application_log.has_processed_url(canonical_id.url):
            self.finalize_posting_outcome(
                canonical_id,
                posting_data,
                log_entry,
                "skipped",
                SKIP_REASON_DUPLICATE_URL,
                0,
            )
            print("Skipped")
            return
        if not is_valid_linkedin_job_url(posting_data["url"]):
            self.finalize_posting_outcome(
                canonical_id,
                posting_data,
                log_entry,
                "failed",
                "invalid-job-url",
                0,
            )
            print("Failed")
            return
        posting_page: Any | None = None
        opened_at = time.time()
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
                    posting_data["url"], wait_until="domcontentloaded", timeout=300_000
                )
            except Exception as error:
                if active_page.is_closed():
                    self.finalize_posting_outcome(
                        canonical_id,
                        posting_data,
                        log_entry,
                        "skipped",
                        SKIP_REASON_CLOSED_BEFORE_READY,
                        int((time.time() - opened_at) * 1000),
                    )
                    print("Skipped")
                    return
                self.finalize_posting_outcome(
                    canonical_id,
                    posting_data,
                    log_entry,
                    "failed",
                    str(error),
                    int((time.time() - opened_at) * 1000),
                )
                print("Failed")
                return
            ready_at = time.time()
            active_page.wait_for_event("close", timeout=0)
            closed_at = time.time()
            status, reason = self.get_posting_outcome(closed_at - ready_at)
            self.finalize_posting_outcome(
                canonical_id,
                posting_data,
                log_entry,
                status,
                reason,
                int((closed_at - opened_at) * 1000),
            )
            print("Reviewed" if status == "reviewed" else "Skipped")
        except Exception as error:
            if posting_page and not posting_page.is_closed():
                try:
                    posting_page.close()
                except Exception:
                    pass
            self.finalize_posting_outcome(
                canonical_id,
                posting_data,
                log_entry,
                "failed",
                str(error),
                int((time.time() - opened_at) * 1000),
            )
            print("Failed")
        finally:
            self.return_focus_to_linkedin_results()

    def run(self) -> RunSummary:
        print(f"\nProcessing {len(self.snapshot_data)} job postings...\n")
        print(f"Run ID: {self.run_id}")
        self.application_log.start_run()
        for index, posting in enumerate(self.snapshot_data):
            self.process_posting(posting, index)
        self.application_log.end_run(self.summary)
        self.summary.finish()
        report = render_run_report(self.summary)
        print(report)
        self.logger.log_run(
            "summary",
            "completed",
            "Job posting processing completed",
            {
                "runId": self.run_id,
                "counts": self.summary.to_counts(),
                "skipReasons": self.summary.skip_reasons,
                "failureReasons": self.summary.failure_reasons,
            },
        )
        return self.summary
