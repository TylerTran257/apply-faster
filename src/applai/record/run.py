from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any, TypedDict

from applai.bootstrap.browser import open_review_tab
from applai.linkedin.extractor import PostingPayload
from applai.log.runtime import get_runtime_logger
from applai.paths import APPLICATION_ENTRIES_DIR


MANUAL_CLOSE_THRESHOLD_SECONDS = 10
SKIP_REASON_DUPLICATE_URL = "duplicate-url"
SKIP_REASON_CLOSED_BEFORE_READY = "closed-before-ready"
SKIP_REASON_CLOSED_WITHIN_10_SECONDS = "closed-within-10-seconds"
CHECKPOINT_RUN_START = "run-start"
CHECKPOINT_POSTING_STARTED = "posting-started"
CHECKPOINT_POSTING_COMPLETED = "posting-completed"
CHECKPOINT_RUN_END = "run-end"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class CanonicalJobIdentity:
    url: str
    title: str | None
    company: str | None

    def unique_key(self) -> str:
        return self.url.lower().strip()

    def display_name(self) -> str:
        return f"{self.title} at {self.company}"


@dataclass
class ApplicationLogEntry:
    canonical_id: CanonicalJobIdentity
    start_time: str = field(default_factory=now_iso)
    end_time: str | None = None
    outcome: str | None = None

    def finish(self, outcome: str) -> None:
        self.end_time = now_iso()
        self.outcome = outcome


@dataclass
class JobPostingResult:
    canonical_id: CanonicalJobIdentity
    status: str
    reason: str | None = None
    timestamp: str = field(default_factory=now_iso)


class SummaryPostingIdentity(TypedDict):
    url: str
    title: str | None
    company: str | None


class SummaryPosting(TypedDict):
    canonicalId: SummaryPostingIdentity
    status: str
    reason: str | None
    timestamp: str


@dataclass
class RunSummary:
    reviewed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    postings: list[SummaryPosting] = field(default_factory=list)
    skip_reasons: dict[str, int] = field(default_factory=dict)
    failure_reasons: dict[str, int] = field(default_factory=dict)
    start_time: str = field(default_factory=now_iso)
    end_time: str | None = None

    def add_result(self, result: JobPostingResult) -> None:
        identity: SummaryPostingIdentity = {
            "url": result.canonical_id.url,
            "title": result.canonical_id.title,
            "company": result.canonical_id.company,
        }
        self.postings.append(
            {
                "canonicalId": identity,
                "status": result.status,
                "reason": result.reason,
                "timestamp": result.timestamp,
            }
        )
        if result.status == "reviewed":
            self.reviewed_count += 1
        elif result.status == "skipped":
            self.skipped_count += 1
            if result.reason:
                self.skip_reasons[result.reason] = self.skip_reasons.get(result.reason, 0) + 1
        elif result.status == "failed":
            self.failed_count += 1
            if result.reason:
                self.failure_reasons[result.reason] = self.failure_reasons.get(result.reason, 0) + 1

    def finish(self) -> None:
        self.end_time = now_iso()

    def to_counts(self) -> dict[str, int]:
        return {
            "reviewed": self.reviewed_count,
            "skipped": self.skipped_count,
            "failed": self.failed_count,
            "total": self.reviewed_count + self.skipped_count + self.failed_count,
        }

    def generate_report(self) -> str:
        self.finish()
        start = datetime.fromisoformat(self.start_time)
        end = datetime.fromisoformat(self.end_time or self.start_time)
        duration_seconds = int((end - start).total_seconds())
        minutes, seconds = divmod(duration_seconds, 60)
        duration_display = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
        lines = [
            "",
            "=" * 60,
            "           APPLICATION RUN SUMMARY",
            "=" * 60,
            "",
            f"Start Time: {self.start_time}",
            f"End Time: {self.end_time}",
            "",
            f"Duration: {duration_display}",
            "",
            "-" * 40,
            "COUNTS",
            "-" * 40,
            f"Reviewed: {self.reviewed_count}",
            f"Skipped:  {self.skipped_count}",
            f"Failed:   {self.failed_count}",
            f"Total:    {self.reviewed_count + self.skipped_count + self.failed_count}",
            "",
        ]
        if self.skip_reasons:
            lines.extend(["-" * 40, "SKIP REASONS", "-" * 40])
            for reason, count in self.skip_reasons.items():
                lines.append(f"  • {reason.replace('-', ' ').upper()}: {count}")
            lines.append("")
        if self.failure_reasons:
            lines.extend(["-" * 40, "FAILURE REASONS", "-" * 40])
            for reason, count in self.failure_reasons.items():
                lines.append(f"  • {reason}: {count}")
            lines.append("")
        lines.extend(["-" * 40, "POSTING OUTCOMES", "-" * 40])
        for posting in self.postings:
            identity = posting["canonicalId"]
            emoji = {"reviewed": "✅", "skipped": "⏭️", "failed": "❌"}.get(posting["status"], "➖")
            line = f"{emoji} {identity['title']} at {identity['company']}"
            if posting["reason"]:
                line += f" ({posting['reason']})"
            lines.append(line)
        lines.extend(["", "=" * 60])
        return "\n".join(lines)


class ApplicationLog:
    def __init__(self, run_id: str) -> None:
        self.current_run_id = run_id
        self.processed_urls: set[str] = set()
        self.entries: list[ApplicationLogEntry] = []
        self.logger = get_runtime_logger()

    def start_run(self) -> None:
        self.logger.log_checkpoint(self.current_run_id, None, CHECKPOINT_RUN_START, {"runStart": True})

    def start_posting(self, canonical_id: CanonicalJobIdentity) -> ApplicationLogEntry:
        entry = ApplicationLogEntry(canonical_id=canonical_id)
        self.logger.log_checkpoint(
            self.current_run_id,
            canonical_id.unique_key(),
            CHECKPOINT_POSTING_STARTED,
            {"canonicalId": asdict(canonical_id)},
        )
        return entry

    def complete_posting(self, entry: ApplicationLogEntry, outcome: str, reason: str | None) -> None:
        entry.finish(outcome)
        self.logger.log_checkpoint(
            self.current_run_id,
            entry.canonical_id.url,
            CHECKPOINT_POSTING_COMPLETED,
            {"outcome": outcome, "reason": reason},
        )
        self.entries.append(entry)
        self.persist_entry(entry)

    def end_run(self, summary: RunSummary) -> None:
        self.logger.log_checkpoint(
            self.current_run_id,
            None,
            CHECKPOINT_RUN_END,
            {
                "summary": {
                    "counts": summary.to_counts(),
                    "skipReasons": summary.skip_reasons,
                    "failureReasons": summary.failure_reasons,
                }
            },
        )

    def has_processed_url(self, url: str) -> bool:
        return url.lower().strip() in self.processed_urls

    def mark_as_processed(self, url: str) -> None:
        self.processed_urls.add(url.lower().strip())

    def persist_entry(self, entry: ApplicationLogEntry) -> None:
        APPLICATION_ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
        stamp = entry.start_time.replace(":", "-").replace(".", "-")
        payload = {
            "canonicalId": asdict(entry.canonical_id),
            "startTime": entry.start_time,
            "endTime": entry.end_time,
            "outcome": entry.outcome,
        }
        path = APPLICATION_ENTRIES_DIR / f"entry-{stamp}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class RecordJobPostings:
    def __init__(self, browser: Any, results_page: Any, snapshot_path: Path) -> None:
        self.browser = browser
        self.results_page = results_page
        self.snapshot_path = snapshot_path
        self.snapshot_data: list[PostingPayload] = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.summary = RunSummary()
        self.run_id = f"run-{int(time.time() * 1000)}"
        self.application_log = ApplicationLog(self.run_id)
        self.logger = get_runtime_logger()

    def capture_canonical_identity(self, posting_data: PostingPayload) -> CanonicalJobIdentity:
        return CanonicalJobIdentity(
            url=posting_data["url"],
            title=posting_data["title"],
            company=posting_data["company"],
        )

    def get_posting_outcome(self, seconds_open_after_ready: float) -> tuple[str, str | None]:
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
            self.logger.log_run("skip", "logged", f"Skipping {canonical_id.display_name()}: {reason}", details)
        elif status == "reviewed":
            self.application_log.mark_as_processed(str(posting_data["url"]))
            self.logger.log_run("review", "logged", f"Reviewed {canonical_id.display_name()}", details)
        else:
            self.logger.log_run("review", "failure", f"Failed {canonical_id.display_name()}: {reason}", details)
        self.summary.add_result(JobPostingResult(canonical_id=canonical_id, status=status, reason=reason))
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
        print(f"\n[{index + 1}/{len(self.snapshot_data)}] Processing: {canonical_id.display_name()}")
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
                    posting_data["url"],
                    wait_until="domcontentloaded",
                    timeout=300_000,
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
        report = self.summary.generate_report()
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
