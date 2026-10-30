# InmueblesPY maintenance toolchain

This repository ships the rendered site, not a generator: `site/` contains
4,023 pre-built pages and there is no upstream template or CSV. The corpus is
therefore treated as the source of truth, and these tools are what make a
change reproducible across thousands of URLs and checkable afterwards.

## Everyday use

```sh
python3 tools/extract_dataset.py     # recover facts from the corpus
python3 tools/apply_codemods.py      # apply every transformation (idempotent)
python3 tools/build_sitemaps.py      # refresh lastmod from page content
python3 tools/audit.py               # gate: non-zero exit if a check fails
node    tools/browser/check.mjs      # real-browser checks (needs a local server)
```

For the browser suite, serve the site first:

```sh
cd site && python3 -m http.server 8899 --bind 127.0.0.1
BASE=http://127.0.0.1:8899 OUT=/tmp/shots node tools/browser/check.mjs
```

## What lives where

| Path | Role |
| --- | --- |
| `tools/lib/corpus.py` | Reading, writing, text extraction, similarity, content fingerprints |
| `tools/lib/facts.py` | Numbers derived from the dataset: profile counts, ranks, shares |
| `tools/lib/category_content.py` | Per-category editorial content for the buy pages |
| `tools/extract_dataset.py` | Rebuilds `data/dataset.json` from the rendered pages |
| `tools/codemods/*.py` | One transformation each, run in `ORDER` |
| `tools/audit.py` | 20 checks; blocking ones gate a deploy |
| `tools/build_sitemaps.py` | Content-derived `<lastmod>`, stored in `data/lastmod.json` |
| `data/dataset.json` | Ground truth: agencies, cities, price references, counts |
| `data/lastmod.json` | Per-URL content hash and the date it last changed |

## Rules for a codemod

A codemod must be **idempotent**: running it twice changes nothing the second
time. `apply_codemods.py` reports how many pages each one touched, so a re-run
printing `0 of N page(s) changed` is the proof.

Prefer anchoring on structure (an element, an id, a full sentence) over loose
fragments. An earlier version of `a10_lang_leaks` replaced the bare substring
`"da empresa"`, which also matched inside `"cada empresa"` and corrupted 1,282
pages; the guarded rules in that file show the pattern to follow.

## Numbers must come from the dataset

Never write a count into a page by hand. Several blocks on a page quote the
same figure, and when they were maintained separately 96 pages ended up
contradicting themselves. `facts.Facts` is the single authority, and
`audit.py`'s `counts` check fails if any published figure disagrees with it.

## Known limitation

`doorway_cities` is a warning, not a blocker. 121 of 195 municipalities have no
seated professional, no registered neighbourhood and no price reference, so
population is the only datum that distinguishes their category pages. More
prose cannot fix that; either per-city data is acquired, or the thin
municipalities' four category pages are consolidated into the city page with
redirects.
