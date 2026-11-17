"""Read submission deadlines from the public OpenReview API (api2.openreview.net).

Used by update_deadlines.py. No account or key is needed.

What OpenReview gives us
------------------------
* A list of "active venues" (about 1,000 entries: conferences, workshops,
  journals, courses...).
* For each venue, a "Submission" form with a closing time (duedate).
  This is when the OpenReview form stops taking NEW submissions. For many
  conferences this is the abstract or paper registration deadline, which can be
  a few days before the full paper deadline. So when the ai-deadlines list also
  has the conference, its date stays the main deadline and the OpenReview date
  is shown as an extra line.
* The venue's full name, location, start date and website.

OpenReview limits how fast you can call it, so we wait between calls and
retry when it says "too many requests" (HTTP 429).
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api2.openreview.net"
PAUSE = 1.0  # seconds between calls
YEAR_RE = re.compile(r"^(20\d\d)$")


class OpenReview:
    def __init__(self, pause: float = PAUSE):
        self.pause = pause
        self.calls = 0
        self.failures = 0
        self.retries = 0  # "too many requests" answers
        self.waited = 0.0  # seconds spent waiting after those answers
        self.timeouts = 0  # calls that got no answer in time (network problems)
        self.seconds = 0.0  # total time spent on OpenReview calls

    def get(self, path: str, params: dict) -> dict | None:
        url = f"{API}{path}?{urllib.parse.urlencode(params)}"
        for attempt in range(6):
            if self.calls:
                time.sleep(self.pause)
            self.calls += 1
            req = urllib.request.Request(url, headers={"User-Agent": "conference-deadline-tracker"})
            started = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.load(resp)
                self.seconds += time.monotonic() - started
                return data
            except urllib.error.HTTPError as err:
                if err.code == 429:  # too many requests: wait longer each time
                    self.retries += 1
                    self.waited += 5 * (attempt + 1)
                    time.sleep(5 * (attempt + 1))
                    continue
                if err.code in (403, 404):  # not there, or not public
                    return None
                break
            except (urllib.error.URLError, TimeoutError):
                self.timeouts += 1
                time.sleep(3)
        self.failures += 1
        return None

    def active_venues(self) -> list[str]:
        data = self.get("/groups", {"id": "active_venues"}) or {}
        groups = data.get("groups") or [{}]
        return list(groups[0].get("members") or [])

    def venue(self, venue_id: str) -> dict | None:
        """Deadline and details for one venue, or None if it has no submission form we can read."""
        inv = self.get("/invitations", {"id": f"{venue_id}/-/Submission", "expired": "true"})
        invitations = (inv or {}).get("invitations") or []
        due = invitations[0].get("duedate") if invitations else None
        if not due:
            return None
        info = self.details(venue_id)
        info["deadline_utc"] = ms_to_iso(due)
        return info

    def details(self, venue_id: str) -> dict:
        """Name, place, start date and website of a venue. Works before its submission form exists."""
        grp = self.get("/groups", {"id": venue_id}) or {}
        return info_from_group(venue_id, ((grp.get("groups") or [{}])[0]).get("content") or {})

    def workshops(self, parent: str) -> tuple[list[dict], int] | None:
        """All workshops under a conference, e.g. parent 'NeurIPS.cc/2026'.

        Uses one call to list the workshop groups and one call per 40 submission forms,
        instead of two calls per workshop. Returns (workshops with a deadline, number
        without a submission form yet), or None if OpenReview could not be read."""
        data = self.get("/groups", {"parent": f"{parent}/Workshop"})
        if data is None:
            return None
        infos = {}
        for grp in data.get("groups") or []:
            content = grp.get("content") or {}
            sub_id = (content.get("submission_id") or {}).get("value") or f"{grp['id']}/-/Submission"
            infos[sub_id] = info_from_group(grp["id"], content)
        ids = list(infos)
        for i in range(0, len(ids), 40):
            inv = self.get("/invitations", {"ids": ",".join(ids[i:i + 40]), "expired": "true"})
            if inv is None:
                return None
            for item in inv.get("invitations") or []:
                if item.get("id") in infos and item.get("duedate"):
                    infos[item["id"]]["deadline_utc"] = ms_to_iso(item["duedate"])
        found = [info for info in infos.values() if info["deadline_utc"]]
        return found, len(infos) - len(found)


def info_from_group(venue_id: str, content: dict) -> dict:
    def val(key):
        v = (content.get(key) or {}).get("value")
        return v.strip() if isinstance(v, str) else v

    start = val("start_date")
    if isinstance(start, str) and start.isdigit():
        start = int(start)
    return {
        "id": venue_id,
        "deadline_utc": None,
        "title": val("title") or "",
        "subtitle": val("subtitle") or "",
        "location": val("location") or "",
        "start": datetime.fromtimestamp(start / 1000, timezone.utc).date() if isinstance(start, (int, float)) else None,
        "website": val("website") or "",
        "link": f"https://openreview.net/group?id={urllib.parse.quote(venue_id, safe='/')}",
    }


def ms_to_iso(ms) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def looks_like_aoe(iso: str) -> bool:
    """23:59 AoE is 11:59 UTC the next day."""
    return iso[11:16] == "11:59"


def plain(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def split_venue_id(venue_id: str):
    """'thecvf.com/CVPR/2027/Conference' -> ('CVPR', 2027, 'Conference').

    The short name is the part just before the year, without a web domain ending
    ('ICLR.cc' -> 'ICLR', 'AAAI.org' -> 'AAAI')."""
    parts = venue_id.split("/")
    for i, part in enumerate(parts):
        if YEAR_RE.match(part) and i > 0:
            short = re.sub(r"\.(cc|org|io|com|net|in|ai|edu|club)$", "", parts[i - 1], flags=re.IGNORECASE)
            return short, int(part), "/".join(parts[i + 1:])
    return None, None, None


def newest_matching(active: list[str], template: str) -> str | None:
    """Find the newest active venue that fits a template like 'NeurIPS.cc/{year}/Workshop/Africa_in_AI'."""
    pattern = re.compile("^" + re.escape(template).replace(re.escape("{year}"), r"(20\d\d)") + "$")
    best = None
    for vid in active:
        m = pattern.match(vid)
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), vid)
    return best[1] if best else None


def conference_index(active: list[str]) -> dict[str, list[tuple[int, str]]]:
    """Main conference venues by plain short name: {'cvpr': [(2027, 'thecvf.com/CVPR/2027/Conference')]}."""
    index: dict[str, list[tuple[int, str]]] = {}
    for vid in active:
        short, year, rest = split_venue_id(vid)
        if short and rest == "Conference":
            index.setdefault(plain(short), []).append((year, vid))
    for items in index.values():
        items.sort(reverse=True)
    return index


def warn(msg: str) -> None:
    print(f"  warning: {msg}", file=sys.stderr)
