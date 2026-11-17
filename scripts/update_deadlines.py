#!/usr/bin/env python3
"""Build data/deadlines.json for tracker.html.

Steps:
  1. Read conference deadlines from the AI deadlines list that Hugging Face keeps
     on Papers with Code (https://paperswithcode.co/ai-deadlines), through its
     public API. Full conference names come from the huggingface/ai-deadlines
     GitHub repository, because the API does not include them.
  2. Check those conferences on OpenReview, and add the extra OpenReview venues
     listed in data/openreview_venues.yml (see scripts/openreview.py).
  3. Add the African venues kept by hand in data/african_venues.yml.
  4. Turn every deadline into a UTC time and write data/deadlines.json.

Usage:
    python scripts/update_deadlines.py                           # Papers with Code API + OpenReview
    python scripts/update_deadlines.py --source huggingface      # GitHub repo (updated less often)
    python scripts/update_deadlines.py --source paperswithcode   # old list (last updated 2024)
    python scripts/update_deadlines.py --no-openreview           # skip OpenReview

Needs Python 3.9+ and PyYAML (pip install pyyaml).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tarfile
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import openreview as orv  # noqa: E402
import review  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AFRICAN = ROOT / "data" / "african_venues.yml"
DEFAULT_OUT = ROOT / "data" / "deadlines.json"
DEFAULT_OPENREVIEW = ROOT / "data" / "openreview_venues.yml"
DEFAULT_NAMES = ROOT / "data" / "full_names.yml"
DEFAULT_WORKSHOPS = ROOT / "data" / "manual" / "workshops.yaml"
DEFAULT_SCHOOLS = ROOT / "data" / "manual" / "summer-schools.yaml"
DEFAULT_APPROVED = ROOT / "data" / "manual" / "approved.yaml"
DEFAULT_PENDING = ROOT / "data" / "review" / "pending.yaml"

# Kinds of opportunity shown on the page, in filter order.
TYPES = ["Conference", "Workshop", "Summer school", "Community talk", "Fellowship"]

SOURCES = {
    "api": {
        "label": "Papers with Code AI deadlines",
        "page": "https://paperswithcode.co/ai-deadlines",
        "url": "https://paperswithcode.co/api/v1/conferences/deadlines",
    },
    "paperswithcode": {
        "label": "paperswithcode/ai-deadlines",
        "page": "https://github.com/paperswithcode/ai-deadlines",
        "url": "https://raw.githubusercontent.com/paperswithcode/ai-deadlines/gh-pages/_data/conferences.yml",
    },
    "huggingface": {
        "label": "huggingface/ai-deadlines",
        "page": "https://github.com/huggingface/ai-deadlines",
        "url": "https://codeload.github.com/huggingface/ai-deadlines/tar.gz/main",
    },
}

# Field codes used by paperswithcode/ai-deadlines, written out in full.
FIELD_CODES = {
    "ML": "Machine Learning",
    "CV": "Computer Vision",
    "CG": "Computer Graphics",
    "NLP": "Natural Language Processing",
    "RO": "Robotics",
    "SP": "Speech and Signal Processing",
    "DM": "Data Mining",
    "AP": "Automated Planning",
    "KR": "Knowledge Representation",
    "HCI": "Human-Computer Interaction",
}

# Short time zone names that zoneinfo does not know.
TZ_ALIASES = {
    "AOE": "UTC-12",  # Anywhere on Earth
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CET": "Europe/Paris",
    "CEST": "Europe/Paris",
}

# Words to keep in capitals when turning a tag like "large-language-models" into a label.
UPPER_WORDS = {"ai", "nlp", "hci"}
SMALL_WORDS = {"and", "of", "for", "on", "in", "the"}

# Conferences held every two years. The list may hold only one recent edition,
# so the gap between editions cannot always be worked out from the data.
KNOWN_CYCLE = {"iccv": 2, "eccv": 2, "accv": 2, "lrec": 2}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "conference-deadline-tracker"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def parse_tz(name) -> timezone | ZoneInfo:
    """Turn 'AoE', 'UTC-12', 'GMT+02', 'UTC' or 'Europe/London' into a tzinfo."""
    text = str(name or "AoE").strip()
    text = TZ_ALIASES.get(text.upper(), text)
    m = re.fullmatch(r"(?:UTC|GMT)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?", text, re.IGNORECASE)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        delta = timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))
        return timezone(sign * delta)
    if text.upper() in ("UTC", "GMT", "Z"):
        return timezone.utc
    try:
        return ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError):
        print(f"  warning: unknown time zone {name!r}, using AoE", file=sys.stderr)
        return timezone(timedelta(hours=-12))


def to_utc(value, tz_name) -> str | None:
    """Return the deadline as an ISO 8601 UTC string, or None when it is not set (e.g. 'TBA')."""
    if value is None:
        return None
    if isinstance(value, datetime):
        local = value
    elif isinstance(value, date):
        local = datetime(value.year, value.month, value.day, 23, 59, 59)
    else:
        text = str(value).strip()
        local = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                local = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if local is None:
            return None
        if len(text) == 10:  # date only: the deadline is the end of that day
            local = local.replace(hour=23, minute=59, second=59)
    if local.tzinfo is None:
        local = local.replace(tzinfo=parse_tz(tz_name))
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tz_label(tz_name) -> str:
    text = str(tz_name or "AoE").strip()
    return "AoE" if text.upper() in ("AOE", "UTC-12", "GMT-12") else text


def as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def iso_day(d) -> str | None:
    return d.isoformat() if d else None


def event_dates(conf: dict) -> str:
    """Make a short, clear date range like 'Jun 28 - Jul 2, 2027'."""
    start, end = as_date(conf.get("start")), as_date(conf.get("end"))
    if start and end:
        if start == end:
            return f"{start:%b} {start.day}, {start.year}"
        if start.year != end.year:
            return f"{start:%b} {start.day}, {start.year} - {end:%b} {end.day}, {end.year}"
        if start.month == end.month:
            return f"{start:%b} {start.day} - {end.day}, {end.year}"
        return f"{start:%b} {start.day} - {end:%b} {end.day}, {end.year}"
    return str(conf.get("date") or "To be announced").strip()


def _plain(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


KNOWN_FIELDS = {_plain(v): v for v in FIELD_CODES.values()}


def label_from_tag(tag: str) -> str:
    """'human-computer-interaction' -> 'Human-Computer Interaction', 'web mining' -> 'Web Mining'."""
    text = str(tag).strip()
    if text.upper() in FIELD_CODES:
        return FIELD_CODES[text.upper()]
    if _plain(text) in KNOWN_FIELDS:
        return KNOWN_FIELDS[_plain(text)]
    words = [w for w in re.split(r"[-_\s]+", text) if w]
    out = []
    for i, w in enumerate(words):
        if w.lower() == "ml":  # spell out, e.g. "ML for Health" -> "Machine Learning for Health"
            out.append("Machine Learning")
        elif w.lower() in UPPER_WORDS:
            out.append(w.upper())
        elif i and w.lower() in SMALL_WORDS:
            out.append(w.lower())
        else:
            out.append(w[0].upper() + w[1:].lower())
    return " ".join(out)


def fields_from(conf: dict) -> list[str]:
    raw = conf.get("sub") or conf.get("tags") or conf.get("field") or []
    if isinstance(raw, str):
        raw = [raw]
    fields = []
    for item in raw:
        name = label_from_tag(item)
        if name and name not in fields:
            fields.append(name)
    return fields or ["Other"]


def location(conf: dict) -> str:
    if conf.get("place"):
        return str(conf["place"]).strip()
    parts = [str(conf.get(k)).strip() for k in ("city", "country") if conf.get(k)]
    return ", ".join(parts) or "To be announced"


def name_with_year(title, year) -> str:
    """'AfricaNLP', 2027 -> 'AfricaNLP 2027'; a title that already has the year is left as it is."""
    title = str(title or "").strip()
    if year and re.search(rf"\b{year}\b", title):
        return title
    return f"{title} {year or ''}".strip()


def make_record(conf: dict, *, paper, abstract, source: str, africa: bool, sub_type: str,
                kind: str = "Conference") -> dict:
    """paper and abstract are (date, timezone) pairs or None."""
    deadline_utc = to_utc(*paper) if paper else None
    record = {
        "id": str(conf.get("id") or f"{conf.get('title')}{conf.get('year')}").lower(),
        "name": name_with_year(conf.get("title"), conf.get("year")),
        "year": int(conf.get("year") or 0),
        "full_name": str(conf.get("full_name") or "").strip(),
        "submission_type": sub_type,
        "deadline_utc": deadline_utc,
        "deadline_timezone": tz_label(paper[1]) if paper and deadline_utc else None,
        "abstract_deadline_utc": to_utc(*abstract) if abstract else None,
        "deadline_source": source,
        "openreview_deadline_utc": None,
        "openreview_link": None,
        "upcoming": False,
        "expected_deadline_utc": None,
        "last_deadline_utc": None,
        "last_edition": None,
        "fields": fields_from(conf),
        "event_dates": event_dates(conf),
        "event_end": iso_day(as_date(conf.get("end")) or as_date(conf.get("start"))),
        "location": location(conf),
        "link": str(conf.get("link") or "").strip(),
        "africa": africa,
        "source": source,
        "type": kind,
        "parent": str(conf.get("parent") or "").strip() or None,
        # Hand-kept entries only: "Check date" when the date is not confirmed,
        # and "yearly" to show "Check next year's date" once the deadline passes.
        "check_date": bool(conf.get("check_date")),
        "recurring": str(conf.get("recurring") or "").strip().lower() or None,
        "note": str(conf.get("note") or "").strip() or None,
    }
    return record


# ---------- ai-deadlines readers ----------

def read_paperswithcode(raw: bytes) -> list[dict]:
    """One flat YAML list with 'deadline', 'abstract_deadline' and 'timezone'."""
    out = []
    for conf in yaml.safe_load(raw) or []:
        tz = conf.get("timezone")
        abstract = (conf["abstract_deadline"], tz) if conf.get("abstract_deadline") else None
        out.append(make_record(conf, paper=(conf.get("deadline"), tz), abstract=abstract,
                               source="ai-deadlines", africa=False, sub_type="Full paper"))
    return out


def read_huggingface(raw: bytes) -> list[dict]:
    """A tarball with one YAML file per conference series in src/data/conferences/."""
    out = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not (member.isfile() and "/src/data/conferences/" in member.name and member.name.endswith((".yml", ".yaml"))):
                continue
            for conf in yaml.safe_load(tar.extractfile(member)) or []:
                top_tz = conf.get("timezone")
                paper = abstract = None
                for d in conf.get("deadlines") or []:
                    kind = str(d.get("type", "")).lower()
                    pair = (d.get("date"), d.get("timezone") or top_tz)
                    if kind in ("paper", "submission") and paper is None:
                        paper = pair
                    elif kind == "abstract" and abstract is None:
                        abstract = pair
                if paper is None and conf.get("deadline"):  # older entries use flat fields
                    paper = (conf["deadline"], top_tz)
                if abstract is None and conf.get("abstract_deadline"):
                    abstract = (conf["abstract_deadline"], top_tz)
                if paper is None and abstract is not None:
                    paper, abstract, sub_type = abstract, None, "Abstract"
                else:
                    sub_type = "Full paper"
                out.append(make_record(conf, paper=paper, abstract=abstract,
                                       source="ai-deadlines", africa=False, sub_type=sub_type))
    return out


def read_api(raw: bytes) -> list[dict]:
    """JSON from paperswithcode.co/api/v1/conferences/deadlines.

    Deadlines are already in UTC ("deadline_at"); "timezone" is the organisers' own zone."""
    data = json.loads(raw)
    items = data.get("results") or []
    if data.get("count") and data["count"] > len(items):
        print(f"  warning: the API says {data['count']} conferences but sent {len(items)}", file=sys.stderr)
    names = full_names_from_repo()
    out = []
    for item in items:
        title = str(item.get("short_name") or item.get("name") or "").strip()
        year = item.get("year")
        paper = abstract = None
        for d in item.get("deadlines") or []:
            kind = str(d.get("type", "")).lower()
            when = d.get("deadline_at")
            if not when:
                continue
            pair = (datetime.fromisoformat(str(when).replace("Z", "+00:00")), d.get("timezone") or "UTC")
            if kind in ("paper", "submission") and paper is None:
                paper = pair
            elif kind == "abstract" and abstract is None:
                abstract = pair
        sub_type = "Full paper"
        if paper is None and abstract is not None:
            paper, abstract, sub_type = abstract, None, "Abstract"
        conf = {
            "id": item.get("slug"),
            "title": title,
            "year": year,
            "full_name": names.get((title.lower(), year)) or names.get(title.lower()) or "",
            "link": item.get("url"),
            "start": item.get("start_date"),
            "end": item.get("end_date"),
            "place": item.get("location"),
            "tags": item.get("tags") or [],
        }
        out.append(make_record(conf, paper=paper, abstract=abstract, source="Papers with Code", africa=False, sub_type=sub_type))
    return out


def full_names_from_repo() -> dict:
    """Full conference names from the huggingface/ai-deadlines repository (best effort)."""
    try:
        raw = fetch(SOURCES["huggingface"]["url"])
    except Exception as err:  # names are nice to have, not needed
        print(f"  warning: could not read full names ({err})", file=sys.stderr)
        return {}
    names = {}
    for rec in read_huggingface(raw):
        if rec["full_name"]:
            title = rec["name"].removesuffix(str(rec["year"])).strip().lower()
            names[(title, rec["year"])] = rec["full_name"]
            names.setdefault(title, rec["full_name"])
    return names


def latest_editions(records: list[dict]) -> list[dict]:
    """Keep only the newest year of each conference, so old editions do not fill the page.

    Also note how often it happens ("cycle": 1 = every year, 2 = every two years),
    from the gap between its two newest editions."""
    years: dict[str, set[int]] = {}
    best: dict[str, dict] = {}
    for rec in records:
        key = rec["name"].removesuffix(str(rec["year"])).strip().lower()
        years.setdefault(key, set()).add(rec["year"])
        if key not in best or rec["year"] > best[key]["year"]:
            best[key] = rec
    for key, rec in best.items():
        ys = sorted(years[key], reverse=True)
        gap = ys[0] - ys[1] if len(ys) > 1 else 1
        rec["cycle"] = KNOWN_CYCLE.get(orv.plain(key), gap if gap in (1, 2) else 1)
    return list(best.values())


def read_manual(path: Path, *, source: str, default_type: str, africa: bool | None) -> list[dict]:
    """Read a hand-edited YAML list (same fields as data/african_venues.yml).

    africa=None means each entry says it with "africa: true"; otherwise all entries get that value.
    An entry can set "type" (Conference, Workshop, ...) and "parent" (the conference a workshop belongs to)."""
    if not path.exists():
        return []
    out = []
    for conf in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
        kind = str(conf.get("type") or default_type)
        if kind not in TYPES:
            print(f"  warning: unknown type {kind!r} for {conf.get('title')} in {path.name}", file=sys.stderr)
        out.append(make_record(
            conf,
            paper=(conf.get("deadline"), conf.get("timezone")),
            abstract=(conf["abstract_deadline"], conf.get("timezone")) if conf.get("abstract_deadline") else None,
            source=source,
            africa=bool(conf.get("africa")) if africa is None else africa,
            sub_type=str(conf.get("submission_type") or "Full paper"),
            kind=kind,
        ))
    return out


def read_african(path: Path) -> list[dict]:
    return read_manual(path, source="African venues list", default_type="Conference", africa=True)


# ---------- OpenReview ----------

def or_event_dates(info: dict) -> str:
    return f"Starts {info['start']:%b} {info['start'].day}, {info['start'].year}" if info.get("start") else "To be announced"


def record_from_openreview(info: dict, *, title: str, year: int, fields: list[str], africa: bool) -> dict:
    deadline = info["deadline_utc"]
    full_name = info["title"] if plain_differs(info["title"], title) else ""
    return {
        "id": info["id"].lower(),
        "name": f"{title} {year}",
        "year": year,
        "full_name": full_name,
        "submission_type": "Paper (OpenReview)",
        "deadline_utc": deadline,
        "deadline_timezone": "AoE" if orv.looks_like_aoe(deadline) else "UTC",
        "abstract_deadline_utc": None,
        "deadline_source": "OpenReview",
        "openreview_deadline_utc": deadline,
        "openreview_link": info["link"],
        "upcoming": False,
        "expected_deadline_utc": None,
        "last_deadline_utc": None,
        "last_edition": None,
        "fields": fields or ["Other"],
        "event_dates": or_event_dates(info),
        "event_end": iso_day(info.get("start")),
        "location": info["location"] or "To be announced",
        "link": info["website"] or info["link"],
        "africa": africa,
        "source": "OpenReview",
        "type": "Workshop" if "/Workshop/" in info["id"] else "Conference",
        "parent": parent_from_id(info["id"]),
        "check_date": False,
        "recurring": None,
        "note": None,
    }


def parent_from_id(venue_id: str) -> str | None:
    """'NeurIPS.cc/2026/Workshop/Africa_in_AI' -> 'NeurIPS 2026'."""
    if "/Workshop/" not in venue_id:
        return None
    short, year, _ = orv.split_venue_id(venue_id.split("/Workshop/")[0] + "/Conference")
    return f"{short} {year}" if short and year else None


def plain_differs(a: str, b: str) -> bool:
    return bool(a) and orv.plain(a) != orv.plain(b)


def add_openreview(records: list[dict], venues_file: Path, api, active: list[str]) -> list[dict]:
    """Add OpenReview dates to matching conferences, and add the extra venues from venues_file."""
    index = orv.conference_index(active)
    by_key = {orv.plain(r["name"].removesuffix(str(r["year"]))): r for r in records}
    matched = added = 0

    # 1. Conferences already in the ai-deadlines list.
    for key, rec in list(by_key.items()):
        if rec["year"] == 0 or key not in index:
            continue
        year, vid = index[key][0]  # newest edition on OpenReview
        if year < rec["year"]:
            continue
        info = api.venue(vid)
        if not info:
            continue
        if year == rec["year"]:
            rec["openreview_deadline_utc"] = info["deadline_utc"]
            rec["openreview_link"] = info["link"]
            if rec["deadline_utc"] is None:  # ai-deadlines has no date yet
                rec["deadline_utc"] = info["deadline_utc"]
                rec["deadline_timezone"] = "AoE" if orv.looks_like_aoe(info["deadline_utc"]) else "UTC"
                rec["deadline_source"] = "OpenReview"
                rec["submission_type"] = "Paper (OpenReview)"
            if not rec["full_name"] and plain_differs(info["title"], rec["name"]):
                rec["full_name"] = info["title"]
            matched += 1
        else:  # OpenReview already has the next edition: show that one instead
            title = rec["name"].removesuffix(str(rec["year"])).strip()
            new = record_from_openreview(info, title=title, year=year, fields=rec["fields"], africa=rec["africa"])
            records[records.index(rec)] = new
            by_key[key] = new
            added += 1

    # 2. Extra venues kept by hand.
    extra = yaml.safe_load(venues_file.read_text(encoding="utf-8")) if venues_file.exists() else []
    for item in extra or []:
        vid = orv.newest_matching(active, str(item.get("openreview", "")))
        title = str(item.get("title") or "").strip()
        if not vid or not title:
            continue
        _, year, _ = orv.split_venue_id(vid)
        key = orv.plain(title)
        if key in by_key and by_key[key]["year"] >= year:
            continue  # already on the page from ai-deadlines
        info = api.venue(vid)
        if not info:
            continue
        fields = fields_from({"field": item.get("field")})
        new = record_from_openreview(info, title=title, year=year, fields=fields, africa=bool(item.get("africa")))
        if key in by_key:
            records[records.index(by_key[key])] = new
        else:
            records.append(new)
        by_key[key] = new
        added += 1

        new["cycle"] = int(item.get("cycle") or KNOWN_CYCLE.get(orv.plain(title), 1))
        new["_template"] = str(item.get("openreview", ""))

    print(f"  OpenReview: {matched} dates added to listed conferences, {added} venues added")
    return records


# ---------- Workshops on OpenReview ----------

def add_workshops(records: list[dict], api, active: list[str]) -> tuple[list[dict], bool]:
    """Add the OpenReview workshops of conferences on the tracker whose event is still ahead.

    Returns (records, ok). ok is False when OpenReview could not be read for some conference."""
    today = datetime.now(timezone.utc).date()
    by_key = {}
    for rec in records:
        if rec.get("type", "Conference") == "Conference" and rec["year"]:
            by_key[(orv.plain(rec["name"].removesuffix(str(rec["year"]))), rec["year"])] = rec
    parents = {}
    for vid in active:
        if "/Workshop/" not in vid:
            continue
        prefix = vid.split("/Workshop/")[0]
        short, year, _ = orv.split_venue_id(prefix + "/Conference")
        rec = by_key.get((orv.plain(short or ""), year))
        if rec and not (rec["deadline_utc"] and event_is_over(rec, today)):
            parents[prefix] = rec
    known = {r["id"] for r in records}
    added = no_form = 0
    ok = True
    for prefix, conf in sorted(parents.items()):
        result = api.workshops(prefix)
        if result is None:
            ok = False
            orv.warn(f"could not read workshops of {conf['name']}")
            continue
        found, missing = result
        no_form += missing
        for info in found:
            if info["id"].lower() in known:
                continue  # already listed, e.g. from data/openreview_venues.yml
            short = info["id"].split("/Workshop/")[-1].replace("_", " ")
            rec = record_from_openreview(info, title=short, year=conf["year"], fields=conf["fields"],
                                         africa="africa" in (info["id"] + info["title"]).lower())
            rec["name"] = short  # the parent conference already shows the year
            rec["full_name"] = re.sub(rf"\s*{conf['year']}$", "", info["title"]) if info["title"] else ""
            rec["type"] = "Workshop"
            rec["parent"] = conf["name"]
            rec["submission_type"] = "Workshop paper"
            if not info.get("location"):
                rec["location"] = conf["location"]
            rec["_scanned"] = True
            if rec["deadline_utc"] and event_is_over(rec, today):
                continue
            records.append(rec)
            known.add(rec["id"])
            added += 1
    print(f"  Workshops: {added} added from {len(parents)} conferences ({no_form} have no submission form yet)")
    return records, ok


def keep_last_good(records: list[dict], old: dict | None) -> list[dict]:
    """OpenReview failed for some calls: bring back what it gave last time instead of dropping it."""
    if not old:
        return records
    by_id = {r["id"]: r for r in records}
    names = {(r["name"].lower(), r.get("parent")) for r in records}
    kept = 0
    for prev in old.get("conferences") or []:
        cur = by_id.get(prev["id"])
        if cur is None and prev.get("source") == "OpenReview" and (prev["name"].lower(), prev.get("parent")) not in names:
            prev = dict(prev)
            if prev.get("type") == "Workshop" and prev.get("parent"):
                prev["_scanned"] = True
            records.append(prev)
            kept += 1
        elif cur is not None and not cur.get("openreview_deadline_utc") and prev.get("openreview_deadline_utc"):
            cur["openreview_deadline_utc"] = prev["openreview_deadline_utc"]
            cur["openreview_link"] = prev.get("openreview_link")
            kept += 1
    print(f"  OpenReview had errors: kept {kept} entries from the last good data")
    return records


# ---------- Summer schools (awesome-mlss) and community talks (Python Deadlines) ----------
# Both are MIT-licensed; see data/THIRD_PARTY_NOTICES.md.

EXTRA_SOURCES = {
    "awesome-mlss": {
        "page": "https://awesome-mlss.com",
        "data": "https://raw.githubusercontent.com/sshkhr/awesome-mlss/master/site/_data/summerschools.yml",
        "types": "https://raw.githubusercontent.com/sshkhr/awesome-mlss/master/site/_data/types.yml",
    },
    "Python Deadlines": {
        "page": "https://pythondeadlin.es",
        "data": "https://raw.githubusercontent.com/jesperdramsch/python-deadlines/main/_data/conferences.yml",
        "types": "https://raw.githubusercontent.com/jesperdramsch/python-deadlines/main/_data/types.yml",
    },
}

# Short field codes from those lists, written out in full (these win over the lists' own names).
EXTRA_FIELD_NAMES = {
    "GenAI": "Generative AI",
    "HW": "Machine Learning Hardware",
    "AI4Games": "AI for Games",
}


def field_names(types_url: str) -> dict:
    """Code -> full field name, from a source's types.yml (best effort)."""
    try:
        types = yaml.safe_load(fetch(types_url)) or []
        names = {str(t["sub"]): str(t["name"]) for t in types if t.get("sub") and t.get("name")}
    except Exception as err:
        print(f"  warning: could not read field names ({err})", file=sys.stderr)
        names = {}
    names.update(FIELD_CODES)
    names.update(EXTRA_FIELD_NAMES)
    return names


def codes_to_fields(sub, names: dict) -> list[str]:
    if isinstance(sub, str):
        sub = [c.strip() for c in sub.split(",")]
    return [names.get(str(c), str(c)) for c in (sub or []) if str(c).strip()]


def read_awesome_mlss() -> list[dict]:
    """Summer schools from awesome-mlss. Keeps the newest edition of each school.

    A school whose event is over (or that has no deadline) becomes a "Check date" card for its
    next edition, showing the last deadline, so volunteers know to look for the new date."""
    src = EXTRA_SOURCES["awesome-mlss"]
    items = yaml.safe_load(fetch(src["data"])) or []
    names = field_names(src["types"])
    today = datetime.now(timezone.utc).date()
    newest: dict[str, dict] = {}
    for item in items:
        year = int(item.get("year") or 0)
        series = orv.plain(item.get("series") or re.sub(r"\b20\d\d\b", "", str(item.get("title", ""))))
        if series not in newest or year > int(newest[series].get("year") or 0):
            newest[series] = item
    out = []
    for item in newest.values():
        year = int(item.get("year") or 0)
        title = str(item.get("title") or "").strip()
        conf = {
            "id": f"mlss-{item.get('id') or orv.plain(title)}",
            "title": title, "year": year,
            "full_name": item.get("full_name") or "",
            "link": item.get("link"),
            "start": item.get("start"), "end": item.get("end"), "date": item.get("date"),
            "place": item.get("place"),
            "field": codes_to_fields(item.get("sub"), names),
        }
        rec = make_record(conf, paper=(item.get("deadline"), item.get("timezone")), abstract=None,
                          source="awesome-mlss", africa=False, sub_type="Application", kind="Summer school")
        if str(year) in title:  # titles like "ACVSS 2026 - African Computer Vision Summer School"
            rec["name"] = title
        if not rec["deadline_utc"] or event_is_over(rec, today):
            next_year = year + 1 if year else 0
            last = rec["deadline_utc"]
            rec.update({
                "name": re.sub(rf"\b{year}\b", str(next_year), rec["name"]) if year else rec["name"],
                "full_name": " ".join(re.sub(rf"\b{year}\b", "", rec["full_name"]).split()) if year else rec["full_name"],
                "year": next_year,
                "deadline_utc": None, "deadline_timezone": None,
                "check_date": True,
                "last_deadline_utc": last,
                "last_edition": f"{title} {year}".strip() if str(year) not in title else title,
                "expected_deadline_utc": add_years(last, 1) if last else None,
                "event_dates": "To be announced",
                "event_end": None,
                "location": f"{rec['location']} (last edition)" if rec["location"] != "To be announced" else rec["location"],
            })
        out.append(rec)
    return out


def read_python_deadlines() -> list[dict]:
    """Calls for talks from Python Deadlines (PyCon and other Python community events).

    No time zone in the data means AoE (Anywhere on Earth). An extended deadline counts as the deadline.
    Events that are over are left out; Python Deadlines adds the next year's event itself."""
    src = EXTRA_SOURCES["Python Deadlines"]
    items = yaml.safe_load(fetch(src["data"])) or []
    names = field_names(src["types"])
    today = datetime.now(timezone.utc).date()
    out = []
    for item in items:
        tz = item.get("timezone") or "AoE"
        cfp, ext = item.get("cfp"), item.get("cfp_ext")
        conf = {
            "id": f"pyd-{orv.plain(item.get('conference', ''))}{item.get('year')}",
            "title": str(item.get("conference") or "").strip(),
            "year": item.get("year"),
            "full_name": item.get("alt_name") or "",
            "link": item.get("cfp_link") or item.get("link"),
            "start": item.get("start"), "end": item.get("end"),
            "place": item.get("place"),
            "field": codes_to_fields(item.get("sub"), names),
            "note": f"Deadline extended (first deadline was {str(cfp)[:10]})." if ext and str(ext) > str(cfp) else None,
        }
        deadline = ext if ext and str(ext) > str(cfp) else cfp
        rec = make_record(conf, paper=(deadline, tz), abstract=None, source="Python Deadlines",
                          africa="africa" in conf["title"].lower(), sub_type="Talk proposal", kind="Community talk")
        if rec["deadline_utc"] and event_is_over(rec, today):
            continue
        out.append(rec)
    return out


def load_source(label: str, reader, old: dict | None) -> tuple[list[dict], bool]:
    """Run one source. If it fails, keep what it gave last time, so the other sources still load."""
    try:
        recs = reader()
        print(f"  {len(recs)} entries from {label}")
        return recs, True
    except Exception as err:
        kept = [dict(r) for r in (old or {}).get("conferences", []) if r.get("source") == label]
        print(f"  warning: {label} failed ({err}); kept {len(kept)} entries from the last good data", file=sys.stderr)
        return kept, bool(kept)


def drop_duplicates(records: list[dict]) -> list[dict]:
    """One card per name (and parent conference). A real deadline beats an "Upcoming" guess."""
    best: dict[tuple, dict] = {}
    for rec in records:
        key = (rec["name"].lower(), rec.get("parent"))
        if key not in best or (best[key].get("upcoming") and not rec.get("upcoming")):
            best[key] = rec
    kept = set(map(id, best.values()))
    return [r for r in records if id(r) in kept]


# ---------- Upcoming editions ----------

def add_years(iso: str, years: int) -> str:
    t = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    try:
        t = t.replace(year=t.year + years)
    except ValueError:  # 29 February
        t = t.replace(year=t.year + years, day=28)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def event_is_over(rec: dict, today: date) -> bool:
    if rec.get("event_end"):
        end = date.fromisoformat(rec["event_end"])
        # Only a start date (OpenReview): allow a week for the event itself.
        return end + (timedelta(days=7) if rec["source"] == "OpenReview" else timedelta()) < today
    # No event dates: workshops usually happen within about four months of their deadline.
    deadline = datetime.strptime(rec["deadline_utc"], "%Y-%m-%dT%H:%M:%SZ").date()
    return deadline + timedelta(days=120) < today


def add_upcoming(records: list[dict], api, active: list[str]) -> list[dict]:
    """Swap finished conferences for their next edition, with the deadline marked as not announced.

    The card shows last edition's deadline and an expected month (last deadline + one cycle).
    If OpenReview already lists the next edition, its name, place and dates are used."""
    today = datetime.now(timezone.utc).date()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index = orv.conference_index(active) if active else {}
    out, made = [], 0
    for rec in records:
        if rec.get("_scanned"):  # workshops found on OpenReview: drop them once the event is over
            if not (rec["deadline_utc"] and event_is_over(rec, today)):
                out.append(rec)
            continue
        if not rec["deadline_utc"] or rec["deadline_utc"] > now_iso or rec["year"] == 0 or not event_is_over(rec, today):
            out.append(rec)
            continue
        cycle = rec.get("cycle", 1)
        year = rec["year"] + cycle
        title = rec["name"].removesuffix(str(rec["year"])).strip()
        new = dict(rec)
        new.update({
            "id": f"{orv.plain(title)}{year}",
            "name": f"{title} {year}",
            "year": year,
            "submission_type": "Paper",
            "deadline_utc": None,
            "deadline_timezone": None,
            "abstract_deadline_utc": None,
            "deadline_source": "Expected from last edition",
            "openreview_deadline_utc": None,
            "openreview_link": None,
            "upcoming": True,
            "expected_deadline_utc": add_years(rec["deadline_utc"], cycle),
            "last_deadline_utc": rec["deadline_utc"],
            "last_edition": rec["name"],
            "event_dates": "To be announced",
            "event_end": None,
            "location": "To be announced",
            "parent": re.sub(r"\d{4}$", str(year), rec["parent"]) if rec.get("parent") else None,
        })
        # Does OpenReview already list the next edition (even without a submission form yet)?
        vid = None
        if rec.get("_template"):
            vid = orv.newest_matching(active, rec["_template"]) if active else None
            if vid and orv.split_venue_id(vid)[1] != year:
                vid = None
        else:
            for y, v in index.get(orv.plain(title), []):
                if y == year:
                    vid = v
        if vid and api:
            info = api.details(vid)
            if info.get("title") and plain_differs(info["title"], title):
                new["full_name"] = info["title"]
            new["location"] = info.get("location") or new["location"]
            new["event_dates"] = or_event_dates(info)
            new["link"] = info.get("website") or new["link"]
            new["openreview_link"] = info["link"]
        out.append(new)
        made += 1
    print(f"  {made} finished conferences replaced by their next edition (deadline not announced yet)")
    return out


AFRICAN_COUNTRIES = {
    "algeria", "angola", "benin", "botswana", "burkina faso", "burundi", "cabo verde", "cape verde", "cameroon",
    "central african republic", "chad", "comoros", "congo", "côte d'ivoire", "cote d'ivoire", "ivory coast",
    "djibouti", "egypt", "equatorial guinea", "eritrea", "eswatini", "ethiopia", "gabon", "gambia", "ghana",
    "guinea", "guinea-bissau", "kenya", "lesotho", "liberia", "libya", "madagascar", "malawi", "mali",
    "mauritania", "mauritius", "morocco", "mozambique", "namibia", "niger", "nigeria", "rwanda",
    "são tomé and príncipe", "sao tome and principe", "senegal", "seychelles", "sierra leone", "somalia",
    "south africa", "south sudan", "sudan", "tanzania", "togo", "tunisia", "uganda", "zambia", "zimbabwe",
}


# Characters you cannot see that sometimes come in with copied text,
# such as the zero-width non-joiner in OpenReview's "C\u200conference".
INVISIBLE = re.compile("[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")


def clean_text(rec: dict) -> None:
    """Remove invisible characters and extra spaces from every text field."""
    for key, value in rec.items():
        if isinstance(value, str):
            rec[key] = " ".join(INVISIBLE.sub("", value).split())


def apply_full_names(records: list[dict], path: Path) -> None:
    """Fill in full names from the hand-kept file (it wins over the sources)."""
    if not path.exists():
        return
    names = {str(k).strip().lower(): str(v).strip() for k, v in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).items()}
    for rec in records:
        title = rec["name"].removesuffix(str(rec["year"])).strip().lower()
        if title in names:
            rec["full_name"] = names[title]


def held_in_africa(location: str) -> bool:
    """True when the last part of 'City, Country' is an African country."""
    country = re.sub(r"\s*\(.*?\)", "", str(location or "")).split(",")[-1].strip().lower()
    return country in AFRICAN_COUNTRIES


def sort_key(rec: dict):
    # Same order as the page before it knows the time: by deadline, unknown deadlines last.
    return (rec["deadline_utc"] is None, rec["deadline_utc"] or "", rec["name"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=sorted(SOURCES), default="api")
    ap.add_argument("--no-openreview", action="store_true", help="do not check OpenReview")
    ap.add_argument("--openreview-venues", type=Path, default=DEFAULT_OPENREVIEW,
                    help="extra OpenReview venues to show (YAML)")
    ap.add_argument("--african", type=Path, default=DEFAULT_AFRICAN, help="hand-kept African venues (YAML)")
    ap.add_argument("--names", type=Path, default=DEFAULT_NAMES, help="hand-kept full names (YAML)")
    ap.add_argument("--workshops", type=Path, default=DEFAULT_WORKSHOPS, help="hand-kept workshops (YAML)")
    ap.add_argument("--schools", type=Path, default=DEFAULT_SCHOOLS, help="hand-kept summer schools (YAML)")
    ap.add_argument("--approved", type=Path, default=DEFAULT_APPROVED, help="items approved by volunteers (YAML)")
    ap.add_argument("--pending", type=Path, default=DEFAULT_PENDING, help="review list to update (YAML)")
    ap.add_argument("--no-review", action="store_true", help="do not update the review list")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    old = None
    if args.out.exists():
        try:
            old = json.loads(args.out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = None

    src = SOURCES[args.source]
    print(f"Downloading {src['label']} ...")
    reader = {"api": read_api, "paperswithcode": read_paperswithcode, "huggingface": read_huggingface}[args.source]
    main_label = {"api": "Papers with Code"}.get(args.source, "ai-deadlines")
    try:
        records = latest_editions(reader(fetch(src["url"])))
        print(f"  {len(records)} conferences (newest edition of each)")
    except Exception as err:
        # Keep last time's conferences (they skip the steps below, which they already went through).
        records = [dict(r) for r in (old or {}).get("conferences", []) if r.get("source") == main_label]
        print(f"  warning: {src['label']} failed ({err}); kept {len(records)} entries from the last good data",
              file=sys.stderr)

    sources = [{"label": src["label"], "url": src["page"]}]
    api, active = None, []
    if not args.no_openreview:
        print("Checking OpenReview ...")
        api = orv.OpenReview()
        active = api.active_venues()
        if active:
            records = add_openreview(records, args.openreview_venues, api, active)
            records, workshops_ok = add_workshops(records, api, active)
            sources.append({"label": "OpenReview", "url": "https://openreview.net/venues"})
        else:
            workshops_ok = False
            orv.warn("could not read the OpenReview venue list")
        if api.failures or not workshops_ok:
            records = keep_last_good(records, old)
            if not active and old and any(s.get("label") == "OpenReview" for s in old.get("sources", [])):
                sources.append({"label": "OpenReview", "url": "https://openreview.net/venues"})
    records = add_upcoming(records, api, active)
    if api:
        print(f"  OpenReview: {api.calls} calls, {api.failures} failed, {api.timeouts} timed out, "
              f"{api.retries} rate-limit retries ({api.waited / 60:.1f} minutes waiting); "
              f"answers took {api.seconds / 60:.1f} minutes in total")

    print("Reading summer schools and community talks ...")
    for label, reader_fn in (("awesome-mlss", read_awesome_mlss), ("Python Deadlines", read_python_deadlines)):
        recs, ok = load_source(label, reader_fn, old)
        records += recs
        if ok:
            sources.append({"label": label, "url": EXTRA_SOURCES[label]["page"]})
    records = drop_duplicates(records)
    for rec in records:  # working values, not needed on the page
        rec.pop("cycle", None)
        rec.pop("_template", None)
        rec.pop("_scanned", None)
        if held_in_africa(rec["location"]):
            rec["africa"] = True

    african = read_african(args.african)
    print(f"  {len(african)} African venues from {args.african.name}")
    workshops = read_manual(args.workshops, source="Workshops list", default_type="Workshop", africa=None)
    print(f"  {len(workshops)} workshops from {args.workshops.name}")
    schools = read_manual(args.schools, source="Summer schools list", default_type="Summer school", africa=None)
    print(f"  {len(schools)} summer schools from {args.schools.name}")
    approved = read_manual(args.approved, source="Approved by volunteers", default_type="Conference", africa=None)
    print(f"  {len(approved)} items from {args.approved.name}")
    manual = african + workshops + schools + approved
    # A hand-kept entry replaces an entry from the sources with the same name.
    names = {r["name"].lower() for r in manual}
    records = [r for r in records if r["name"].lower() not in names] + manual
    apply_full_names(records, args.names)
    for rec in records:
        clean_text(rec)
    records.sort(key=sort_key)

    payload = {
        "sources": sources,
        "conferences": records,
    }

    counts = {t: sum(1 for r in records if r["type"] == t) for t in TYPES}
    print("  By type: " + ", ".join(f"{t}: {n}" for t, n in counts.items()))

    # Review list (data/review/pending.yaml): never shown on the page, so a failure here
    # must not stop the tracker data from being written.
    if not args.no_review:
        print("Updating the review list ...")
        try:
            result = review.update_review(args.pending, args.approved, records, held_in_africa)
            print(f"  {review.SOURCE}: " + ", ".join(f"{k}: {v}" for k, v in result.items()))
        except Exception as err:
            review.warn(f"{review.SOURCE} failed ({err}); review list left as it is")

    # Only touch the file when the data changed, so the daily job does not make empty commits.
    if old and {k: v for k, v in old.items() if k != "updated_at"} == payload:
        print(f"No changes; {args.out} left as it is.")
        return 0

    payload = {"updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **payload}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} entries to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
