#!/usr/bin/env python3
"""Apply idempotent transformations across the rendered corpus.

Every codemod is a module in tools/codemods/ exposing:

    ORDER       : int    - lower runs first
    TITLE       : str    - human description
    SELECT      : str|None - regex matched against the page URL (None = all)
    apply(path, src, ctx) -> str   - must be idempotent

Run:
    python3 tools/apply_codemods.py                 # all codemods
    python3 tools/apply_codemods.py banner counts   # named only
    python3 tools/apply_codemods.py --dry-run
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)
import corpus as C  # noqa: E402


def load_codemods(names: list[str]):
    import codemods

    mods = []
    for mi in pkgutil.iter_modules(codemods.__path__):
        if names and mi.name not in names:
            continue
        m = importlib.import_module(f"codemods.{mi.name}")
        if not hasattr(m, "apply"):
            continue
        m.__key__ = mi.name
        mods.append(m)
    return sorted(mods, key=lambda m: (getattr(m, "ORDER", 100), m.__key__))


def build_context() -> dict:
    ds = C.load_json("dataset.json", {}) or {}
    ctx = {"dataset": ds}
    cities = ds.get("cities", {})
    pbc = ds.get("profiles_by_city", {})
    key_by_name, name_by_key = {}, {}
    for key, c in cities.items():
        m = re.match(r"Comprar propiedades en (.*?):", c.get("h1") or "")
        if m:
            key_by_name[m.group(1).strip()] = key
            name_by_key[key] = m.group(1).strip()
    ctx["city_key_by_name"] = key_by_name
    ctx["city_name_by_key"] = name_by_key
    ctx["profiles_truth"] = {
        key_by_name[n]: r for n, r in pbc.items() if n in key_by_name
    }
    return ctx


def main() -> int:
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    mods = load_codemods(argv)
    if not mods:
        print("no codemods matched")
        return 2

    ctx = build_context()
    paths = C.all_pages()
    print(f"{len(paths)} pages, {len(mods)} codemod(s){' (dry run)' if dry else ''}\n")

    srcs = {p: C.read(p) for p in paths}
    totals = {}
    for m in mods:
        sel = getattr(m, "SELECT", None)
        changed = 0
        considered = 0
        for p in paths:
            url = C.rel_url(p)
            if sel and not re.search(sel, url):
                continue
            considered += 1
            before = srcs[p]
            after = m.apply(p, before, ctx)
            if after != before:
                srcs[p] = after
                changed += 1
        totals[m.__key__] = (considered, changed)
        print(f"[{m.__key__:22}] {getattr(m,'TITLE','')}")
        print(f"{'':24} {changed} of {considered} page(s) changed")

    written = 0
    if not dry:
        for p, s in srcs.items():
            if C.write(p, s):
                written += 1
    print(f"\n{written} file(s) written")

    # extra non-page work (sitemaps, robots, root) handled by dedicated scripts
    return 0


if __name__ == "__main__":
    sys.exit(main())
