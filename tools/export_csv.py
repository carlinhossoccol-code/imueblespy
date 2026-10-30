#!/usr/bin/env python3
"""Export the recovered facts as normalised CSVs: the project's data source.

The repository was delivered as rendered HTML with no upstream generator or
spreadsheet. These files are the sustainable source of truth that replaces
"read it back out of the HTML": they are diffable, editable by hand, and every
published figure is checked against them by tools/audit.py.

Regenerate with:
    python3 tools/extract_dataset.py && python3 tools/export_csv.py

Workflow once data changes: edit the CSV, run tools/apply_codemods.py to push
the change into the pages, then tools/audit.py to confirm the pages agree.
"""
from __future__ import annotations

import csv
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import corpus as C  # noqa: E402

ECON_RE = re.compile(r"<b>(?:Economía departamental|Economia departamental):</b>\s*([^<]*)")
H1_RE = re.compile(r"<h1>(.*?)</h1>", re.S)


def _write(name: str, header: list[str], rows: list[list]) -> None:
    path = os.path.join(C.DATA, name)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    print(f"  {name:28} {len(rows):5} rows")


# Asunción is the one department whose URL slug is localised.
PT_DEPT_SLUG = {"asuncion": "assuncao"}
ES_DEPT_SLUG = {v: k for k, v in PT_DEPT_SLUG.items()}


def department_facts() -> dict:
    """Department display names and the economy line shown on their pages.

    Keyed by the Spanish slug, which the rest of the toolchain uses as the
    canonical department identifier; the Portuguese slug is recorded alongside
    because Asunción differs between the two editions.
    """
    out: dict[str, dict] = {}
    for lang, zone in (("es", "zonas"), ("pt", "regioes")):
        base = os.path.join(C.SITE, "es" if lang == "es" else "pt-br", zone)
        for dept_dir in sorted(os.listdir(base)):
            dept = ES_DEPT_SLUG.get(dept_dir, dept_dir) if lang == "pt" else dept_dir
            p = os.path.join(base, dept_dir, "index.html")
            if not os.path.exists(p):
                continue
            src = C.read(p)
            rec = out.setdefault(dept, {})
            h1 = H1_RE.search(src)
            if h1:
                name = C.TAG_RE.sub("", h1.group(1)).strip().split(":")[0].strip()
                # Department pages are titled "Inmobiliarias y ciudades de X" /
                # "Imobiliárias e cidades de X"; keep only the department name.
                name = re.sub(
                    r"^(?:Inmobiliarias y ciudades de|Imobiliárias e cidades de|"
                    r"Comprar propiedades en|Comprar imóveis em)\s+", "", name)
                rec[f"name_{lang}"] = name
            m = ECON_RE.search(src)
            if m:
                rec[f"economy_{lang}"] = m.group(1).strip()
    # The economy line is rendered on city and category pages, not on the
    # department index, so it is always collected from there.
    for lang, buy in (("es", "venta"), ("pt", "comprar")):
        base = os.path.join(C.SITE, "es" if lang == "es" else "pt-br", buy)
        for dept_dir in sorted(os.listdir(base)):
            dept = ES_DEPT_SLUG.get(dept_dir, dept_dir) if lang == "pt" else dept_dir
            dpath = os.path.join(base, dept_dir)
            if not os.path.isdir(dpath) or out.get(dept, {}).get(f"economy_{lang}"):
                continue
            for root, _d, files in os.walk(dpath):
                if "index.html" not in files:
                    continue
                m = ECON_RE.search(C.read(os.path.join(root, "index.html")))
                if m:
                    out.setdefault(dept, {})[f"economy_{lang}"] = m.group(1).strip()
                    break
    return out


def main() -> int:
    ds = C.load_json("dataset.json")
    if not ds:
        print("run tools/extract_dataset.py first")
        return 2
    cities, agencies, prices = ds["cities"], ds["agencies"], ds["price_refs"]
    depts = department_facts()
    os.makedirs(C.DATA, exist_ok=True)
    print("writing CSVs:")

    _write(
        "departments.csv",
        ["slug_es", "slug_pt", "name_es", "name_pt", "economy_es", "economy_pt"],
        [
            [d, PT_DEPT_SLUG.get(d, d), r.get("name_es", ""), r.get("name_pt", ""),
             r.get("economy_es", ""), r.get("economy_pt", "")]
            for d, r in sorted(depts.items())
        ],
    )

    muni_rows = []
    for key, c in sorted(cities.items()):
        name = ""
        m = re.search(r"Comprar propiedades en (.*?): ciudad e inmobiliarias", c.get("h1") or "")
        if m:
            name = m.group(1).strip()
        muni_rows.append([
            key, c["department_slug"], c["city_slug"], name,
            c.get("population_2022") or "", len(c.get("neighbourhoods", [])),
        ])
    _write("municipalities.csv",
           ["key", "department_slug", "city_slug", "name", "population_2022", "neighbourhood_count"],
           muni_rows)

    hood_rows = []
    for key, c in sorted(cities.items()):
        for h in c.get("neighbourhoods", []):
            hood_rows.append([key, c["department_slug"], c["city_slug"], h])
    _write("neighbourhoods.csv", ["municipality_key", "department_slug", "city_slug", "slug"], hood_rows)

    prof_rows = []
    for pid, a in sorted(agencies.items(), key=lambda kv: int(kv[0])):
        fields = a.get("published_fields") or []
        prof_rows.append([
            pid, a["slug"], a["kind"], a.get("name") or "", a.get("city") or "",
            a.get("department") or "", a.get("address") or "", a.get("phone") or "",
            "yes" if "whatsapp" in (a.get("channels") or []) else "",
            "yes" if "website" in (a.get("channels") or []) else "",
            a.get("source") or "", a.get("source_url") or "", a.get("researched") or "",
            "|".join(fields),
        ])
    _write("professionals.csv",
           ["id", "slug", "kind", "name", "city", "department", "address", "phone",
            "whatsapp", "website", "source", "source_url", "researched_date", "published_fields"],
           prof_rows)

    # Networks: one row per published location, with the domain that evidences it
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
    import facts as FA

    F = FA.Facts()
    net_rows = []
    for key, n in sorted(F.networks.items()):
        for pid in n["ids"]:
            a = agencies[pid]
            net_rows.append([n["name"], n["domain"], len(n["ids"]), pid,
                             a.get("name") or "", a.get("city") or "",
                             a.get("source_url") or ""])
    _write("networks.csv",
           ["brand", "evidence_domain", "locations", "professional_id",
            "professional_name", "city", "source_url"], net_rows)

    price_rows = []
    for k, v in sorted(prices.items()):
        parts = k.split("/")
        cat = parts[-1]
        muni = "/".join(parts[:-1])
        price_rows.append([muni, cat, v.get("value", ""), v.get("dated", ""), v.get("source_url", "")])
    _write("price_references.csv",
           ["municipality_key", "category", "value", "dated", "source_url"], price_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
