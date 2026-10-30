# InmueblesPY maintenance toolchain

This repository ships the rendered site, not a generator: `site/` contains
4,023 pre-built pages and there is no upstream template or CSV. The corpus is
therefore treated as the source of truth, and these tools are what make a
change reproducible across thousands of URLs and checkable afterwards.

## Everyday use

```sh
python3 tools/validate_data.py       # check data/ before anything reads it
python3 tools/apply_codemods.py      # apply every transformation (idempotent)
python3 tools/build_sitemaps.py      # refresh lastmod from page content
python3 tools/audit.py               # gate: non-zero exit if a check fails
python3 tools/check_environment.py   # what the host will publish and send
node    tools/browser/check.mjs      # responsiveness and accessibility
node    tools/browser/journeys.mjs   # the fifteen user journeys
```

The data files are the input. `tools/extract_dataset.py` and
`tools/export_csv.py` exist to *recover* them from the rendered HTML, which was
necessary once because the site arrived with no generator. Day to day, edit the
CSV and run the codemods; do not re-derive the data from pages the codemods
themselves wrote.

Or run the whole thing with `./tools/run_all.sh`
(`WITH_LIGHTHOUSE=1` adds the Lighthouse pass).

For the browser suite, serve the site first:

```sh
python3 -I tools/serve.py 8899
```

Use that server, not `python3 -m http.server`. The default one answers a
single request at a time, which queues subresources and then shows up as the
page's own latency: the full directory page measured Lighthouse 92 with
570 ms of server latency on the serial server, and 100 with 0 ms on this one.
A performance number taken against a serial server is measuring the server.

## Deploying

See `DEPLOY.md`. In short: run `./tools/run_all.sh` green, deploy to the
temporary Render host, then `python3 -I tools/check_http.py <url>` and require
the eleven platform checks to pass there before touching the definitive
domain.

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
| `data/*.csv` | The source of truth: departments, municipalities, neighbourhoods, professionals, prices, coordinates |
| `tools/match_geonames.py` | Attaches GeoNames coordinates to municipalities |
| `tools/check_environment.py` | Publishable files, headers, CSP, 404, secrets |
| `tools/browser/journeys.mjs` | Fifteen end-to-end journeys with assertions |
| `tools/browser/overflow-debug.mjs` | Finds what actually widens the document |
| `tools/browser/a11y.mjs` | Zoom reflow, contrast, reduced motion, focus visibility |
| `tools/browser/lighthouse.mjs` | Lighthouse, mobile and desktop |
| `tools/serve.py` | Threaded local server, used by every browser check |
| `tools/run_all.sh` | The whole pipeline, in the only correct order |
| `tools/check_http.py` | Verifies a deployed host over real HTTP |

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

## Differentiating municipalities

`doorway_cities` is a blocking check. It compares the same category across
municipalities, which is the axis that breaks when shared guidance is added to
every page.

It was resolved with geography, not with prose. `data/municipality_coordinates.csv`
carries a GeoNames coordinate for 194 of 195 municipalities, which lets two
things be real rather than approximated:

- nearby professionals are ranked by actual distance, so neighbouring
  municipalities no longer list identical firms in identical order
- each municipality publishes its own location facts: distance to Asunción,
  orientation relative to the department's largest city, national population
  rank, and the five nearest localities with population and professional counts

All 195 municipalities have a different set of nearest neighbours, so this is
each page's own content. Measured over 2,860 cross-municipality pairs, maximum
similarity fell from 0.859 to 0.718.

If a future change pushes the check back over its threshold, add data rather
than text. Padding pages with generic prose to move a number is the failure
mode this check exists to catch.

## What is not recoverable here

The original generators and CSVs were never in this repository: `git log
--diff-filter=A` shows only rendered output. The pages themselves record that
an observed price reference exists for 36 municipality/category pairs whose
value was never published, so the upstream source held more than the HTML
exposes. Those values can only come from that source.
