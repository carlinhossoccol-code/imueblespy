"""Derived facts computed once from data/dataset.json.

Both the audit and the codemods read their numbers from here, so a page claim
is always compared against — and rewritten from — the same authority.
"""
from __future__ import annotations

import collections
import csv
import math
import os
import re
import statistics
import unicodedata

import corpus as C

CITY_H1_RE = re.compile(r"Comprar propiedades en (.*?): ciudad e inmobiliarias")

# Kept in step with tools/extract_dataset.py.
CITY_NAME_ALIASES = {
    "Juan León Mallorquín": "Doctor Juan León Mallorquín",
    "Juan Emilio O\u2019Leary": "Juan Emiliano O'Leary",
    "San Pedro del Ycuamandiyú": "San Pedro de Ycuamandiyú",
}


class Facts:
    def __init__(self, dataset: dict | None = None):
        ds = dataset or C.load_json("dataset.json", {}) or {}
        self.raw = ds
        self.cities: dict = ds.get("cities", {})
        self.agencies: dict = ds.get("agencies", {})
        self.price_refs: dict = ds.get("price_refs", {})
        pbc: dict = ds.get("profiles_by_city", {})

        self.key_by_name: dict[str, str] = {}
        self.name_by_key: dict[str, str] = {}
        for key, c in self.cities.items():
            m = CITY_H1_RE.search(c.get("h1") or "")
            if m:
                self.key_by_name.setdefault(m.group(1).strip(), key)
                self.name_by_key[key] = m.group(1).strip()
        # The directory spells a few municipalities differently from their page.
        # Without these, the professionals seated there resolve to no location
        # and silently drop out of the proximity ranking.
        for alias, canonical in CITY_NAME_ALIASES.items():
            if canonical in self.key_by_name:
                self.key_by_name.setdefault(alias, self.key_by_name[canonical])

        self.profiles: dict[str, int] = collections.defaultdict(int)
        self.with_channel: dict[str, int] = collections.defaultdict(int)
        self.profile_ids: dict[str, list] = {}
        for name, rec in pbc.items():
            key = rec.get("city_key")
            if not key:
                continue
            self.profiles[key] = rec["profiles"]
            self.with_channel[key] = rec["with_channel"]
            self.profile_ids[key] = rec["profile_ids"]

        self.dept_cities: dict[str, list] = collections.defaultdict(list)
        for key, c in self.cities.items():
            self.dept_cities[c["department_slug"]].append(key)
        for v in self.dept_cities.values():
            v.sort()

        self._load_coordinates()
        self._load_networks()

    # ------------------------------------------------------------------ #
    def _load_coordinates(self) -> None:
        """Municipality coordinates, and each professional's seat location.

        Sourced from GeoNames via tools/match_geonames.py. One municipality
        (Boquerón) has no coordinate; everything here degrades to an empty
        result for it rather than guessing a position.
        """
        self.coords: dict[str, tuple] = {}
        path = os.path.join(C.DATA, "municipality_coordinates.csv")
        if os.path.exists(path):
            with open(path, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    self.coords[r["municipality_key"]] = (
                        float(r["latitude"]), float(r["longitude"]))

        # professional id -> municipality key of its declared seat
        self.seat_of: dict[str, str] = {}
        for pid, a in self.agencies.items():
            city = a.get("city")
            if not city:
                continue
            key = self.key_by_name.get(city)
            if key:
                self.seat_of[pid] = key

    def distance_km(self, a: str, b: str):
        """Great-circle distance between two municipalities, or None."""
        pa, pb = self.coords.get(a), self.coords.get(b)
        if not pa or not pb:
            return None
        R = 6371.0
        la1, lo1, la2, lo2 = map(math.radians, (pa[0], pa[1], pb[0], pb[1]))
        h = (math.sin((la2 - la1) / 2) ** 2
             + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(h))

    def local_professionals(self, key: str) -> list:
        """Professional ids whose declared seat is this municipality."""
        return sorted((pid for pid, k in self.seat_of.items() if k == key), key=int)

    def nearest_professionals(self, key: str, limit: int = 6) -> list:
        """(professional id, seat key, km) for the closest seats elsewhere.

        Ranked by real distance rather than by department membership, so two
        neighbouring municipalities no longer receive an identical list. A
        distance says where a firm is, never that it covers this municipality.
        """
        if key not in self.coords:
            return []
        out = []
        for pid, seat in self.seat_of.items():
            if seat == key:
                continue
            d = self.distance_km(key, seat)
            if d is None:
                continue
            out.append((pid, seat, d))
        out.sort(key=lambda t: (round(t[2], 3), int(t[0])))
        return out[:limit]

    def _load_networks(self) -> None:
        """Group agency records that are branches of the same brand.

        A brand with declared seats in several municipalities is documented
        evidence of regional presence, which is the one relevance signal this
        dataset genuinely supports. It says nothing about specialisation by
        property type, which is never recorded and so is never claimed.
        """
        groups: dict[str, list] = collections.defaultdict(list)
        for pid, a in self.agencies.items():
            if a.get("kind") != "agency" or not a.get("name"):
                continue
            groups[self._brand_key(a["name"])].append(pid)

        self.network_of: dict[str, dict] = {}
        self.networks: dict[str, dict] = {}
        for key, ids in groups.items():
            cities = {self.agencies[i].get("city") for i in ids if self.agencies[i].get("city")}
            if len(cities) < 2:
                continue
            depts = {self.agencies[i].get("department") for i in ids if self.agencies[i].get("department")}
            rec = {
                "key": key,
                "name": self._brand_name(self.agencies[sorted(ids, key=int)[0]]["name"]),
                "ids": sorted(ids, key=int),
                "cities": sorted(cities),
                "departments": sorted(d for d in depts if d),
            }
            self.networks[key] = rec
            for i in ids:
                self.network_of[i] = rec

    @staticmethod
    def _brand_name(name: str) -> str:
        n = re.split(r"\s+[—–-]\s+", name)[0].strip()
        n = re.sub(r"\b(sucursal|agencia|agência|casa central|casa matriz|filial)\b.*", "",
                   n, flags=re.I)
        return n.strip(" -—,")

    @classmethod
    def _brand_key(cls, name: str) -> str:
        n = unicodedata.normalize("NFD", cls._brand_name(name).lower())
        n = "".join(c for c in n if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]+", " ", n).strip()

    def bearing_deg(self, a: str, b: str):
        """Initial bearing from a to b, in degrees, or None."""
        pa, pb = self.coords.get(a), self.coords.get(b)
        if not pa or not pb:
            return None
        la1, lo1, la2, lo2 = map(math.radians, (pa[0], pa[1], pb[0], pb[1]))
        dl = lo2 - lo1
        y = math.sin(dl) * math.cos(la2)
        x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dl)
        return (math.degrees(math.atan2(y, x)) + 360) % 360

    def dept_seat(self, key: str):
        """The most populous municipality of this department."""
        d = self.dept_of(key)
        best, bestpop = None, -1
        for k in self.dept_cities[d]:
            p = self.population(k) or 0
            if p > bestpop:
                best, bestpop = k, p
        return best

    def national_rank(self, key: str):
        """1-based rank by population among all municipalities in the dataset."""
        pops = sorted(
            ((self.population(k) or 0, k) for k in self.cities),
            key=lambda t: (-t[0], t[1]))
        for i, (_p, k) in enumerate(pops, 1):
            if k == key:
                return i, len(pops)
        return None, len(pops)

    def nearest_with_professionals(self, key: str):
        """(municipality key, km, count) for the closest place that has one.

        For a municipality with no seated professional this is the single most
        useful fact the dataset can offer a buyer: where the nearest one
        actually is, and how far.
        """
        if key not in self.coords:
            return None
        best = None
        for k in self.cities:
            if k == key or not self.profiles.get(k):
                continue
            d = self.distance_km(key, k)
            if d is None:
                continue
            if best is None or d < best[1]:
                best = (k, d, self.profiles[k])
        return best

    def nearest_municipalities(self, key: str, limit: int = 5) -> list:
        """(municipality key, km) for the closest other municipalities."""
        if key not in self.coords:
            return []
        out = [(k, self.distance_km(key, k)) for k in self.coords if k != key]
        out = [(k, d) for k, d in out if d is not None]
        out.sort(key=lambda t: (round(t[1], 3), t[0]))
        return out[:limit]

    # ------------------------------------------------------------------ #
    def dept_of(self, key: str) -> str:
        return self.cities[key]["department_slug"]

    def others_in_dept(self, key: str) -> int:
        """Profiles seated in the same department but not in this municipality."""
        d = self.dept_of(key)
        return sum(self.profiles[k] for k in self.dept_cities[d] if k != key)

    def population(self, key: str):
        return self.cities[key].get("population_2022")

    def dept_populations(self, dept: str) -> list:
        return [
            self.cities[k]["population_2022"]
            for k in self.dept_cities[dept]
            if self.cities[k].get("population_2022")
        ]

    def pop_rank(self, key: str):
        """1-based rank of this municipality by population inside its department."""
        d = self.dept_of(key)
        pops = sorted(self.dept_populations(d), reverse=True)
        mine = self.population(key)
        if mine is None or not pops:
            return None, len(pops)
        return pops.index(mine) + 1, len(pops)

    def pop_share(self, key: str):
        d = self.dept_of(key)
        tot = sum(self.dept_populations(d))
        mine = self.population(key)
        if not tot or mine is None:
            return None
        return round(100.0 * mine / tot, 1)

    def pop_median(self, dept: str):
        pops = self.dept_populations(dept)
        return int(statistics.median(sorted(pops))) if pops else None

    def neighbourhoods(self, key: str) -> list:
        return self.cities[key].get("neighbourhoods", [])

    def price_ref(self, key: str, category: str):
        return self.price_refs.get(f"{key}/{category}")

    def city_key_from_url(self, url: str):
        """Resolve a /es/venta/... or /pt-br/comprar/... URL to a city key."""
        m = re.match(r"^/(?:es/venta|pt-br/comprar)/([a-z0-9-]+)(?:/([a-z0-9-]+))?", url)
        if not m:
            return None
        a, b = m.group(1), m.group(2)
        if b and f"{a}/{b}" in self.cities:
            return f"{a}/{b}"
        if a in self.cities and (b is None or b in C.CATEGORIES):
            return a
        return None
