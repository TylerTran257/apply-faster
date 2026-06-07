from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, TypedDict

from ..paths import OUTPUT_DIR


EXTRACT_VISIBLE_RESULTS_JS = r"""
({ maxScrollAttempts, scrollWaitMs }) => {
  function parseJobCardsFromDOM() {
    var cards = Array.from(document.querySelectorAll("li[data-job-id]"));
    if (cards.length === 0) cards = Array.from(document.querySelectorAll(".job-card-container"));
    if (cards.length === 0) cards = Array.from(document.querySelectorAll(".jobs-search-results__list-item"));
    if (cards.length === 0) return [];
    return cards.map(function (card) {
      var linkEl = card.querySelector('a[href*="/jobs/view/"]') || card.querySelector('a[href*="/jobs/"]') || card.querySelector("a");
      var url = linkEl ? linkEl.href || linkEl.getAttribute("href") : null;
      var title = null;
      if (linkEl) {
        var ariaLabel = linkEl.getAttribute("aria-label");
        if (ariaLabel) title = ariaLabel.trim();
      }
      if (!title) {
        var titleEl = card.querySelector("[data-job-title]") || card.querySelector(".job-card-list__title");
        if (titleEl) title = titleEl.textContent.trim();
      }
      if (!title && linkEl) {
        var linkText = linkEl.textContent.trim();
        if (linkText) title = linkText;
      }
      var companyEl = card.querySelector("[data-company-name]") || card.querySelector(".artdeco-entity-lockup__subtitle");
      var company = companyEl ? companyEl.textContent.trim() : null;
      var locationEl = card.querySelector("[data-location]") || card.querySelector(".artdeco-entity-lockup__metadata") || card.querySelector(".job-card-container__metadata-item");
      var location = locationEl ? locationEl.textContent.trim() || null : null;
      var applyType = "external";
      var cardText = card.textContent || "";
      if (cardText.toLowerCase().indexOf("easy apply") !== -1) applyType = "easy-apply";
      return { title: title, company: company, location: location, url: url, applyType: applyType };
    });
  }

  function parseCollectionsJobCards() {
    function normalizeText(text) { return text ? text.replace(/\s+/g, " ").trim() : ""; }
    function isMetaText(text) {
      var lower = text.toLowerCase();
      return lower === "·" || lower.indexOf("posted ") === 0 || lower.indexOf("ago") !== -1 || lower.indexOf("viewed") === 0 || lower.indexOf("reposted") === 0 || lower.indexOf("promoted") !== -1 || lower.indexOf("actively reviewing") !== -1 || lower.indexOf("easy apply") !== -1 || lower.indexOf("connection") !== -1 || lower.indexOf("alumni") !== -1 || lower.indexOf("applicant") !== -1 || lower.indexOf("benefit") !== -1 || /^\$[\d,]/.test(text);
    }
    function isLocationText(text) {
      var lower = text.toLowerCase();
      return /,\s*[A-Z]{2}(?:\b|\s)/.test(text) || lower.indexOf("(remote)") !== -1 || lower.indexOf("(hybrid)") !== -1 || lower.indexOf("(on-site)") !== -1 || lower === "united states" || lower.indexOf("united states ") === 0 || lower.indexOf("metropolitan area") !== -1;
    }
    function getOrderedTextBlocks(link, fullText) {
      var seen = {};
      var nodes = Array.from(link.querySelectorAll("div, span, strong, p"));
      var blocks = [];
      for (var i = 0; i < nodes.length; i++) {
        var text = normalizeText(nodes[i].textContent);
        if (!text || text === fullText || text.length > 140) continue;
        if (seen[text]) continue;
        seen[text] = true;
        blocks.push(text);
      }
      return blocks.filter(function (text, index) {
        for (var j = index + 1; j < blocks.length; j++) {
          if (blocks[j] !== text && blocks[j].length >= 3 && text.indexOf(blocks[j]) !== -1) return false;
        }
        return true;
      });
    }
    var links = Array.from(document.querySelectorAll('a[href*="currentJobId"]'));
    var jobLinks = [];
    for (var i = 0; i < links.length; i++) {
      var text = links[i].textContent.trim();
      if (text.length > 20 && text.indexOf("Show all") !== 0 && text !== "More") jobLinks.push(links[i]);
    }
    if (jobLinks.length === 0) return [];
    return jobLinks.map(function (link) {
      var href = link.href || link.getAttribute("href") || "";
      var jobIdMatch = href.match(/currentJobId=(\d+)/);
      var jobId = jobIdMatch ? jobIdMatch[1] : null;
      var url = jobId ? "https://www.linkedin.com/jobs/view/" + jobId + "/" : null;
      var fullText = normalizeText(link.textContent);
      var blocks = getOrderedTextBlocks(link, fullText);
      var title = null;
      var company = null;
      var location = null;
      for (var j = 0; j < blocks.length; j++) {
        var block = blocks[j];
        if (!title && !isMetaText(block)) { title = block; continue; }
        if (title && !company && block !== title && !isMetaText(block) && !isLocationText(block)) { company = block; continue; }
        if (title && !location && isLocationText(block)) { location = block; }
      }
      if (title) {
        title = title.replace(/\s*\(Verified job\)\s*/g, "");
        if (title.length > 2 && title.length % 2 === 0) {
          var half = title.substring(0, title.length / 2);
          if (title === half + half) title = half;
        }
      }
      if (!title) {
        var bulletIdx = fullText.indexOf(" • ");
        if (bulletIdx > 0) {
          title = fullText.substring(0, bulletIdx).trim();
          title = title.replace(/\s*\(Verified job\)\s*/g, "");
        }
      }
      var bulletIdx2 = fullText.indexOf(" • ");
      if ((!company || !location) && bulletIdx2 > 0) {
        var afterTitle = fullText.substring(bulletIdx2 + 3);
        var companyText = fullText.substring(0, bulletIdx2);
        if (title && companyText.indexOf(title) !== -1) companyText = companyText.substring(companyText.lastIndexOf(title) + title.length).trim();
        companyText = companyText.replace(/\s*\(Verified job\)\s*/g, "").trim();
        if (!company && companyText) company = companyText;
        var locMatch = afterTitle.match(/^([^•\n]+?)(?:\s*\((?:On-site|Remote|Hybrid)\)|\s*•|\s*\d)/);
        if (!location && locMatch) {
          location = locMatch[1].trim();
          location = location.replace(/\s*\$[\d,]+.*$/, "").trim();
        }
        if (!location) {
          var parenIdx = afterTitle.indexOf("(");
          if (parenIdx > 0) location = afterTitle.substring(0, parenIdx).trim();
        }
        if (location && location.length > 80) location = null;
      }
      var applyType = "external";
      if (fullText.toLowerCase().indexOf("easy apply") !== -1) applyType = "easy-apply";
      return { title: title, company: company, location: location, url: url, applyType: applyType };
    });
  }

  var currentUrl = window.location.href;
  if (currentUrl.indexOf("linkedin.com/jobs") === -1) {
    return { postings: [], postingCount: 0, timestamp: new Date().toISOString() };
  }

  var previousCardCount = 0;
  var previousScrollTop = -1;
  var previousScrollHeight = -1;
  var stalledAttempts = 0;

  function getCollectionLinks() {
    var links = Array.from(document.querySelectorAll('a[href*="currentJobId"]'));
    return links.filter(function (link) {
      var text = (link.textContent || "").trim();
      return text.length > 20 && text.indexOf("Show all") !== 0 && text !== "More";
    });
  }
  function countCards() {
    var classicCount = document.querySelectorAll("li[data-job-id]").length;
    if (classicCount > 0) return classicCount;
    var fallbackCount = document.querySelectorAll(".job-card-container").length;
    if (fallbackCount > 0) return fallbackCount;
    var listItemCount = document.querySelectorAll(".jobs-search-results__list-item").length;
    if (listItemCount > 0) return listItemCount;
    return getCollectionLinks().length;
  }
  function getOverflowY(node) {
    if (typeof window !== "undefined" && window.getComputedStyle && node) return window.getComputedStyle(node).overflowY;
    return "";
  }
  function isScrollable(node) {
    if (!node) return false;
    var overflowY = getOverflowY(node);
    return (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") && node.scrollHeight > node.clientHeight + 20;
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
    return document.querySelector("li[data-job-id]") || document.querySelector(".job-card-container") || document.querySelector(".jobs-search-results__list-item") || getCollectionLinks()[0] || document.querySelector('a[href*="/jobs/view/"]');
  }
  function findFallbackScroller() {
    var selectorCandidates = [".jobs-search-results-list", ".scaffold-layout__list", "main"];
    for (var k = 0; k < selectorCandidates.length; k++) {
      var candidate = document.querySelector(selectorCandidates[k]);
      if (isScrollable(candidate)) return candidate;
    }
    var elements = Array.from(document.querySelectorAll("*"));
    for (var m = 0; m < elements.length; m++) {
      if (isScrollable(elements[m])) return elements[m];
    }
    return document.scrollingElement || document.documentElement || document.body;
  }

  for (var i = 0; i < maxScrollAttempts; i++) {
    var firstCard = findSeedElement();
    var scroller = (firstCard && findScrollableAncestor(firstCard)) || findFallbackScroller();
    var scrollTop = 0;
    var scrollHeight = 0;
    var clientHeight = 0;
    if (scroller) {
      scrollTop = scroller.scrollTop || 0;
      scrollHeight = scroller.scrollHeight || 0;
      clientHeight = scroller.clientHeight || 0;
      var scrollAmount = Math.floor(clientHeight * 0.9) || 800;
      if (typeof scroller.scrollBy === "function") scroller.scrollBy(0, scrollAmount);
      else scroller.scrollTop = scrollTop + scrollAmount;
      scrollTop = scroller.scrollTop || scrollTop;
      scrollHeight = scroller.scrollHeight || scrollHeight;
      clientHeight = scroller.clientHeight || clientHeight;
    }
    var cardCount = countCards();
    var noCardGrowth = cardCount <= previousCardCount;
    var noScrollMovement = scrollTop === previousScrollTop && scrollHeight === previousScrollHeight;
    if (i > 0 && noCardGrowth && noScrollMovement) {
      stalledAttempts++;
      if (stalledAttempts >= 2) break;
    } else {
      stalledAttempts = 0;
    }
    previousCardCount = cardCount;
    previousScrollTop = scrollTop;
    previousScrollHeight = scrollHeight;
    const end = Date.now() + scrollWaitMs;
    while (Date.now() < end) {}
  }

  var rawCards = parseJobCardsFromDOM();
  if (rawCards.length === 0) rawCards = parseCollectionsJobCards();
  var postings = [];
  for (var j = 0; j < rawCards.length; j++) {
    var card = rawCards[j];
    if (!card.title || !card.url) continue;
    postings.push(card);
  }
  return { postings: postings, postingCount: postings.length, timestamp: new Date().toISOString() };
}
"""


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


def extract_visible_results_list(page: Any) -> ExtractionResult:
    raw = page.evaluate(
        EXTRACT_VISIBLE_RESULTS_JS,
        {"maxScrollAttempts": 5, "scrollWaitMs": 1000},
    )
    postings: list[PostingPayload] = raw["postings"]
    return ExtractionResult(
        postings=postings,
        posting_count=raw["postingCount"],
        timestamp=raw["timestamp"],
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
