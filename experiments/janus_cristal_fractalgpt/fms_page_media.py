#!/usr/bin/env python3
"""Resolve labeled FMDB specimen images without persisting their media bytes.

The scientific identity boundary is the single FMDB specimen record. This helper
only resolves which full-resolution image URL belongs to a caption such as
"Normal light" or "Fluorescence under shortwave UV light". It does not infer
specimen identity across separate records.
"""
from __future__ import annotations

import re
import urllib.request
from html import unescape

UA = "Janus-Cristal-FMS-resolver/0.1 (+https://github.com/Hawkar-usls/Janus_Genesis)"


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def _attr(tag: str, name: str) -> str | None:
    m = re.search(rf"\b{name}\s*=\s*([\"'])(.*?)\1", tag, flags=re.I | re.S)
    return unescape(m.group(2)) if m else None


def _largest_src_from_tag(tag: str) -> str | None:
    srcset = _attr(tag, "srcset") or _attr(tag, "data-srcset")
    if srcset:
        choices = []
        for item in srcset.split(","):
            item = item.strip()
            if not item:
                continue
            parts = item.split()
            url = parts[0]
            width = 0
            if len(parts) > 1 and parts[1].lower().endswith("w"):
                try:
                    width = int(parts[1][:-1])
                except ValueError:
                    pass
            choices.append((width, url))
        if choices:
            return max(choices)[1]
    return _attr(tag, "data-src") or _attr(tag, "src")


def _strip_html(s: str) -> str:
    s = re.sub(r"<script\b.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", unescape(s)).strip()


def media_candidates(page_url: str) -> list[dict]:
    html = _fetch_text(page_url)
    out = []
    for m in re.finditer(r"<img\b[^>]*>", html, flags=re.I | re.S):
        tag = m.group(0)
        start, end = m.span()
        # Full-resolution WordPress images are often linked from an enclosing <a>.
        pre = html[max(0, start - 1800):start]
        post = html[end:min(len(html), end + 1800)]
        a_open = list(re.finditer(r"<a\b[^>]*>", pre, flags=re.I | re.S))
        full_url = None
        if a_open:
            candidate_tag = a_open[-1].group(0)
            href = _attr(candidate_tag, "href")
            # Only use the parent href if no closing </a> occurs after that opener before the img.
            tail = pre[a_open[-1].end():]
            if "</a" not in tail.lower() and href and re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", href, re.I):
                full_url = href
        src = full_url or _largest_src_from_tag(tag)
        if not src or src.startswith("data:"):
            continue
        context = _strip_html(pre[-900:] + " " + tag + " " + post[:900])
        out.append({
            "url": src,
            "alt": _attr(tag, "alt") or "",
            "title": _attr(tag, "title") or "",
            "context": context[:1200],
        })
    # Preserve order while removing duplicate URLs caused by responsive markup.
    seen = set()
    unique = []
    for item in out:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique


def resolve_labeled_media(page_url: str, label: str) -> dict:
    label_norm = re.sub(r"\s+", " ", label.strip().lower().rstrip("."))
    rows = media_candidates(page_url)
    scored = []
    for i, row in enumerate(rows):
        hay = " ".join([row["alt"], row["title"], row["context"]]).lower()
        hay = re.sub(r"\s+", " ", hay)
        score = 0
        if label_norm in hay:
            score += 100
        words = [w for w in re.findall(r"[a-z0-9]+", label_norm) if len(w) >= 3]
        score += sum(4 for w in words if w in hay)
        if "shortwave" in label_norm and ("shortwave" in hay or "254" in hay):
            score += 40
        if "normal" in label_norm and ("normal light" in hay or "natural light" in hay):
            score += 40
        scored.append((score, -i, row))
    scored.sort(reverse=True, key=lambda x: (x[0], x[1]))
    if not scored or scored[0][0] < 20:
        raise RuntimeError(f"Could not resolve FMDB label {label!r}; candidates={len(rows)}")
    best_score = scored[0][0]
    tied = [x for x in scored if x[0] == best_score]
    # If exact text context yields a tie, prefer the earlier page image but expose ambiguity.
    best = tied[0][2]
    return {
        "label": label,
        "url": best["url"],
        "score": best_score,
        "candidate_count": len(rows),
        "top_score_tie_count": len(tied),
        "alt": best["alt"],
        "title": best["title"],
        "context_excerpt": best["context"][:500],
        "status": "RESOLVED" if len(tied) == 1 else "RESOLVED_WITH_TOP_SCORE_TIE_EARLIEST_PAGE_ORDER",
    }
