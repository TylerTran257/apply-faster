from __future__ import annotations

from ..record.models import SOURCE_LINKEDIN, JobPostingInput
from .extractor import PostingPayload


def normalize_snapshot(postings: list[PostingPayload]) -> list[JobPostingInput]:
    return [
        JobPostingInput(
            source=SOURCE_LINKEDIN,
            url=posting["url"].strip() or None,
            title=posting["title"],
            company=posting["company"],
        )
        for posting in postings
    ]
