#!/usr/bin/env python3
"""Refresh sitemap <lastmod> values from page content, not from the clock.

Every URL's meaningful content (main element, structured data, title,
description) is hashed. data/lastmod.json stores the hash and the date it was
last seen changing, so rebuilding the site does not bump thousands of dates
that nothing touched.

    python3 tools/build_sitemaps.py                  # update from today
    python3 tools/build_sitemaps.py --seed DIR DATE   # initialise the store
                                                      # from an earlier tree
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import corpus as C  # noqa: E402

LOC_RE = re.compile(r"(<loc>)(.*?)(</loc>)")
URL_BLOCK_RE = re.compile(r"<url>.*?</url>", re.S)
LASTMOD_RE = re.compile(r"<lastmod>.*?</lastmod>", re.S)


def fingerprints(root: str) -> dict:
    out = {}
    for dirpath, _d, files in os.walk(root):
        for name in files:
            if name != "index.html":
                continue
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            url = "/" + rel[: -len("index.html")]
            out[url] = C.content_fingerprint(C.read(p))
    return out


def main() -> int:
    today = dt.date.today().isoformat()

    if "--seed" in sys.argv:
        i = sys.argv.index("--seed")
        seed_dir, seed_date = sys.argv[i + 1], sys.argv[i + 2]
        base = os.path.join(seed_dir, "site") if os.path.isdir(os.path.join(seed_dir, "site")) else seed_dir
        store = {u: {"hash": h, "lastmod": seed_date} for u, h in fingerprints(base).items()}
        C.save_json("lastmod.json", store)
        print(f"seeded {len(store)} URLs at {seed_date}")
        return 0

    store = C.load_json("lastmod.json", {}) or {}
    current = fingerprints(C.SITE)
    changed = new = 0
    for url, h in current.items():
        rec = store.get(url)
        if rec is None:
            store[url] = {"hash": h, "lastmod": today}
            new += 1
        elif rec["hash"] != h:
            store[url] = {"hash": h, "lastmod": today}
            changed += 1
    for url in [u for u in store if u not in current]:
        del store[url]
    C.save_json("lastmod.json", store)

    written = 0
    for f in sorted(glob.glob(os.path.join(C.SITE, "sitemaps", "*.xml"))):
        src = C.read(f)

        def fix(block: str) -> str:
            m = LOC_RE.search(block)
            if not m:
                return block
            url = m.group(2)[len(C.CANONICAL_HOST):]
            rec = store.get(url)
            if not rec:
                return block
            tag = f"<lastmod>{rec['lastmod']}</lastmod>"
            if LASTMOD_RE.search(block):
                return LASTMOD_RE.sub(tag, block, count=1)
            return block.replace(m.group(0), m.group(0) + tag, 1)

        out = URL_BLOCK_RE.sub(lambda m: fix(m.group(0)), src)
        if C.write(f, out):
            written += 1

    dates = {}
    for f in glob.glob(os.path.join(C.SITE, "sitemaps", "*.xml")):
        for d in re.findall(r"<lastmod>(.*?)</lastmod>", C.read(f)):
            dates[d] = dates.get(d, 0) + 1
    print(f"{new} new, {changed} changed, {written} sitemap file(s) rewritten")
    for d, n in sorted(dates.items()):
        print(f"  {d}: {n} URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
