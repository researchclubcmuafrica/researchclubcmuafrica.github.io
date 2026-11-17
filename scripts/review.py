"""Review list: items from "noisy" sources that a volunteer checks before they go on the tracker.

Used by update_deadlines.py. New items go to data/review/pending.yaml. They do NOT appear on
the tracker until a volunteer moves them to data/manual/approved.yaml (see docs/volunteers.md).

Sources read here:
* ACL (Association for Computational Linguistics) member portal, the two event lists:
  "Browse ACL Events" and "Browse Non-ACL Events". Calls for workshops, shared tasks,
  summer schools and conferences in natural language processing.
  Its robots.txt allows reading these pages with at most one request every 10 seconds.
  We read only the two list pages (2 requests a day, 10 seconds apart) and never each
  event's own page, because the portal blocks readers that ask for many pages.

Skipped: items whose deadline has passed, items already on the tracker, items already in
the review list or in approved.yaml.
"""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import yaml

PORTAL = "https://www.aclweb.org"
ACL_LISTS = [
    f"{PORTAL}/portal/acl_sponsored_events",
    f"{PORTAL}/portal/non-acl_events",
]
CRAWL_DELAY = 10  # seconds, from https://www.aclweb.org/robots.txt
SOURCE = "ACL member portal"

HEADER = """\
# REVIEW LIST - items waiting for a volunteer to check them.
#
# The daily job adds new items here. Nothing in this file is shown on the tracker.
# To publish an item: check it on its official page, fix any field, then MOVE it
# (cut and paste) to data/manual/approved.yaml. See docs/volunteers.md.
# To turn an item down: add the line   reject: true   to it. It then stays here (so it is
# not added again) and is removed by the daily job once its deadline has passed.
#
# "link" points to the item's ACL portal page. When checking, replace it with the
# official website, and check the deadline: the portal gives only a date, so the
# deadline is set to 23:59 AoE (Anywhere on Earth). Fix the time and time zone if needed.

"""


class Portal:
    def __init__(self):
        self.last = 0.0
        self.requests = 0

    def get(self, url: str) -> str:
        wait = CRAWL_DELAY - (time.monotonic() - self.last)
        if self.requests and wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": "conference-deadline-tracker"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        self.last = time.monotonic()
        self.requests += 1
        return text


def text_of(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def parse_date(text: str) -> date | None:
    """'Friday, 5 February 2027' or '17 Aug 2027' -> date."""
    text = re.sub(r"^[A-Za-z]+,\s*", "", text.strip())
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def cell(row: str, name: str) -> str:
    m = re.search(rf'<td\s+class="views-field views-field-{name}(?:\s[^"]*)?"\s*>(.*?)</td>', row, re.S)
    return m.group(1) if m else ""


def parse_list(page: str) -> list[dict]:
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        title_cell = cell(row, "title")
        link = re.search(r'href="([^"]+)"', title_cell)
        if not link:
            continue  # header row
        dates = cell(row, "field-event-date")
        start = re.search(r'date-display-(?:start|single)">([^<]+)<', dates)
        end = re.search(r'date-display-end">([^<]+)<', dates)
        rows.append({
            "title": text_of(title_cell),
            "portal_link": PORTAL + link.group(1) if link.group(1).startswith("/") else link.group(1),
            "venue": text_of(cell(row, "field-event-location")),
            "city": text_of(cell(row, "field-event-city")),
            "country": text_of(cell(row, "field-event-country")),
            "deadline": parse_date(text_of(cell(row, "field-event-submission-deadline"))),
            "start": parse_date(start.group(1)) if start else None,
            "end": parse_date(end.group(1)) if end else None,
        })
    return rows


CFP_PREFIX = re.compile(
    r"(?i)^\s*(\[[^\]]*\]\s*)?((first|second|third|final|last|\d+(st|nd|rd|th))\s+)?"
    r"(call for (papers|participation|submissions?)|cfp|cfps)\s*[:\-–]?\s*")


def clean_title(title: str) -> str:
    """'[2nd CFP - DEADLINE EXTENDED] PACLIC 40: ...' -> 'PACLIC 40: ...'."""
    t = re.sub(r"^\s*\[[^\]]*\]\s*", "", title)  # leading note such as "[2nd CFP - DEADLINE EXTENDED]"
    # "Call for Papers and Mentors: X", "Call for workshop proposals: X", "Call for Abstracts: X" -> "X"
    m = re.match(r"(?i)\s*((first|second|third|final|last|\d+(st|nd|rd|th))\s+)?(call for|cfp\b)[^:]{0,60}:\s*", t)
    if m:
        t = t[m.end():]
    t = CFP_PREFIX.sub("", t)
    t = re.sub(r"(?i)\s*[–-]\s*((first|second|final|\d+(st|nd|rd|th))\s+)?call for (papers|participation)\s*$", "", t)
    return t.strip() or title


def classify(title: str, kind: str) -> str:
    t = f"{title} {kind}".lower()
    if re.search(r"summer school|winter school|spring school|\bschool\b", t):
        return "Summer school"
    if re.search(r"workshop|shared task|semeval|call for participation|tutorial|preconference|co-?located", t):
        return "Workshop"
    # "TrustNLP 2027 @ COLING 2027", "XAI4Who ... at ACL 2027": held at a conference
    if re.search(r"(@| at )\s*(acl|eacl|naacl|emnlp|coling|lrec|aacl|ijcnlp|interspeech|neurips|icml|iclr|aaai|ijcai)\b", t):
        return "Workshop"
    return "Conference"


def series_key(title: str) -> str:
    """Same event posted twice ("RANLP'27" and "... 2027"): compare without years and brackets."""
    t = re.sub(r"\([^)]*\)", "", clean_title(title))
    t = re.sub(r"\b(19|20)\d\d\b|'\d\d\b", "", t)
    return plain(t)


def plain(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def is_duplicate(title: str, website: str, known_titles: list[str], known_links: set[str]) -> bool:
    if website and website.rstrip("/").lower() in known_links:
        return True
    p = plain(clean_title(title))
    for k in known_titles:
        if p == k or (len(p) > 20 and SequenceMatcher(None, p, k).ratio() > 0.9):
            return True
    return False


def load_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def update_review(pending_path: Path, approved_path: Path, records: list[dict], held_in_africa) -> dict:
    """Add new ACL portal items to the review list. Returns counts for the log."""
    today = datetime.now(timezone.utc).date()
    pending = load_list(pending_path)
    approved = load_list(approved_path)

    def still_valid(item) -> bool:
        d = item.get("deadline")
        if not d or str(d).upper() == "TBA":
            return True
        return str(d)[:10] >= today.isoformat()

    # Items a volunteer moved to approved.yaml leave the review list; so do passed deadlines.
    approved_links = {str(a.get("source_link", "")).lower() for a in approved if a.get("source_link")}
    before = len(pending)
    pending = [p for p in pending if still_valid(p) and str(p.get("source_link", "")).lower() not in approved_links]
    removed = before - len(pending)

    known_titles = []
    for r in records:
        for t in (r.get("name"), r.get("full_name")):
            if t:
                known_titles.append(plain(t))
    for a in approved:
        known_titles += [plain(a.get("title", "")), plain(a.get("full_name", ""))]
    known_titles = [k for k in known_titles if k]
    known_links = {str(r.get("link", "")).rstrip("/").lower() for r in records if r.get("link")}
    known_links |= {str(a.get("link", "")).rstrip("/").lower() for a in approved if a.get("link")}
    seen = {str(p.get("source_link", "")).lower() for p in pending}
    seen_series = {series_key(p.get("full_name") or p.get("title", "")) for p in pending}

    counts = {"added": 0, "deadline passed": 0, "already on the tracker": 0, "already in review": 0}
    portal = Portal()
    rows = []
    for url in ACL_LISTS:
        rows += parse_list(portal.get(url))
    rows.sort(key=lambda r: r["deadline"] is None)  # if an event is posted twice, keep the post with a deadline
    for row in rows:
        if row["portal_link"].lower() in seen:
            counts["already in review"] += 1
            continue
        if row["deadline"] and row["deadline"] < today:
            counts["deadline passed"] += 1
            continue
        if is_duplicate(row["title"], "", known_titles, known_links):
            counts["already on the tracker"] += 1
            continue
        if series_key(row["title"]) in seen_series:
            counts["already in review"] += 1
            continue
        # We do not open each item's own page: the portal blocks readers that ask for many
        # pages (it answered 403 Forbidden in testing). The volunteer finds the official
        # website when checking the item.
        deadline = row["deadline"]
        place = ", ".join(x for x in (row["city"], row["country"]) if x) or row["venue"] or "To be announced"
        year = (row["start"] or deadline or today).year
        title = clean_title(row["title"])
        proposal = re.search(r"(?i)call for (workshop|tutorial)s? proposals?", row["title"])
        if proposal:  # a call to organise a workshop or tutorial, not to send a paper
            title = f"{title} (call for {proposal.group(1).lower()} proposals)"
            submission = f"{proposal.group(1).capitalize()} proposal"
        elif re.search(r"(?i)shared task|call for participation", row["title"]):
            submission = "Shared task participation"
        else:
            submission = "Paper"
        item = {
            "title": title,
            "year": year,
            "type": classify(row["title"], ""),
            "submission_type": submission,
            "deadline": f"{deadline.isoformat()} 23:59:59" if deadline else "TBA",
            "timezone": "AoE",
            "place": place,
            "field": ["Natural Language Processing"],
            "link": row["portal_link"],
            "source": SOURCE,
            "source_link": row["portal_link"],
            "found": today.isoformat(),
        }
        if row["start"]:
            item["start"] = row["start"].isoformat()
            item["end"] = (row["end"] or row["start"]).isoformat()
        else:
            item["date"] = "To be announced"
        if held_in_africa(place):
            item["africa"] = True
        pending.append(item)
        seen.add(row["portal_link"].lower())
        seen_series.add(series_key(row["title"]))
        counts["added"] += 1

    pending.sort(key=lambda p: str(p.get("deadline") or "9999"))
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(pending, sort_keys=False, allow_unicode=True, width=1000) if pending else "[]\n"
    pending_path.write_text(HEADER + body, encoding="utf-8")
    counts["removed (approved or deadline passed)"] = removed
    counts["in review list now"] = len(pending)
    counts["portal requests"] = portal.requests
    return counts


def warn(msg: str) -> None:
    print(f"  warning: {msg}", file=sys.stderr)
