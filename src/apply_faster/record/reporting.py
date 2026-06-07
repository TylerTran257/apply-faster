from __future__ import annotations

from datetime import datetime

from .models import RunSummary


def render_run_report(summary: RunSummary) -> str:
    start = datetime.fromisoformat(summary.start_time)
    end = datetime.fromisoformat(summary.end_time or summary.start_time)
    duration_seconds = int((end - start).total_seconds())
    minutes, seconds = divmod(duration_seconds, 60)
    duration_display = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
    lines = [
        "",
        "=" * 60,
        "           APPLICATION RUN SUMMARY",
        "=" * 60,
        "",
        f"Start Time: {summary.start_time}",
        f"End Time: {summary.end_time}",
        "",
        f"Duration: {duration_display}",
        "",
        "-" * 40,
        "COUNTS",
        "-" * 40,
        f"Reviewed: {summary.reviewed_count}",
        f"Skipped:  {summary.skipped_count}",
        f"Failed:   {summary.failed_count}",
        f"Total:    {summary.reviewed_count + summary.skipped_count + summary.failed_count}",
        "",
    ]
    if summary.skip_reasons:
        lines.extend(["-" * 40, "SKIP REASONS", "-" * 40])
        for reason, count in summary.skip_reasons.items():
            lines.append(f"  • {reason.replace('-', ' ').upper()}: {count}")
        lines.append("")
    if summary.failure_reasons:
        lines.extend(["-" * 40, "FAILURE REASONS", "-" * 40])
        for reason, count in summary.failure_reasons.items():
            lines.append(f"  • {reason}: {count}")
        lines.append("")
    lines.extend(["-" * 40, "POSTING OUTCOMES", "-" * 40])
    for posting in summary.postings:
        identity = posting["canonicalId"]
        emoji = {"reviewed": "✅", "skipped": "⏭️", "failed": "❌"}.get(
            posting["status"], "➖"
        )
        line = f"{emoji} {identity['title']} at {identity['company']}"
        if posting["reason"]:
            line += f" ({posting['reason']})"
        lines.append(line)
    lines.extend(["", "=" * 60])
    return "\n".join(lines)
