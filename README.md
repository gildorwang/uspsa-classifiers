# uspsa-classifiers

Active (non-retired) USPSA classifier stage data scraped from https://uspsa.org/classifiers.

- `data/classifiers.json` - one entry per active classifier: `id`, `name`, `scoring` (Comstock/Virginia),
  `rounds`, `paper_targets`, `scored_hits_per_paper`, `poppers`, `pdf_url`, and `notes` (anomalies / inferred values).
- `data/classifier_index.json` - raw listing of every classifier card on the site, including retired ones.
- `pdfs/` - local copies of the classifier PDFs (git-ignored).

## Check if nearby clubs shot a classifier recently

`scripts/check_classifier.py` scrapes https://uspsa.org/classifiers-by-club for local clubs
(default: NW01, NW02, NW05, NW07, NW15) and reports when each one last shot a classifier.

```
pip install curl_cffi
python scripts/check_classifier.py 26-03 99-08      # per-club last-shot dates; exit code 1 if any shot recently
python scripts/check_classifier.py 26-03 --months 6 # change the "recent" window (default 3 months)
python scripts/check_classifier.py --recent         # every classifier shot by these clubs in the window
python scripts/check_classifier.py --unshot         # active classifiers none of them shot in the window
python scripts/check_classifier.py 26-03 --clubs NW01,NW02
```

## Website

`site/index.html` is a static page with the same checks, plus a sortable table of every active classifier
showing its last-shot date. It reads `site/data.json`, a committed snapshot of the club pages.

uspsa.org's Cloudflare blocks GitHub Actions IPs, so refresh the data from your own machine:

```
python scripts/build_site_data.py
git commit -am "Refresh club data" && git push
```

The `Deploy site` workflow (`.github/workflows/pages.yml`) deploys `site/` to GitHub Pages on every push to `main`.
It also runs daily and tries to re-scrape, keeping the committed snapshot if it's blocked.
To preview locally: `python -m http.server --directory site`.

## Regenerate

```
pip install curl_cffi pymupdf
python scripts/fetch_classifiers.py    # downloads index + PDFs (uses browser impersonation to pass Cloudflare)
python scripts/extract_classifiers.py  # parses PDFs into data/classifiers.json
```
