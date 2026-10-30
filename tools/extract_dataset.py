#!/usr/bin/env python3
"""Reconstruct a machine-readable dataset from the rendered corpus.

The repository ships only pre-rendered HTML, so the facts the pages assert are
recovered here into data/dataset.json. That file becomes the single source of
truth used by the audits and codemods, which lets per-page numbers be checked
against one authority instead of against each other.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import corpus as C  # noqa: E402


def _cell(src: str, label: str) -> str | None:
    m = re.search(
        r'<th scope="row">' + re.escape(label) + r"</th><td>(.*?)</td>", src, re.S
    )
    if not m:
        return None
    v = C.TAG_RE.sub("", m.group(1)).strip()
    return __import__("html").unescape(v) or None


def extract_agencies() -> dict:
    """One record per professional profile, keyed by numeric id."""
    out: dict[str, dict] = {}
    for seg_key, kind in ((C.AGENCY_SEGMENT, "agency"), (C.AGENT_SEGMENT, "agent")):
        base = os.path.join(C.SITE, "es", seg_key["es"])
        if not os.path.isdir(base):
            continue
        for slug in sorted(os.listdir(base)):
            p = os.path.join(base, slug, "index.html")
            if not os.path.exists(p):
                continue
            src = C.read(p)
            pid = slug.split("-")[0]
            name = _cell(src, "Nombre público")
            rec = {
                "id": pid,
                "slug": slug,
                "kind": kind,
                "name": name,
                "city": _cell(src, "Ciudad informada"),
                "department": _cell(src, "Departamento informado"),
                "address": _cell(src, "Dirección publicada"),
                "phone": _cell(src, "Teléfono reportado"),
                "source": _cell(src, "Fuente consultada"),
                "researched": _cell(src, "Fecha de investigación"),
            }
            # The profile's own "Campos publicados" list is the authoritative
            # statement of which fields exist for this record. The "Consultar
            # fuente" link is the provenance URL, not a contact channel, so it
            # must not be counted as one.
            m = re.search(r"Campos publicados:</b>([^<]*)", src)
            published = {
                t.strip().rstrip(".")
                for t in (m.group(1).split(",") if m else [])
                if t.strip()
            }
            rec["published_fields"] = sorted(published)
            chans = set()
            if "Teléfono" in published:
                chans.add("phone")
            if "WhatsApp" in published:
                chans.add("whatsapp")
            if "Sitio web" in published:
                chans.add("website")
            rec["channels"] = sorted(chans)
            m = re.search(r'<a href="(https?://[^"]+)" rel="nofollow noopener noreferrer"[^>]*>Consultar fuente', src)
            if m:
                rec["source_url"] = m.group(1)
            out[pid] = rec
    return out


CITY_H1_RE = re.compile(r"Comprar propiedades en (.*?): ciudad e inmobiliarias")

# The directory data names a few municipalities slightly differently from the
# city pages. Mapping them explicitly keeps the profile counts attributable
# instead of silently dropping those records.
CITY_NAME_ALIASES = {
    "Juan León Mallorquín": "Doctor Juan León Mallorquín",
    "Juan Emilio O’Leary": "Juan Emiliano O'Leary",
    "San Pedro del Ycuamandiyú": "San Pedro de Ycuamandiyú",
}


def _city_record(src, dept, city):
    h1 = re.search(r"<h1>(.*?)</h1>", src, re.S)
    pop = re.search(r'<strong class="population-number">([\d.]+)</strong>', src)
    # Neighbourhood pages live under a /barrios/ segment.
    prefix = f"/es/zonas/{dept}/" + (f"{city}/" if city else "") + "barrios/"
    hoods = sorted(set(re.findall(r'href="' + re.escape(prefix) + r'([a-z0-9-]+)/"', src)))
    return {
        "department_slug": dept,
        "city_slug": city or dept,
        "h1": C.TAG_RE.sub("", h1.group(1)).strip() if h1 else None,
        "population_2022": int(pop.group(1).replace(".", "")) if pop else None,
        "neighbourhoods": hoods,
    }


def extract_cities() -> dict:
    """One record per municipality.

    Keyed by 'department/city' slug pair, except for Asunción, which is its own
    department and whose pages therefore sit one level higher.
    """
    out: dict[str, dict] = {}
    base = os.path.join(C.SITE, "es", "zonas")
    for dept in sorted(os.listdir(base)):
        dpath = os.path.join(base, dept)
        if not os.path.isdir(dpath):
            continue
        # A department page that is itself a municipality (Asunción).
        dindex = os.path.join(dpath, "index.html")
        if os.path.exists(dindex):
            dsrc = C.read(dindex)
            if CITY_H1_RE.search(dsrc):
                out[dept] = _city_record(dsrc, dept, None)
        for city in sorted(os.listdir(dpath)):
            cpath = os.path.join(dpath, city, "index.html")
            if not os.path.exists(cpath):
                continue
            out[f"{dept}/{city}"] = _city_record(C.read(cpath), dept, city)
    return out


CATEGORY_SLUGS = {"terrenos", "casas", "departamentos", "comerciales"}


def _price_from(path: str):
    src = C.read(path)
    m = re.search(r'<p class="v10-price-value">([^<]+)</p>', src)
    if not m:
        return None
    d = re.search(r"fechado (\d{4}-\d{2}-\d{2})", src)
    u = re.search(r'<a href="(https?://[^"]+)" rel="noopener noreferrer" target="_blank">Consultar la fuente', src)
    return {
        "value": m.group(1).strip(),
        "dated": d.group(1) if d else None,
        "source_url": u.group(1) if u else None,
    }


def extract_price_refs() -> dict:
    """Observed asking-price references, keyed by 'municipality/category'.

    Asunción is a department that is also a municipality, so its category pages
    sit one level higher than everyone else's. Walking only the deeper shape
    silently dropped its four references, and the pages published figures the
    dataset did not know about.
    """
    out: dict[str, dict] = {}
    base = os.path.join(C.SITE, "es", "venta")
    for dept in sorted(os.listdir(base)):
        dpath = os.path.join(base, dept)
        if not os.path.isdir(dpath):
            continue
        for entry in sorted(os.listdir(dpath)):
            epath = os.path.join(dpath, entry)
            if not os.path.isdir(epath):
                continue
            if entry in CATEGORY_SLUGS:
                # /es/venta/<municipality-department>/<category>/
                rec = _price_from(os.path.join(epath, "index.html")) \
                    if os.path.exists(os.path.join(epath, "index.html")) else None
                if rec:
                    out[f"{dept}/{entry}"] = rec
                continue
            for cat in sorted(os.listdir(epath)):
                f = os.path.join(epath, cat, "index.html")
                if os.path.exists(f):
                    rec = _price_from(f)
                    if rec:
                        out[f"{dept}/{entry}/{cat}"] = rec
    return out


def main() -> None:
    agencies = extract_agencies()
    cities = extract_cities()
    prices = extract_price_refs()

    # Ground-truth profile counts per city, derived from the profiles themselves.
    by_city: dict[str, list[str]] = {}
    for pid, a in agencies.items():
        if a.get("city"):
            by_city.setdefault(a["city"], []).append(pid)

    # Map the human city name used on profiles back to a slug key.
    name_to_key = {}
    for key, c in cities.items():
        m = CITY_H1_RE.search(c["h1"] or "")
        if m:
            name_to_key.setdefault(m.group(1).strip(), key)
    for alias, canonical in CITY_NAME_ALIASES.items():
        if canonical in name_to_key:
            name_to_key.setdefault(alias, name_to_key[canonical])

    counts = {}
    for name, ids in by_city.items():
        key = name_to_key.get(name)
        counts[name] = {
            "city_key": key,
            "profile_ids": sorted(ids, key=int),
            "profiles": len(ids),
            "with_channel": sum(1 for i in ids if agencies[i]["channels"]),
        }

    C.save_json("dataset.json", {
        "agencies": agencies,
        "cities": cities,
        "price_refs": prices,
        "profiles_by_city": counts,
    })
    print(f"agencies/agents : {len(agencies)}")
    print(f"cities          : {len(cities)}")
    print(f"price refs      : {len(prices)}")
    print(f"cities w/ profs : {len(counts)}")


if __name__ == "__main__":
    main()
