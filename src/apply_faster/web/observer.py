from __future__ import annotations

import queue
from typing import Any

from ..record.models import JobPostingInput, RunSummary
from .state import SessionState


def _posting_dict(posting: JobPostingInput) -> dict[str, Any]:
    return {
        "source": posting.source,
        "url": posting.url,
        "title": posting.title,
        "company": posting.company,
    }


def _summary_dict(summary: RunSummary) -> dict[str, Any]:
    return {
        "reviewed_count": summary.reviewed_count,
        "skipped_count": summary.skipped_count,
        "failed_count": summary.failed_count,
        "total": summary.reviewed_count + summary.skipped_count + summary.failed_count,
        "start_time": summary.start_time,
        "end_time": summary.end_time,
        "skip_reasons": dict(summary.skip_reasons),
        "failure_reasons": dict(summary.failure_reasons),
        "postings": list(summary.postings),
    }


class WebObserver:
    def __init__(self, state: SessionState, event_queue: queue.Queue[dict[str, Any]]) -> None:
        self._state = state
        self._queue = event_queue

    def on_session_start(self, total: int) -> None:
        self._state.set_running(total)
        self._queue.put({"type": "session_start", "total": total})

    def on_job_start(self, index: int, total: int, posting: JobPostingInput) -> None:
        info = _posting_dict(posting)
        self._state.set_current_job(index, info)
        self._queue.put({
            "type": "job_start",
            "index": index,
            "total": total,
            "posting": info,
        })

    def on_job_complete(
        self, index: int, total: int, posting: JobPostingInput, status: str, reason: str | None
    ) -> None:
        info = _posting_dict(posting)
        completed = {**info, "status": status, "reason": reason}
        self._state.add_completed(completed)
        self._queue.put({
            "type": "job_complete",
            "index": index,
            "total": total,
            "posting": info,
            "status": status,
            "reason": reason,
        })

    def on_session_complete(self, summary: RunSummary) -> None:
        summary_data = _summary_dict(summary)
        self._state.set_complete(summary_data)
        self._queue.put({"type": "session_complete", "summary": summary_data})
