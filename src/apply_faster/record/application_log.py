from __future__ import annotations

from dataclasses import asdict
import json

from ..log.runtime import get_runtime_logger
from ..paths import APPLICATION_ENTRIES_DIR
from .models import (
    CHECKPOINT_POSTING_COMPLETED,
    CHECKPOINT_POSTING_STARTED,
    CHECKPOINT_RUN_END,
    CHECKPOINT_RUN_START,
    ApplicationLogEntry,
    CanonicalJobIdentity,
    RunSummary,
)


class ApplicationLog:
    def __init__(self, run_id: str) -> None:
        self.current_run_id = run_id
        self.processed_urls: set[str] = set()
        self.logger = get_runtime_logger()

    def start_run(self) -> None:
        self.logger.log_checkpoint(
            self.current_run_id, None, CHECKPOINT_RUN_START, {"runStart": True}
        )

    def start_posting(self, canonical_id: CanonicalJobIdentity) -> ApplicationLogEntry:
        entry = ApplicationLogEntry(canonical_id=canonical_id)
        self.logger.log_checkpoint(
            self.current_run_id,
            canonical_id.unique_key(),
            CHECKPOINT_POSTING_STARTED,
            {"canonicalId": asdict(canonical_id)},
        )
        return entry

    def complete_posting(
        self, entry: ApplicationLogEntry, outcome: str, reason: str | None
    ) -> None:
        entry.finish(outcome)
        self.logger.log_checkpoint(
            self.current_run_id,
            entry.canonical_id.url,
            CHECKPOINT_POSTING_COMPLETED,
            {"outcome": outcome, "reason": reason},
        )
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
