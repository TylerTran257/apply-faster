from __future__ import annotations

from ..bootstrap.browser import is_valid_linkedin_job_url
from .models import SOURCE_LINKEDIN, JobPostingInput


def validate_posting_url(posting: JobPostingInput) -> bool:
    if not posting.url:
        return False
    if posting.source.lower() == SOURCE_LINKEDIN.lower():
        return is_valid_linkedin_job_url(posting.url)
    return bool(posting.url.strip())
