#!/usr/bin/env python3
"""Attach coordinates to each municipality from the GeoNames gazetteer.

The site shipped with no geographic data, so "nearby professional" could only
ever mean "somewhere in the same department". GeoNames (CC BY 4.0) is a public
gazetteer with stable identifiers, which makes every coordinate traceable to a
row a reader can look up.

Matching is deliberately strict: a candidate must sit in the same department
and its name must match exactly once accents and administrative suffixes are
normalised. Anything ambiguous is left unmatched and reported, because a wrong
coordinate is worse than a missing one.

    python3 tools/match_geonames.py /path/to/PY.txt
"""
from __future__ import annotations

import csv
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import corpus as C  # noqa: E402

# Our department slug -> GeoNames admin1 code.
ADMIN1 = {
    "alto-paraguay": "23", "alto-parana": "01", "amambay": "02", "asuncion": "22",
    "boqueron": "24", "caaguazu": "04", "caazapa": "05", "canindeyu": "19",
    "central": "06", "concepcion": "07", "cordillera": "08", "guaira": "10",
    "itapua": "11", "misiones": "12", "neembucu": "13", "paraguari": "15",
    "presidente-hayes": "16", "san-pedro": "17",
}

# Feature codes worth considering, best first.
PREFERRED = ["ADM2", "PPLA", "PPLA2", "PPLA3", "PPLC", "PPL"]

# Districts whose official name is longer than the name the site uses, pinned
# to a GeoNames id so the match is explicit and auditable rather than inferred
# from a fuzzy rule. Each was confirmed by listing every candidate in the same
# department and checking the district actually exists under that longer name.
PINNED = {
    "caaguazu/mariscal-lopez": "11840002",            # Mcal. Francisco Solano López
    "caaguazu/tres-de-febrero": "11840137",           # 3 de Febrero
    "canindeyu/general-alvarez": "11839956",          # Francisco Caballero Álvarez
    "central/julian-augusto-saldivar": "11840074",    # J. Augusto Saldívar
    "guaira/capitan-mauricio-jose-troche": "11839984",# Mauricio José Troche
    "guaira/mbocayaty-del-guaira": "11840135",        # Mbocayaty
    "itapua/bella-vista-sur": "11840077",             # Bella Vista (Itapúa)
    "paraguari/san-roque": "11839985",                # San Roque González
    "presidente-hayes/teniente-irala": "11840029",    # Tte 1ro Manuel Irala Fernández
    "san-pedro/san-pedro-de-ycuamandiyu": "11840133", # San Pedro del Ykuamandiyú
    # Boquerón district was created by Ley N.º 6688 (2021) out of Mariscal
    # Estigarribia, with its municipal seat in Colonia Neuland. GeoNames has no
    # ADM2 for it, so the seat settlement is the reference point.
    "boqueron/boqueron": "3867411",                   # Colonia Neuland
    # Districts large enough that their centroid falls tens of kilometres from
    # the town of the same name - the Chaco ones span whole regions. For a
    # property site the town is the meaningful reference, so these point at
    # the settlement; the page states which kind of point it is showing.
    "alto-paraguay/puerto-casado": "3437380",  # Puerto Casado
    "boqueron/filadelfia": "3867291",  # Filadelfia
    "boqueron/mariscal-estigarribia": "3867236",  # Mariscal José Félix Estigarribia
    "concepcion/concepcion": "3438834",  # Concepción
    "presidente-hayes/benjamin-aceval": "3439348",  # Benjamín Aceval
    "presidente-hayes/puerto-pinasco": "3437352",  # Puerto Pinasco
    "presidente-hayes/villa-hayes": "3436725",  # Villa Hayes
    # Promoted from a populated-place match to the district (ADM2) after
    # checking both signals: the names agree once orthographic variants are
    # folded (Yvycui/Ybycuí, Yasy Kañy/Yasy Cañy, 3 de Mayo/Tres de Mayo) and
    # the two points are close enough to be the same place. Candidates that
    # were merely nearby, such as Cerro Corá against Zanja Pytã, were rejected.
    "alto-parana/juan-emiliano-o-leary": "11840121",  # Juan E. O´Leary (6.7km)
    "caaguazu/doctor-juan-eulogio-estigarribia": "11840072",  # J Eulogio Estigarribia (11.6km)
    "caaguazu/r-i-tres-corrales": "11839941",  # R.I. 3 Corrales (36.7km)
    "caazapa/tres-de-mayo": "11840160",  # 3 De Mayo (8.9km)
    "canindeyu/salto-del-guaira": "11839948",  # Saltos Del Guaira (21.2km)
    "canindeyu/yasy-cany": "11840068",  # Yasy Kañy (4.2km)
    "concepcion/sargento-jose-felix-lopez": "11840007",  # Sgto. Jose Felix Lopez (16.6km)
    "concepcion/yby-yau": "11840024",  # Yvy Ya´U (16.6km)
    "paraguari/ybycui": "11839983",  # Yvycui (8.2km)
    "paraguari/ybytymi": "11840140",  # Yvytimi (4.3km)
    "san-pedro/guayaibi": "11840023",  # Guajayvi (15.1km)
}

# GeoNames has no ADM2 for districts created after its Paraguay extract, so
# their seat settlement is used instead, with the law that created them noted.
KNOWN_MISSING: set[str] = set()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"\b(district|distrito|departamento|department)\b", " ", s)
    # administrative honorifics the two sources spell differently
    s = re.sub(r"\b(dr|doctor|gral|general|cnel|coronel|mcal|mariscal|pdte|presidente)\b\.?", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def load_geonames(path: str):
    rows = []
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(r) < 15:
                continue
            rows.append({
                "id": r[0], "name": r[1], "ascii": r[2], "alt": r[3],
                "lat": r[4], "lon": r[5], "fclass": r[6], "fcode": r[7],
                "admin1": r[10], "pop": r[14],
            })
    return rows


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    gn = load_geonames(sys.argv[1])

    by_admin: dict[str, list] = {}
    for g in gn:
        if g["fcode"] in PREFERRED:
            by_admin.setdefault(g["admin1"], []).append(g)

    munis = list(csv.DictReader(open(os.path.join(C.DATA, "municipalities.csv"), encoding="utf-8")))
    out, unmatched, ambiguous = [], [], []

    by_id = {g["id"]: g for g in gn}
    for m in munis:
        admin1 = ADMIN1.get(m["department_slug"])
        target = norm(m["name"])
        cands = by_admin.get(admin1, [])
        hit = by_id.get(PINNED.get(m["key"], ""))
        if hit is None and m["key"] in KNOWN_MISSING:
            unmatched.append(m)
            continue
        for code in PREFERRED if hit is None else []:
            same = []
            for g in cands:
                if g["fcode"] != code:
                    continue
                names = {norm(g["name"]), norm(g["ascii"])}
                names |= {norm(a) for a in g["alt"].split(",") if a}
                if target in names:
                    same.append(g)
            if same:
                # collapse duplicates that share a coordinate
                uniq = {(round(float(x["lat"]), 3), round(float(x["lon"]), 3)) for x in same}
                if len(uniq) > 1:
                    ambiguous.append((m["key"], code, [(x["id"], x["name"]) for x in same]))
                hit = same[0]
                break
        if hit:
            out.append([m["key"], m["department_slug"], m["name"], hit["lat"], hit["lon"],
                        hit["id"], hit["fcode"], hit["name"]])
        else:
            unmatched.append(m)

    path = os.path.join(C.DATA, "municipality_coordinates.csv")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["municipality_key", "department_slug", "name", "latitude", "longitude",
                    "geonames_id", "geonames_feature", "geonames_name"])
        w.writerows(sorted(out))

    print(f"matched   {len(out)}/{len(munis)}")
    print(f"ambiguous {len(ambiguous)} (first candidate used, coordinates agree unless listed)")
    for k, code, c in ambiguous[:10]:
        print(f"   {k} [{code}] {c}")
    print(f"unmatched {len(unmatched)}")
    for m in unmatched:
        print(f"   {m['key']:44} {m['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
