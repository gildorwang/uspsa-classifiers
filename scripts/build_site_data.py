"""Scrape club classifier history and write site/data.json for the static website.

  python scripts/build_site_data.py [--clubs NW01,NW02,...]
"""
import argparse
import json
from datetime import datetime, timezone

from check_classifier import DEFAULT_CLUBS, ROOT, fetch_all, load_active_classifiers

OUT = ROOT / "site" / "data.json"
INDEX_JSON = ROOT / "data" / "classifier_index.json"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--clubs", default=",".join(DEFAULT_CLUBS))
    args = p.parse_args()
    clubs = [c.strip().upper() for c in args.clubs.split(",") if c.strip()]

    data = fetch_all(clubs)
    active = load_active_classifiers()
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "clubs": [
            {
                "code": club,
                "name": info["name"],
                "url": f"https://uspsa.org/classifiers-by-club?action=show&club={club}",
                "shots": [
                    {"id": s["id"], "date": s["date"].isoformat(), "match_url": s["match_url"]}
                    for s in info["shots"]
                ],
            }
            for club, info in data.items()
        ],
        "classifiers": [
            {k: c.get(k) for k in ("id", "name", "pdf_url", "scoring", "rounds", "paper_targets", "poppers")}
            for c in sorted(active.values(), key=lambda c: c["id"])
        ],
        # Every classifier on uspsa.org (incl. retired), for names and PDF links in lookups.
        "index": {
            c["id"]: {"name": c.get("name"), "pdf_url": c.get("pdf_url"), "retired": c.get("retired", False)}
            for c in json.loads(INDEX_JSON.read_text())
        } if INDEX_JSON.exists() else {},
    }
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT} ({sum(len(c['shots']) for c in out['clubs'])} shots)")


if __name__ == "__main__":
    main()
