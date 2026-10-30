"""Derived facts computed once from data/dataset.json.

Both the audit and the codemods read their numbers from here, so a page claim
is always compared against — and rewritten from — the same authority.
"""
from __future__ import annotations

import collections
import re
import statistics

import corpus as C

CITY_H1_RE = re.compile(r"Comprar propiedades en (.*?): ciudad e inmobiliarias")


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
