from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any, TypedDict

from ..paths import OUTPUT_DIR


_CLASSIC_CARD_SELECTORS = (
    "li[data-job-id]",
    ".job-card-container",
    ".jobs-search-results__list-item",
)

_FIND_SCROLLER_JS = r"""
() => {
  function getOverflowY(node) {
    if (typeof window !== "undefined" && window.getComputedStyle && node)
      return window.getComputedStyle(node).overflowY;
    return "";
  }
  function isScrollable(node) {
    if (!node) return false;
    var oy = getOverflowY(node);
    return (oy === "auto" || oy === "scroll" || oy === "overlay")
      && node.scrollHeight > node.clientHeight + 20;
  }
  function findScrollableAncestor(el) {
    var node = el;
    while (node && node !== document.body) {
      if (isScrollable(node)) return node;
      node = node.parentElement;
    }
    return null;
  }
  function findSeedElement() {
    var collLinks = Array.from(document.querySelectorAll('a[href*="currentJobId"]'));
    var firstColl = collLinks.filter(function(l) {
      var t = (l.textContent || "").trim();
      return t.length > 20 && t.indexOf("Show all") !== 0 && t !== "More";
    })[0];
    return document.querySelector("li[data-job-id]")
      || document.querySelector(".job-card-container")
      || document.querySelector(".jobs-search-results__list-item")
      || firstColl
      || document.querySelector('a[href*="/jobs/view/"]');
  }
  var seed = findSeedElement();
  var scroller = seed ? findScrollableAncestor(seed) : null;
  if (scroller) return scroller;
  var candidates = [".jobs-search-results-list", ".scaffold-layout__list", "main"];
  for (var i = 0; i < candidates.length; i++) {
    var c = document.querySelector(candidates[i]);
    if (isScrollable(c)) return c;
  }
  var all = Array.from(document.querySelectorAll("*"));
  for (var j = 0; j < all.length; j++) {
    if (isScrollable(all[j])) return all[j];
  }
  return document.scrollingElement || document.documentElement || document.body;
}
"""

_SCROLL_AND_MEASURE_JS = """el => {
  var h = Math.floor(el.clientHeight * 0.9) || 800;
  if (typeof el.scrollBy === "function") el.scrollBy(0, h);
  else el.scrollTop = (el.scrollTop || 0) + h;
  return { scrollTop: el.scrollTop || 0, scrollHeight: el.scrollHeight || 0 };
}"""


class PostingPayload(TypedDict):
    title: str | None
    company: str | None
    location: str | None
    url: str
    applyType: str


@dataclass
class ExtractionResult:
    postings: list[PostingPayload]
    posting_count: int
    timestamp: str


@dataclass(frozen=True)
class SnapshotArtifact:
    path: Path
    posting_count: int
    timestamp: str


# ---------------------------------------------------------------------------
# Pure-Python text helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _is_meta_text(text: str) -> bool:
    lower = text.lower()
    return (
        lower == "·"
        or lower.startswith("posted ")
        or "ago" in lower
        or lower.startswith("viewed")
        or lower.startswith("reposted")
        or "promoted" in lower
        or "actively reviewing" in lower
        or "easy apply" in lower
        or "connection" in lower
        or "alumni" in lower
        or "applicant" in lower
        or "benefit" in lower
        or bool(re.match(r"^\$[\d,]", text))
    )


def _is_location_text(text: str) -> bool:
    lower = text.lower()
    return bool(
        re.search(r",\s*[A-Z]{2}(?:\b|\s)", text)
        or "(remote)" in lower
        or "(hybrid)" in lower
        or "(on-site)" in lower
        or lower == "united states"
        or lower.startswith("united states ")
        or "metropolitan area" in lower
    )


# ---------------------------------------------------------------------------
# Browser helpers — card counting
# ---------------------------------------------------------------------------

def _get_collection_links(page: Any) -> list[Any]:
    links = page.query_selector_all('a[href*="currentJobId"]')
    result: list[Any] = []
    for link in links:
        text = (link.text_content() or "").strip()
        if len(text) > 20 and not text.startswith("Show all") and text != "More":
            result.append(link)
    return result


def _count_cards(page: Any) -> int:
    for selector in _CLASSIC_CARD_SELECTORS:
        count = len(page.query_selector_all(selector))
        if count > 0:
            return count
    return len(_get_collection_links(page))


# ---------------------------------------------------------------------------
# Browser helpers — scrolling
# ---------------------------------------------------------------------------

def _scroll_to_load_all_cards(
    page: Any,
    max_scroll_attempts: int = 5,
    scroll_wait_ms: int = 1000,
) -> None:
    previous_card_count = 0
    previous_scroll_top = -1
    previous_scroll_height = -1
    stalled_attempts = 0

    for i in range(max_scroll_attempts):
        scroller = page.evaluate_handle(_FIND_SCROLLER_JS)

        metrics: dict[str, int] = scroller.evaluate(_SCROLL_AND_MEASURE_JS)
        scroll_top = metrics["scrollTop"]
        scroll_height = metrics["scrollHeight"]

        card_count = _count_cards(page)
        no_card_growth = card_count <= previous_card_count
        no_scroll_movement = (
            scroll_top == previous_scroll_top
            and scroll_height == previous_scroll_height
        )

        if i > 0 and no_card_growth and no_scroll_movement:
            stalled_attempts += 1
            if stalled_attempts >= 2:
                break
        else:
            stalled_attempts = 0

        previous_card_count = card_count
        previous_scroll_top = scroll_top
        previous_scroll_height = scroll_height

        page.wait_for_timeout(scroll_wait_ms)


# ---------------------------------------------------------------------------
# Classic card parsing
# ---------------------------------------------------------------------------

def _resolve_href(element: Any) -> str | None:
    return element.evaluate("el => el.href || el.getAttribute('href')")


def _parse_classic_card(card: Any) -> PostingPayload | None:
    link_el = (
        card.query_selector('a[href*="/jobs/view/"]')
        or card.query_selector('a[href*="/jobs/"]')
        or card.query_selector("a")
    )
    url = _resolve_href(link_el) if link_el else None

    title: str | None = None
    if link_el:
        aria_label = link_el.get_attribute("aria-label")
        if aria_label:
            title = aria_label.strip()

    if not title:
        title_el = (
            card.query_selector("[data-job-title]")
            or card.query_selector(".job-card-list__title")
        )
        if title_el:
            title = (title_el.text_content() or "").strip() or None

    if not title and link_el:
        link_text = (link_el.text_content() or "").strip()
        if link_text:
            title = link_text

    company_el = (
        card.query_selector("[data-company-name]")
        or card.query_selector(".artdeco-entity-lockup__subtitle")
    )
    company = (company_el.text_content() or "").strip() or None if company_el else None

    location_el = (
        card.query_selector("[data-location]")
        or card.query_selector(".artdeco-entity-lockup__metadata")
        or card.query_selector(".job-card-container__metadata-item")
    )
    location = (location_el.text_content() or "").strip() or None if location_el else None

    apply_type = "external"
    card_text = card.text_content() or ""
    if "easy apply" in card_text.lower():
        apply_type = "easy-apply"

    if not title or not url:
        return None

    return PostingPayload(
        title=title,
        company=company,
        location=location,
        url=url,
        applyType=apply_type,
    )


def _parse_job_cards_from_dom(page: Any) -> list[PostingPayload]:
    for selector in _CLASSIC_CARD_SELECTORS:
        cards = page.query_selector_all(selector)
        if cards:
            results: list[PostingPayload] = []
            for card in cards:
                parsed = _parse_classic_card(card)
                if parsed:
                    results.append(parsed)
            return results
    return []


# ---------------------------------------------------------------------------
# Collections card parsing
# ---------------------------------------------------------------------------

def _get_ordered_text_blocks(link: Any, full_text: str) -> list[str]:
    nodes = link.query_selector_all("div, span, strong, p")
    seen: set[str] = set()
    blocks: list[str] = []
    for node in nodes:
        text = _normalize_text(node.text_content())
        if not text or text == full_text or len(text) > 140:
            continue
        if text in seen:
            continue
        seen.add(text)
        blocks.append(text)

    return [
        text
        for idx, text in enumerate(blocks)
        if not any(
            blocks[j] != text and len(blocks[j]) >= 3 and blocks[j] in text
            for j in range(idx + 1, len(blocks))
        )
    ]


def _parse_collections_card(link: Any) -> PostingPayload | None:
    href: str = _resolve_href(link) or ""
    job_id_match = re.search(r"currentJobId=(\d+)", href)
    job_id = job_id_match.group(1) if job_id_match else None
    url = f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id else None

    full_text = _normalize_text(link.text_content())
    blocks = _get_ordered_text_blocks(link, full_text)

    title: str | None = None
    company: str | None = None
    location: str | None = None

    for block in blocks:
        if not title and not _is_meta_text(block):
            title = block
            continue
        if title and not company and block != title and not _is_meta_text(block) and not _is_location_text(block):
            company = block
            continue
        if title and not location and _is_location_text(block):
            location = block

    if title:
        title = re.sub(r"\s*\(Verified job\)\s*", "", title)
        if len(title) > 2 and len(title) % 2 == 0:
            half = title[: len(title) // 2]
            if title == half + half:
                title = half

    if not title:
        bullet_idx = full_text.find(" • ")
        if bullet_idx > 0:
            title = full_text[:bullet_idx].strip()
            title = re.sub(r"\s*\(Verified job\)\s*", "", title)

    bullet_idx2 = full_text.find(" • ")
    if (not company or not location) and bullet_idx2 > 0:
        after_title = full_text[bullet_idx2 + 3 :]
        company_text = full_text[:bullet_idx2]
        if title and title in company_text:
            company_text = company_text[company_text.rfind(title) + len(title) :].strip()
        company_text = re.sub(r"\s*\(Verified job\)\s*", "", company_text).strip()
        if not company and company_text:
            company = company_text
        loc_match = re.match(
            r"^([^•\n]+?)(?:\s*\((?:On-site|Remote|Hybrid)\)|\s*•|\s*\d)",
            after_title,
        )
        if not location and loc_match:
            loc_raw = loc_match.group(1).strip()
            location = re.sub(r"\s*\$[\d,]+.*$", "", loc_raw).strip()
        if not location:
            paren_idx = after_title.find("(")
            if paren_idx > 0:
                location = after_title[:paren_idx].strip()
        if location and len(location) > 80:
            location = None

    apply_type = "external"
    if "easy apply" in full_text.lower():
        apply_type = "easy-apply"

    if not title or not url:
        return None

    return PostingPayload(
        title=title,
        company=company,
        location=location,
        url=url,
        applyType=apply_type,
    )


def _parse_collections_job_cards(page: Any) -> list[PostingPayload]:
    links = _get_collection_links(page)
    results: list[PostingPayload] = []
    for link in links:
        parsed = _parse_collections_card(link)
        if parsed:
            results.append(parsed)
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_visible_results_list(page: Any) -> ExtractionResult:
    if "linkedin.com/jobs" not in page.url:
        return ExtractionResult(
            postings=[],
            posting_count=0,
            timestamp=datetime.now(UTC).isoformat(),
        )

    _scroll_to_load_all_cards(page, max_scroll_attempts=5, scroll_wait_ms=1000)

    postings = _parse_job_cards_from_dom(page)
    if not postings:
        postings = _parse_collections_job_cards(page)

    return ExtractionResult(
        postings=postings,
        posting_count=len(postings),
        timestamp=datetime.now(UTC).isoformat(),
    )


def write_results_snapshot(result: ExtractionResult) -> SnapshotArtifact:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = result.timestamp.replace(":", "-").replace(".", "-")
    snapshot_path = OUTPUT_DIR / f"snapshot-{timestamp}.json"
    snapshot_path.write_text(json.dumps(result.postings, indent=2), encoding="utf-8")
    return SnapshotArtifact(
        path=snapshot_path,
        posting_count=result.posting_count,
        timestamp=result.timestamp,
    )
