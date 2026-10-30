#!/usr/bin/env python3
"""Check the CSV source of truth for internal consistency.

Run after editing any file in data/ and before tools/apply_codemods.py, so a
bad edit is caught at the source rather than after it has been written into
thousands of pages.
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import corpus as C  # noqa: E402

CATEGORIES = {"terrenos", "casas", "departamentos", "comerciales"}


def rows(name: str) -> list[dict]:
    p = os.path.join(C.DATA, name)
    with open(p, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    problems: list[str] = []
    depts = rows("departments.csv")
    munis = rows("municipalities.csv")
    hoods = rows("neighbourhoods.csv")
    profs = rows("professionals.csv")
    prices = rows("price_references.csv")

    dept_slugs = {d["slug_es"] for d in depts}
    muni_keys = {m["key"] for m in munis}

    for d in depts:
        for f in ("slug_es", "slug_pt", "name_es", "name_pt", "economy_es", "economy_pt"):
            if not d[f].strip():
                problems.append(f"departments.csv: {d['slug_es']} has empty {f}")

    seen = set()
    for m in munis:
        if m["key"] in seen:
            problems.append(f"municipalities.csv: duplicate key {m['key']}")
        seen.add(m["key"])
        if m["department_slug"] not in dept_slugs:
            problems.append(f"municipalities.csv: {m['key']} references unknown department {m['department_slug']}")
        if not m["name"].strip():
            problems.append(f"municipalities.csv: {m['key']} has no name")
        if m["population_2022"]:
            try:
                if int(m["population_2022"]) <= 0:
                    problems.append(f"municipalities.csv: {m['key']} population must be positive")
            except ValueError:
                problems.append(f"municipalities.csv: {m['key']} population is not a number")
        else:
            problems.append(f"municipalities.csv: {m['key']} has no population")
        want = sum(1 for h in hoods if h["municipality_key"] == m["key"])
        if int(m["neighbourhood_count"]) != want:
            problems.append(
                f"municipalities.csv: {m['key']} claims {m['neighbourhood_count']} "
                f"neighbourhoods, neighbourhoods.csv has {want}")

    for h in hoods:
        if h["municipality_key"] not in muni_keys:
            problems.append(f"neighbourhoods.csv: unknown municipality {h['municipality_key']}")

    ids = set()
    for p in profs:
        if p["id"] in ids:
            problems.append(f"professionals.csv: duplicate id {p['id']}")
        ids.add(p["id"])
        if not p["name"].strip():
            problems.append(f"professionals.csv: id {p['id']} has no name")
        if p["kind"] not in ("agency", "agent"):
            problems.append(f"professionals.csv: id {p['id']} has unknown kind {p['kind']!r}")
        if p["department"] and p["city"]:
            match = [m for m in munis if m["name"] == p["city"]]
            if match and match[0]["department_slug"] not in dept_slugs:
                problems.append(f"professionals.csv: id {p['id']} city/department mismatch")
        # a published phone must be reflected in published_fields and vice versa
        fields = set(filter(None, p["published_fields"].split("|")))
        if bool(p["phone"]) != ("Teléfono" in fields):
            problems.append(f"professionals.csv: id {p['id']} phone column disagrees with published_fields")

    for pr in prices:
        if pr["municipality_key"] not in muni_keys:
            problems.append(f"price_references.csv: unknown municipality {pr['municipality_key']}")
        if pr["category"] not in CATEGORIES:
            problems.append(f"price_references.csv: unknown category {pr['category']!r}")
        if not pr["source_url"].startswith("http"):
            problems.append(
                f"price_references.csv: {pr['municipality_key']}/{pr['category']} "
                f"has no source URL; an observed price must be traceable")
        if not pr["dated"]:
            problems.append(f"price_references.csv: {pr['municipality_key']}/{pr['category']} has no date")

    print(f"departments {len(depts)}  municipalities {len(munis)}  "
          f"neighbourhoods {len(hoods)}  professionals {len(profs)}  prices {len(prices)}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems[:40]:
            print("  -", p)
        if len(problems) > 40:
            print(f"  ... {len(problems) - 40} more")
        return 1
    print("data is internally consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
