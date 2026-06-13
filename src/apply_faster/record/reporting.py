from __future__ import annotations

from datetime import datetime

from .models import RunSummary, SummaryPosting


def _display_label(value: str | None, placeholder: str) -> str:
    return value if value else placeholder


def _needs_url(posting: SummaryPosting) -> bool:
    identity = posting["canonicalId"]
    if posting["status"] == "failed":
        return True
    if not identity["title"] or not identity["company"]:
        return True
    return False


def _format_posting_line(posting: SummaryPosting) -> str:
    identity = posting["canonicalId"]
    status = posting["status"]
    source = _display_label(identity["source"], "(unknown source)")
    company = _display_label(identity["company"], "(unknown company)")
    title = _display_label(identity["title"], "(unknown title)")
    tag = f"[{status}]"
    line = f"  {tag:12s} {source} | {company} | {title}"
    if posting["reason"]:
        line += f" ({posting['reason']})"
    if _needs_url(posting):
        line += f" -- {identity['url'] or '(no url)'}"
    return line


def render_run_report(summary: RunSummary) -> str:
    start = datetime.fromisoformat(summary.start_time)
    end = datetime.fromisoformat(summary.end_time or summary.start_time)
    duration_seconds = int((end - start).total_seconds())
    minutes, seconds = divmod(duration_seconds, 60)
    duration_display = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
    total = summary.reviewed_count + summary.skipped_count + summary.failed_count
    lines = [
        "",
        "=" * 60,
        "        Job Review Session Summary",
        "=" * 60,
        "",
        f"Duration: {duration_display}",
        "",
        "-" * 40,
        "COUNTS",
        "-" * 40,
        f"Reviewed: {summary.reviewed_count}",
        f"Skipped:  {summary.skipped_count}",
        f"Failed:   {summary.failed_count}",
        f"Total:    {total}",
        "",
    ]
    if summary.skip_reasons:
        lines.extend(["-" * 40, "SKIP REASONS", "-" * 40])
        for reason, count in summary.skip_reasons.items():
            lines.append(f"  {reason}: {count}")
        lines.append("")
    if summary.failure_reasons:
        lines.extend(["-" * 40, "FAILURE REASONS", "-" * 40])
        for reason, count in summary.failure_reasons.items():
            lines.append(f"  {reason}: {count}")
        lines.append("")
    lines.extend(["-" * 40, "POSTING OUTCOMES", "-" * 40])
    for posting in summary.postings:
        lines.append(_format_posting_line(posting))
    lines.extend(["", "=" * 60])
    return "\n".join(lines)
