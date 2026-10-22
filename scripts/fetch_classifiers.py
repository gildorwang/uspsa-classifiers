"""Fetch the USPSA classifier list and download the PDFs of active classifiers.

uspsa.org sits behind Cloudflare, so requests are made with curl_cffi using a
browser TLS fingerprint (pip install curl_cffi).

Outputs:
  data/classifier_index.json  - every classifier card on the page (incl. retired)
  pdfs/<id>.pdf               - PDFs for non-retired classifiers
"""
import html
import json
import re
import time
from pathlib import Path

from curl_cffi import requests

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdfs"
DATA_DIR = ROOT / "data"
URL = "https://uspsa.org/classifiers"

CARD_RE = re.compile(r'<div class="card-body">(?P<body>.*?)</div>', re.S)


def parse_cards(page: str):
    cards = []
    for m in CARD_RE.finditer(page):
        body = m.group("body")
        cid = re.search(r'<h4 class="card-title">\s*(.*?)\s*</h4>', body)
        if not cid:
            continue
        name = re.search(r'<h6[^>]*>\s*(.*?)\s*</h6>', body, re.S)
        scoring = re.search(r'Scoring:\s*([^<]*)', body)
        rounds = re.search(r'Rounds:\s*([^<]*)', body)
        pdf = re.search(r'href="([^"]+\.pdf)"', body)
        viewer_url = pdf.group(1) if pdf else None
        # The page links to an HTML pdf.js viewer; the raw file lives under /viewer/pdf/.
        pdf_url = viewer_url.replace("/viewer/", "/viewer/pdf/", 1) if viewer_url else None
        cards.append({
            "id": html.unescape(cid.group(1)).strip(),
            "name": html.unescape(name.group(1)).strip() if name else None,
            "scoring": scoring.group(1).strip() if scoring else None,
            "rounds": rounds.group(1).strip() if rounds else None,
            "viewer_url": viewer_url,
            "pdf_url": pdf_url,
            "retired": "RETIRED" in body,
        })
    return cards


def main():
    s = requests.Session(impersonate="chrome")
    r = s.get(URL)
    r.raise_for_status()
    cards = parse_cards(r.text)
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "classifier_index.json").write_text(json.dumps(cards, indent=2))
    active = [c for c in cards if not c["retired"]]
    print(f"{len(cards)} classifiers, {len(active)} active")

    PDF_DIR.mkdir(exist_ok=True)
    for c in active:
        dest = PDF_DIR / f"{c['id']}.pdf"
        if dest.exists() and dest.stat().st_size > 0:
            continue
        resp = s.get(c["pdf_url"])
        resp.raise_for_status()
        if not resp.content.startswith(b"%PDF"):
            raise RuntimeError(f"{c['id']}: response is not a PDF")
        dest.write_bytes(resp.content)
        print("downloaded", dest.name)
        time.sleep(0.3)


if __name__ == "__main__":
    main()
