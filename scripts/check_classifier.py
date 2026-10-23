"""Check whether USPSA classifiers have been shot recently by nearby clubs.

Scrapes https://uspsa.org/classifiers-by-club for each club (behind Cloudflare,
so curl_cffi browser impersonation is used: pip install curl_cffi).

Examples:
  python scripts/check_classifier.py 26-03 99-08     # who shot these, and when
  python scripts/check_classifier.py 26-03 --months 6
  python scripts/check_classifier.py --recent        # everything shot in the window
  python scripts/check_classifier.py --unshot        # active classifiers nobody shot in the window
"""
import argparse
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from curl_cffi import requests

ROOT = Path(__file__).resolve().parent.parent
CLASSIFIERS_JSON = ROOT / "data" / "classifiers.json"
URL = "https://uspsa.org/classifiers-by-club?action=show&club={club}"
DEFAULT_CLUBS = ["NW01", "NW02", "NW05", "NW07", "NW15"]

ID_RE = re.compile(r"^\d{2}-\d{2}$")
CLUB_NAME_RE = re.compile(r"<h4>\s*Classifiers shot at\s*(.*?)\s*</h4>", re.S)
ROW_RE = re.compile(
    r"<tr>\s*<td[^>]*>\s*(?P<id>[^<]*?)\s*</td>\s*<td[^>]*>\s*(?P<name>[^<]*?)\s*</td>\s*"
    r"<td[^>]*>\s*(?:<a[^>]*href=\"(?P<href>[^\"]*)\"[^>]*>)?\s*(?P<date>\d{1,2}/\d{1,2}/\d{2,4})",
    re.S,
)


def parse_date(s: str) -> date:
    fmt = "%m/%d/%y" if len(s.rsplit("/", 1)[1]) == 2 else "%m/%d/%Y"
    return datetime.strptime(s, fmt).date()


def parse_club_page(club: str, page: str):
    m = CLUB_NAME_RE.search(page)
    name = html.unescape(m.group(1)) if m else club
    shots = []
    for r in ROW_RE.finditer(page):
        href = r.group("href")
        shots.append({
            "id": html.unescape(r.group("id")).strip(),
            "date": parse_date(r.group("date")),
            "match_url": f"https://uspsa.org/{href}" if href else None,
        })
    return name, shots


def fetch_club(session, club: str):
    resp = session.get(URL.format(club=club), timeout=30)
    resp.raise_for_status()
    if "Classifier Summary" not in resp.text:
        raise RuntimeError(f"{club}: unexpected page (Cloudflare challenge?)")
    return parse_club_page(club, resp.text)


def fetch_all(clubs):
    session = requests.Session(impersonate="chrome")
    with ThreadPoolExecutor(max_workers=len(clubs)) as pool:
        results = list(pool.map(lambda c: fetch_club(session, c), clubs))
    return {club: {"name": name, "shots": shots} for club, (name, shots) in zip(clubs, results)}


def load_active_classifiers():
    if not CLASSIFIERS_JSON.exists():
        return {}
    return {c["id"]: c for c in json.loads(CLASSIFIERS_JSON.read_text())}


def fmt_date(d: date) -> str:
    return d.isoformat()


def report_ids(ids, data, cutoff, active):
    any_recent = False
    for cid in ids:
        title = cid
        if cid in active and active[cid].get("name"):
            title += f" - {active[cid]['name']}"
        elif active and cid not in active:
            title += " (not an active classifier)"
        print(title)
        hits = []
        for club, info in data.items():
            dates = sorted({s["date"] for s in info["shots"] if s["id"] == cid}, reverse=True)
            if dates:
                hits.append((dates[0], club, info["name"], dates))
        if not hits:
            print("  Never shot by any listed club (within USPSA's retained history).")
            print("  => OK to use\n")
            continue
        recent = False
        for last, club, name, dates in sorted(hits, reverse=True):
            is_recent = last >= cutoff
            recent |= is_recent
            marker = "RECENT" if is_recent else "      "
            others = f" (+{len(dates) - 1} earlier)" if len(dates) > 1 else ""
            label = name if club in name else f"{name} ({club})"
            print(f"  {marker} {label}: last shot {fmt_date(last)}{others}")
        any_recent |= recent
        print(f"  => {'SHOT RECENTLY' if recent else 'OK to use'} (window since {fmt_date(cutoff)})\n")
    return any_recent


def report_recent(data, cutoff):
    rows = []
    for club, info in data.items():
        for s in info["shots"]:
            if s["date"] >= cutoff:
                rows.append((s["id"], s["date"], club))
    by_id = {}
    for cid, d, club in rows:
        by_id.setdefault(cid, []).append((d, club))
    print(f"Classifiers shot since {fmt_date(cutoff)} by {', '.join(data)}:")
    for cid in sorted(by_id):
        entries = ", ".join(f"{club} {fmt_date(d)}" for d, club in sorted(by_id[cid], reverse=True))
        print(f"  {cid}: {entries}")
    print(f"{len(by_id)} distinct classifiers")


def report_unshot(data, cutoff, active):
    if not active:
        sys.exit(f"{CLASSIFIERS_JSON} not found; run fetch/extract scripts first.")
    recent_ids = {s["id"] for info in data.values() for s in info["shots"] if s["date"] >= cutoff}
    unshot = [c for cid, c in sorted(active.items()) if cid not in recent_ids]
    print(f"Active classifiers NOT shot by {', '.join(data)} since {fmt_date(cutoff)}:")
    for c in unshot:
        print(f"  {c['id']}  {c.get('name') or ''}")
    print(f"{len(unshot)} of {len(active)} active classifiers")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ids", nargs="*", help='classifier IDs like "26-03"')
    p.add_argument("--months", type=int, default=3, help="what counts as 'recent' (default: 3)")
    p.add_argument("--clubs", default=",".join(DEFAULT_CLUBS),
                   help=f"comma-separated club codes (default: {','.join(DEFAULT_CLUBS)})")
    p.add_argument("--recent", action="store_true", help="list every classifier shot in the window")
    p.add_argument("--unshot", action="store_true", help="list active classifiers not shot in the window")
    args = p.parse_args(argv)

    bad = [i for i in args.ids if not ID_RE.match(i)]
    if bad:
        p.error(f"invalid classifier ID(s): {', '.join(bad)} (expected format like 26-03)")
    if not (args.ids or args.recent or args.unshot):
        p.error("give one or more classifier IDs, or use --recent / --unshot")

    clubs = [c.strip().upper() for c in args.clubs.split(",") if c.strip()]
    cutoff = date.today() - timedelta(days=round(args.months * 30.44))
    data = fetch_all(clubs)
    active = load_active_classifiers()

    rc = 0
    if args.ids:
        rc = 1 if report_ids(args.ids, data, cutoff, active) else 0
    if args.recent:
        report_recent(data, cutoff)
    if args.unshot:
        report_unshot(data, cutoff, active)
    return rc


if __name__ == "__main__":
    sys.exit(main())
