"""Rebuild every BreadcrumbList from the breadcrumb the user actually sees.

Three defects were present: profile pages used a slug-derived name that
included the internal numeric id ("366 Nisa Inmobiliaria Luque") and skipped
the directory level; category pages substituted "Venta" for the department
shown on screen; and slug title-casing produced "25 De Diciembre" where the
page reads "25 de Diciembre". Deriving the markup from the rendered nav keeps
structured data and visible content in agreement by construction.
"""
import html as _html
import json
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import corpus as C

ORDER = 20
TITLE = "Derive BreadcrumbList JSON-LD from the visible breadcrumb"
SELECT = None

NAV_RE = re.compile(r'<nav aria-label="Breadcrumb"[^>]*>(.*?)</nav>', re.S)
ITEM_RE = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>|<strong>(.*?)</strong>', re.S)


def visible_trail(src, page_url):
    m = NAV_RE.search(src)
    if not m:
        return None
    trail = []
    for mm in ITEM_RE.finditer(m.group(1)):
        if mm.group(1) is not None:
            href, label = mm.group(1), mm.group(2)
        else:
            href, label = page_url, mm.group(3)
        label = _html.unescape(C.TAG_RE.sub("", label)).strip()
        if not label:
            continue
        url = href if href.startswith("http") else C.CANONICAL_HOST + href
        trail.append((label, url))
    return trail or None


def apply(path, src, ctx):
    page_url = C.rel_url(path)
    trail = visible_trail(src, page_url)
    if not trail:
        return src

    wanted = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": nm, "item": u}
            for i, (nm, u) in enumerate(trail)
        ],
    }

    def rewrite(m):
        blob = m.group(1)
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            return m.group(0)
        many = isinstance(data, list)
        nodes = data if many else [data]
        hit = False
        for idx, node in enumerate(nodes):
            if node.get("@type") == "BreadcrumbList":
                new = dict(wanted)
                if "@context" in node:
                    new = {"@context": node["@context"], **wanted}
                nodes[idx] = new
                hit = True
        if not hit:
            return m.group(0)
        out = json.dumps(nodes if many else nodes[0], ensure_ascii=False, separators=(",", ":"))
        return f'<script type="application/ld+json">{out}</script>'

    return re.sub(r'<script type="application/ld\+json">(.*?)</script>', rewrite, src, flags=re.S)
