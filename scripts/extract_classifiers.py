"""Extract stage data from the downloaded classifier PDFs into data/classifiers.json.

Run scripts/fetch_classifiers.py first. Requires pymupdf.
"""
import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdfs"
DATA_DIR = ROOT / "data"

# Some PDFs are scanned images with no text layer; transcribed from their
# Written Stage Briefing page.
TEXT_OVERRIDES = {
    "21-01": "8x3 Trigger Freeze is a 24 round, 120-point, Comstock Classifier course. "
             "There are 12 USPSA targets. ",
    "23-01": "THS Short Course is a 12 round, 60-point, Comstock Classifier course. "
             "There are 6 IPSC targets. ",
    "23-02": "This could be the Greatest Night of Our Lives is a 12 round, 60-point, "
             "Comstock Classifier course. There are 6 USPSA targets. ",
}

PAPER_WORDS = ("metric", "classic", "ipsc", "uspsa")
POPPER_RE = re.compile(r"popper|\bpp\b", re.I)
PLATE_RE = re.compile(r"plate", re.I)
NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}


def words_to_digits(s: str) -> str:
    return re.sub(r"\b(" + "|".join(NUMBER_WORDS) + r")\b",
                  lambda m: NUMBER_WORDS[m.group(1).lower()], s, flags=re.I)


def pdf_text(cid: str) -> str:
    if cid in TEXT_OVERRIDES:
        return TEXT_OVERRIDES[cid]
    doc = pymupdf.open(PDF_DIR / f"{cid}.pdf")
    # Drop the vertical "NATIONAL RANGE OFFICERS INSTITUTE" watermark (one char per line).
    lines = [l.strip() for p in doc for l in p.get_text().splitlines()]
    return "\n".join(l for l in lines if len(l) > 1 or l.isdigit())


def flat(s: str) -> str:
    s = s.replace("\u201d", '"').replace("\u2033", '"')
    return words_to_digits(re.sub(r"\s+", " ", s).strip())


def targets_description(text: str) -> str | None:
    f = flat(text)
    m = re.search(r"There (?:are|is) ([^.]+)\.", f, re.I)
    if m:
        return m.group(1)
    m = re.search(r"Targets?:\s*(.+?)\s*(?:Scored Hits|Rounds:)", f, re.I)
    if m:
        return m.group(1)
    # Old NROI layout: the line right after "Comstock|Virginia Count, N rounds, P points".
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if re.match(r"(?i)(comstock|virginia)\b.*\brounds?\b", l):
            return lines[i + 1]
    return None


def parse_targets(desc: str):
    paper = poppers = plates = 0
    unknown = []
    desc = flat(desc)
    # "3 8" plates" -> skip the size prefix so the count is 3.
    for n, words in re.findall(r'(\d+)\s+(?:\d+"\s*)?([A-Za-z][A-Za-z\- ]*)', desc):
        n = int(n)
        w = words.lower()
        if POPPER_RE.search(w):
            poppers += n
        elif PLATE_RE.search(w):
            plates += n
        elif any(k in w for k in PAPER_WORDS) or "target" in w:
            paper += n
        else:
            unknown.append(f"{n} {words.strip()}")
    return paper, poppers, plates, unknown


def extract(card: dict) -> dict:
    cid = card["id"]
    text = pdf_text(cid)
    f = flat(text)
    notes = []

    m = re.search(r"\b(Comstock|Virginia)\b", f, re.I)
    scoring = m.group(1).capitalize() if m else None

    m = (re.search(r"(\d+)[ -]rounds?,? \d+[ -]points?", f, re.I)
         or re.search(r"Rounds:\s*(\d+)", f, re.I)
         or re.search(r"(\d+)[ -]rounds?\b", f, re.I))
    rounds = int(m.group(1)) if m else None

    desc = targets_description(text)
    paper, poppers, plates, unknown = parse_targets(desc or "")
    if plates:
        notes.append(f"{plates} steel plate(s) in addition to poppers ({desc})")
    if unknown:
        notes.append(f"unrecognized target types: {unknown}")

    m = re.search(r"Best\s+(\d+)", f, re.I)
    hits = int(m.group(1)) if m else None
    steel = poppers + plates
    if hits is None and paper and rounds:
        if (rounds - steel) % paper == 0:
            hits = (rounds - steel) // paper
            notes.append("scored hits per paper not stated; inferred from round count")
    if paper == 0:
        hits = None
        notes.append("no paper targets (all steel); scored hits per paper not applicable")
    if cid in TEXT_OVERRIDES:
        notes.append("PDF has no text layer; data transcribed from the stage briefing image")

    if rounds is not None and rounds != paper * (hits or 0) + steel:
        notes.append(
            f"round count {rounds} != paper*hits + steel ({paper}*{hits} + {steel})")
    if card.get("scoring") and scoring and card["scoring"].lower() != scoring.lower():
        notes.append(f"website lists scoring as {card['scoring']}")
    if card.get("rounds", "-").isdigit() and rounds and int(card["rounds"]) != rounds:
        notes.append(f"website lists {card['rounds']} rounds")

    return {
        "id": cid,
        "name": card["name"],
        "scoring": scoring,
        "rounds": rounds,
        "paper_targets": paper,
        "scored_hits_per_paper": hits,
        "poppers": poppers,
        "pdf_url": card["pdf_url"],
        "notes": notes,
    }


def main():
    cards = json.loads((DATA_DIR / "classifier_index.json").read_text())
    active = [c for c in cards if not c["retired"]]
    results = sorted((extract(c) for c in active), key=lambda r: r["id"])
    (DATA_DIR / "classifiers.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"wrote {len(results)} classifiers")
    for r in results:
        if r["notes"]:
            print(r["id"], "|", "; ".join(r["notes"]))


if __name__ == "__main__":
    main()
