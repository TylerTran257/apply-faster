from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from ..paths import OUTPUT_DIR
from .models import RunSummary


def _build_filename(output_dir: Path, now: datetime) -> Path:
    base = f"reviewed-{now.strftime('%Y-%m-%d-%H%M')}"
    candidate = output_dir / f"{base}.csv"
    suffix = 1
    while candidate.exists():
        candidate = output_dir / f"{base}-{suffix}.csv"
        suffix += 1
    return candidate


def export_reviewed_csv(summary: RunSummary) -> Path | None:
    if summary.reviewed_count == 0:
        print("No reviewed jobs -- CSV not generated.")
        return None

    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    path = _build_filename(output_dir, datetime.now())

    rows = [
        posting for posting in summary.postings
        if posting["status"] == "reviewed"
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Source", "Company Name", "Job Title"])
        for posting in rows:
            identity = posting["canonicalId"]
            writer.writerow([
                identity["source"],
                identity["company"] or "",
                identity["title"] or "",
            ])

    print(f"Reviewed jobs CSV saved to: {path}")
    return path
