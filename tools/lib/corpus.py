"""Shared helpers for auditing and transforming the InmueblesPY pre-rendered corpus.

The published HTML under site/ is the project's source of truth: there is no
upstream generator in this repository. These helpers therefore treat the corpus
as a database that can be queried and rewritten idempotently.
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import os
import re
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "site")
DATA = os.path.join(ROOT, "data")

CANONICAL_HOST = "https://inmueblespy.com.py"

SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")

LANGS = ("es", "pt-br")
# category slug -> (es label, pt label)
CATEGORIES = {
    "terrenos": ("Terrenos", "Terrenos"),
    "casas": ("Casas", "Casas"),
    "departamentos": ("Departamentos", "Apartamentos"),
    "comerciales": ("Inmuebles comerciales", "Imóveis comerciais"),
}
# per-language URL segment for the buy family
BUY_SEGMENT = {"es": "venta", "pt-br": "comprar"}
ZONE_SEGMENT = {"es": "zonas", "pt-br": "regioes"}
AGENCY_SEGMENT = {"es": "inmobiliaria", "pt-br": "imobiliaria"}
AGENT_SEGMENT = {"es": "agente", "pt-br": "corretor"}
AGENCY_INDEX_SEGMENT = {"es": "inmobiliarias", "pt-br": "imobiliarias"}


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path: str, content: str) -> bool:
    """Write only when content actually changes. Returns True if written."""
    if os.path.exists(path) and read(path) == content:
        return False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return True


def all_pages(*, lang: str | None = None):
    """Yield every rendered page path under site/, sorted for determinism."""
    out = []
    for dirpath, _dirnames, filenames in os.walk(SITE):
        for name in filenames:
            if name != "index.html":
                continue
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, SITE)
            if lang and not rel.startswith(lang + os.sep) and rel != lang + os.sep + "index.html":
                if not rel.startswith(lang + "/"):
                    continue
            out.append(p)
    return sorted(out)


def rel_url(path: str) -> str:
    """site/es/venta/.../index.html -> /es/venta/.../"""
    rel = os.path.relpath(path, SITE).replace(os.sep, "/")
    rel = rel[: -len("index.html")]
    return "/" + rel if not rel.startswith("/") else rel


def canonical_of(path: str) -> str:
    return CANONICAL_HOST + rel_url(path)


def page_lang(path: str) -> str | None:
    rel = os.path.relpath(path, SITE).replace(os.sep, "/")
    for lang in LANGS:
        if rel == f"{lang}/index.html" or rel.startswith(f"{lang}/"):
            return lang
    return None


def main_html(src: str) -> str:
    i = src.find("<main")
    j = src.find("</main>")
    return src[i:j] if i >= 0 and j > i else ""


def visible_text(src: str, *, main_only: bool = False) -> str:
    s = main_html(src) if main_only else src
    s = SCRIPT_RE.sub(" ", s)
    s = TAG_RE.sub(" ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def shingles(text: str, n: int = 6) -> set:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def content_fingerprint(src: str) -> str:
    """Hash of the meaningful content, ignoring volatile wrappers.

    Used to derive honest sitemap <lastmod> values: the hash only changes when
    the visible content or the structured data changes.
    """
    main = main_html(src)
    ld = "".join(re.findall(r'<script type="application/ld\+json">(.*?)</script>', src, re.S))
    title = re.search(r"<title>(.*?)</title>", src, re.S)
    desc = re.search(r'<meta content="([^"]*)" name="description"', src) or re.search(
        r'<meta name="description" content="([^"]*)"', src
    )
    payload = "\n".join(
        [
            visible_text(main),
            re.sub(r"\s+", "", ld),
            title.group(1) if title else "",
            desc.group(1) if desc else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_json(name: str, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(name: str, obj) -> None:
    os.makedirs(DATA, exist_ok=True)
    p = os.path.join(DATA, name)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
