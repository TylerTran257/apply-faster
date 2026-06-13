from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    status: str = "idle"
    current_index: int = 0
    total: int = 0
    current_posting: dict[str, Any] | None = None
    completed_postings: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] | None = None
    error: str | None = None
    csv_path: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_running(self, total: int) -> None:
        with self._lock:
            self.status = "running"
            self.total = total
            self.current_index = 0
            self.current_posting = None
            self.completed_postings = []
            self.summary = None
            self.error = None
            self.csv_path = None

    def set_current_job(self, index: int, posting: dict[str, Any]) -> None:
        with self._lock:
            self.current_index = index
            self.current_posting = posting

    def add_completed(self, posting: dict[str, Any]) -> None:
        with self._lock:
            self.completed_postings.append(posting)

    def set_complete(self, summary: dict[str, Any], csv_path: str | None = None) -> None:
        with self._lock:
            self.status = "complete"
            self.summary = summary
            self.current_posting = None
            self.csv_path = csv_path

    def set_error(self, error: str) -> None:
        with self._lock:
            self.status = "error"
            self.error = error
            self.current_posting = None

    def reset(self) -> None:
        with self._lock:
            self.status = "idle"
            self.current_index = 0
            self.total = 0
            self.current_posting = None
            self.completed_postings = []
            self.summary = None
            self.error = None
            self.csv_path = None

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "current_index": self.current_index,
                "total": self.total,
                "current_posting": self.current_posting,
                "completed_postings": list(self.completed_postings),
                "summary": self.summary,
                "error": self.error,
                "csv_path": self.csv_path,
            }
