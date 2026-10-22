# uspsa-classifiers

Active (non-retired) USPSA classifier stage data scraped from https://uspsa.org/classifiers.

- `data/classifiers.json` - one entry per active classifier: `id`, `name`, `scoring` (Comstock/Virginia),
  `rounds`, `paper_targets`, `scored_hits_per_paper`, `poppers`, `pdf_url`, and `notes` (anomalies / inferred values).
- `data/classifier_index.json` - raw listing of every classifier card on the site, including retired ones.
- `pdfs/` - local copies of the classifier PDFs (git-ignored).

## Regenerate

```
pip install curl_cffi pymupdf
python scripts/fetch_classifiers.py    # downloads index + PDFs (uses browser impersonation to pass Cloudflare)
python scripts/extract_classifiers.py  # parses PDFs into data/classifiers.json
```
