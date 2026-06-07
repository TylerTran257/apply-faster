from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path

from ..paths import LOGS_DIR


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RuntimeLogger:
    session_stamp: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    )

    @property
    def log_path(self) -> Path:
        return LOGS_DIR / f"app-{self.session_stamp}.log"

    def log_run(
        self,
        operation: str,
        status: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> dict[str, object]:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = _now_iso()
        entry = {
            "timestamp": timestamp,
            "operation": operation,
            "status": status,
            "message": message,
            "details": details or {},
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        print(f"[{timestamp}] {operation.upper()} - {status}: {message}")
        return entry

    def log_checkpoint(
        self,
        run_id: str,
        job_id: str | None,
        phase: str,
        data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "runId": run_id,
            "jobId": job_id,
            "checkpointPhase": phase,
        }
        if data:
            payload.update(data)
        return self.log_run(
            "checkpoint", phase, f"Checkpoint recorded: {phase}", payload
        )


_LOGGER = RuntimeLogger()


def get_runtime_logger() -> RuntimeLogger:
    return _LOGGER
