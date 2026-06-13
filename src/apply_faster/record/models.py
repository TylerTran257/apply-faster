from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TypedDict


MANUAL_CLOSE_THRESHOLD_SECONDS = 10
SOURCE_LINKEDIN = "LinkedIn"
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
class JobPostingInput:
    source: str
    url: str | None = None
    title: str | None = None
    company: str | None = None


@dataclass
class CanonicalJobIdentity:
    url: str
    title: str | None
    company: str | None
    source: str = ""

    def unique_key(self) -> str | None:
        if not self.url or not self.url.strip():
            return None
        return f"{self.source.lower()}:{self.url.strip()}"

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
    source: str
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
            "source": result.canonical_id.source,
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
                self.skip_reasons[result.reason] = (
                    self.skip_reasons.get(result.reason, 0) + 1
                )
        elif result.status == "failed":
            self.failed_count += 1
            if result.reason:
                self.failure_reasons[result.reason] = (
                    self.failure_reasons.get(result.reason, 0) + 1
                )

    def finish(self) -> None:
        self.end_time = now_iso()

    def to_counts(self) -> dict[str, int]:
        return {
            "reviewed": self.reviewed_count,
            "skipped": self.skipped_count,
            "failed": self.failed_count,
            "total": self.reviewed_count + self.skipped_count + self.failed_count,
        }
