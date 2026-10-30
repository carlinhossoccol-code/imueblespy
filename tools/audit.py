#!/usr/bin/env python3
"""InmueblesPY static homologation suite.

Runs every check that can be evaluated from the source corpus without a
browser. Each check returns a list of failures; the process exits non-zero when
any blocking check fails, so it can gate a deploy.

Usage:
    python3 tools/audit.py              # run everything
    python3 tools/audit.py links canon  # run named checks only
"""
from __future__ import annotations

import collections
import glob
import html as _html
import json
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import corpus as C  # noqa: E402
import facts  # noqa: E402

SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
XH_NS = "{http://www.w3.org/1999/xhtml}"

CHECKS: dict[str, "Check"] = {}


class Check:
    def __init__(self, key, title, fn, blocking=True):
        self.key, self.title, self.fn, self.blocking = key, title, fn, blocking


def check(key, title, blocking=True):
    def deco(fn):
        CHECKS[key] = Check(key, title, fn, blocking)
        return fn

    return deco


# --------------------------------------------------------------------------- #
# corpus cache
# --------------------------------------------------------------------------- #
class Corpus:
    def __init__(self):
        self.paths = C.all_pages()
        self.src = {p: C.read(p) for p in self.paths}
        self.urls = {C.rel_url(p) for p in self.paths}
        self.dataset = C.load_json("dataset.json", {}) or {}

    def pages(self, pattern: str | None = None):
        for p in self.paths:
            if pattern is None or re.search(pattern, C.rel_url(p)):
                yield p, self.src[p]


CP: Corpus = None  # type: ignore


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
@check("canon", "Canonical URL matches the page's own location")
def c_canon():
    bad = []
    for p, s in CP.pages():
        # A noindex redirect stub deliberately points at its destination.
        if re.search(r'http-equiv="refresh"', s) and "noindex" in s:
            continue
        m = re.search(r'<link href="([^"]+)" rel="canonical"', s) or re.search(
            r'<link rel="canonical" href="([^"]+)"', s
        )
        if not m:
            bad.append((C.rel_url(p), "missing canonical"))
            continue
        want = C.canonical_of(p)
        if m.group(1) != want:
            bad.append((C.rel_url(p), f"canonical={m.group(1)} want={want}"))
    return bad


@check("hreflang", "hreflang pairs are present, absolute and reciprocal")
def c_hreflang():
    bad = []
    alts: dict[str, dict[str, str]] = {}
    for p, s in CP.pages():
        u = C.rel_url(p)
        found = dict(re.findall(r'<link href="([^"]+)" hreflang="([^"]+)" rel="alternate"', s))
        found.update({v: k for k, v in []})
        pairs = {lg: href for href, lg in re.findall(r'<link href="([^"]+)" hreflang="([^"]+)" rel="alternate"', s)}
        alts[u] = pairs
        for href in pairs.values():
            if not href.startswith(C.CANONICAL_HOST):
                bad.append((u, f"non-canonical-host hreflang {href}"))
    # reciprocity
    for u, pairs in alts.items():
        if not pairs:
            continue
        for lg, href in pairs.items():
            if lg == "x-default":
                continue
            other = href[len(C.CANONICAL_HOST):]
            if other == u:
                continue
            if other not in CP.urls:
                bad.append((u, f"hreflang target does not exist: {other}"))
            elif alts.get(other) and alts[other].get(lg) != href:
                bad.append((u, f"hreflang not reciprocal for {lg}: {other}"))
    return bad


@check("links", "Internal links resolve to a real page or asset")
def c_links():
    bad = []
    assets = set()
    for dirpath, _d, files in os.walk(os.path.join(C.SITE, "assets")):
        for f in files:
            assets.add("/" + os.path.relpath(os.path.join(dirpath, f), C.SITE).replace(os.sep, "/"))
    extra = {"/robots.txt", "/sitemap.xml", "/llms.txt"}
    for f in glob.glob(os.path.join(C.SITE, "sitemaps", "*.xml")):
        extra.add("/" + os.path.relpath(f, C.SITE).replace(os.sep, "/"))
    for p, s in CP.pages():
        u = C.rel_url(p)
        for href in re.findall(r'href="(/[^"#?]*)', s):
            href = urllib.parse.unquote(href)
            if href in CP.urls or href in assets or href in extra:
                continue
            bad.append((u, f"dead link {href}"))
        for src in re.findall(r'src="(/[^"#?]*)', s):
            if src not in assets:
                bad.append((u, f"dead asset {src}"))
    return bad


@check("sitemap_cover", "Every canonical page is in exactly one sitemap")
def c_sitemap_cover():
    bad = []
    locs: list[str] = []
    for f in sorted(glob.glob(os.path.join(C.SITE, "sitemaps", "*.xml"))):
        root = ET.parse(f).getroot()
        for url in root.findall(f"{SM_NS}url"):
            locs.append(url.find(f"{SM_NS}loc").text.strip())
    dupes = [u for u, n in collections.Counter(locs).items() if n > 1]
    for u in dupes:
        bad.append((u, "listed in more than one sitemap"))
    inmap = {u[len(C.CANONICAL_HOST):] for u in locs}
    noindex = set()
    for p, s in CP.pages():
        if re.search(r'name="robots"[^>]*content="[^"]*noindex|content="[^"]*noindex[^"]*" name="robots"', s):
            noindex.add(C.rel_url(p))
    for u in sorted(CP.urls - inmap - noindex):
        bad.append((u, "indexable page missing from sitemaps"))
    for u in sorted(inmap - CP.urls):
        bad.append((u, "sitemap URL has no corresponding page"))
    for u in sorted(inmap & noindex):
        bad.append((u, "noindex page present in sitemap"))
    return bad


@check("sitemap_shape", "Sitemap XML is valid, absolute, canonical-host and index-complete")
def c_sitemap_shape():
    bad = []
    idx = os.path.join(C.SITE, "sitemap.xml")
    if not os.path.exists(idx):
        return [("/sitemap.xml", "missing")]
    listed = {
        e.find(f"{SM_NS}loc").text.strip()
        for e in ET.parse(idx).getroot().findall(f"{SM_NS}sitemap")
    }
    on_disk = {
        C.CANONICAL_HOST + "/" + os.path.relpath(f, C.SITE).replace(os.sep, "/")
        for f in glob.glob(os.path.join(C.SITE, "sitemaps", "*.xml"))
    }
    for u in sorted(on_disk - listed):
        bad.append((u, "sitemap file not referenced by sitemap.xml"))
    for u in sorted(listed - on_disk):
        bad.append((u, "sitemap.xml references a missing file"))
    for f in sorted(glob.glob(os.path.join(C.SITE, "sitemaps", "*.xml"))):
        rel = "/" + os.path.relpath(f, C.SITE).replace(os.sep, "/")
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError as exc:
            bad.append((rel, f"invalid XML: {exc}"))
            continue
        urls = root.findall(f"{SM_NS}url")
        if len(urls) > 50000:
            bad.append((rel, f"{len(urls)} URLs exceeds the 50000 limit"))
        if os.path.getsize(f) > 50 * 1024 * 1024:
            bad.append((rel, "file exceeds 50MB"))
        for url in urls:
            loc = url.find(f"{SM_NS}loc").text.strip()
            if not loc.startswith(C.CANONICAL_HOST + "/"):
                bad.append((rel, f"non-canonical loc {loc}"))
            if "?" in loc:
                bad.append((rel, f"loc carries query parameters {loc}"))
            if any(k in loc for k in ("onrender.com", "http://")):
                bad.append((rel, f"loc points at a non-production host {loc}"))
            for n in ("changefreq", "priority"):
                if url.find(f"{SM_NS}{n}") is not None:
                    bad.append((rel, f"{loc} declares <{n}>"))
    return bad


@check("lastmod", "Sitemap lastmod is derived from page content")
def c_lastmod():
    store = C.load_json("lastmod.json", {}) or {}
    if not store:
        return [("data/lastmod.json", "missing; run tools/build_sitemaps.py")]
    bad = []
    for f in glob.glob(os.path.join(C.SITE, "sitemaps", "*.xml")):
        rel = "/" + os.path.relpath(f, C.SITE).replace(os.sep, "/")
        for url in ET.parse(f).getroot().findall(f"{SM_NS}url"):
            loc = url.find(f"{SM_NS}loc").text.strip()
            u = loc[len(C.CANONICAL_HOST):]
            lm = url.find(f"{SM_NS}lastmod")
            rec = store.get(u)
            if rec is None:
                bad.append((rel, f"{u} is not tracked in lastmod.json"))
            elif lm is None:
                bad.append((rel, f"{u} has no lastmod"))
            elif lm.text.strip() != rec["lastmod"]:
                bad.append((rel, f"{u} lastmod {lm.text.strip()} != tracked {rec['lastmod']}"))
    # The store must reflect the pages actually on disk.
    for p in CP.paths:
        u = C.rel_url(p)
        rec = store.get(u)
        if rec and rec["hash"] != C.content_fingerprint(CP.src[p]):
            bad.append((u, "content changed since the last sitemap build"))
    return bad


@check("counts", "Every published profile count agrees with the dataset")
def c_counts():
    if not CP.dataset:
        return [("data/dataset.json", "missing; run tools/extract_dataset.py")]
    F = facts.Facts(CP.dataset)
    bad = []
    for p, s in CP.pages(r"^/(es/venta|pt-br/comprar)/"):
        u = C.rel_url(p)
        key = F.city_key_from_url(u)
        if not key:
            continue
        local, others, chans = F.profiles[key], F.others_in_dept(key), F.with_channel[key]
        hoods = len(F.neighbourhoods(key))

        for m in re.finditer(
            r'<td><a href="/(?:es/zonas|pt-br/regioes)/([a-z0-9-]+(?:/[a-z0-9-]+)?)/">[^<]*</a></td>'
            r"<td>[^<]*</td><td>(\d+)</td>", s):
            if int(m.group(2)) != F.profiles[m.group(1)]:
                bad.append((u, f"table: {m.group(1)} claims {m.group(2)}, dataset {F.profiles[m.group(1)]}"))
        for m in re.finditer(
            r'<a href="/(?:es/zonas|pt-br/regioes)/([a-z0-9-]+(?:/[a-z0-9-]+)?)/">[^<]*</a>\s*<span>\((\d+) perfi', s):
            if int(m.group(2)) != F.profiles[m.group(1)]:
                bad.append((u, f"related list: {m.group(1)} claims {m.group(2)}"))

        for label, want in (
            (r"(?:Perfiles con sede indicada en la ciudad|Perfis com sede informada na cidade)", local),
            (r"(?:Zonas registradas en la base|Regiões cadastradas na base)", hoods),
        ):
            m = re.search(r">" + label + r"</dt><dd>(\d+)</dd>", s)
            if m and int(m.group(1)) != want:
                bad.append((u, f"fact {label[:28]} claims {m.group(1)}, dataset {want}"))

        for pat, wants in (
            (r"reúne (\d+) perfiles con ciudad declarada en [^<]*? y (\d+) en otras localidades", (local, others)),
            (r"reúne (\d+) perfis com sede informada em [^<]*? e (\d+) em outras cidades", (local, others)),
            (r"Se identificaron (\d+) perfiles con sede declarada en la ciudad; (\d+) tienen", (local, chans)),
            (r"Foram encontrados (\d+) perfis com sede informada na cidade; (\d+) possuem", (local, chans)),
        ):
            m = re.search(pat, s)
            if m and (int(m.group(1)), int(m.group(2))) != wants:
                bad.append((u, f"summary claims {m.groups()}, dataset {wants}"))
    return bad


@check("lang", "No cross-language or untranslated field labels leak between /es/ and /pt-br/")
def c_lang():
    # Terms that must never appear in the other language's pages. Proper names
    # are excluded by anchoring on field labels and sentence fragments.
    es_forbidden = [
        "Site oficial da imobiliária",
        "Pesquisa própria do diretório",
        ">telefone<",
        ">Telefone<",
        ">Website<",
        "imobiliária",
        "imobiliárias",
        "Fonte consultada",
        "Cidade informada",
    ]
    pt_forbidden = [
        "Ciudad informada",
        "Dirección publicada",
        "Teléfono reportado",
        "Fuente consultada",
        "Fecha de investigación",
        ">Sitio web<",
    ]
    bad = []
    for p, s in CP.pages():
        lang = C.page_lang(p)
        terms = es_forbidden if lang == "es" else pt_forbidden if lang == "pt-br" else []
        for t in terms:
            if t in s:
                bad.append((C.rel_url(p), f"foreign-language fragment {t!r}"))
    return bad


NAV_RE = re.compile(r'<nav aria-label="Breadcrumb"[^>]*>(.*?)</nav>', re.S)
CRUMB_ITEM_RE = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>|<strong>(.*?)</strong>', re.S)


def _visible_trail(src, page_url):
    m = NAV_RE.search(src)
    if not m:
        return None
    out = []
    for mm in CRUMB_ITEM_RE.finditer(m.group(1)):
        if mm.group(1) is not None:
            href, label = mm.group(1), mm.group(2)
        else:
            href, label = page_url, mm.group(3)
        label = _html.unescape(C.TAG_RE.sub("", label)).strip()
        if label:
            out.append((label, href if href.startswith("http") else C.CANONICAL_HOST + href))
    return out or None


@check("jsonld", "JSON-LD parses and every BreadcrumbList matches the visible breadcrumb")
def c_jsonld():
    bad = []
    for p, s in CP.pages():
        u = C.rel_url(p)
        visible = _visible_trail(s, u)
        for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
            try:
                data = json.loads(blob)
            except json.JSONDecodeError as exc:
                bad.append((u, f"invalid JSON-LD: {exc}"))
                continue
            for node in data if isinstance(data, list) else [data]:
                if node.get("@type") != "BreadcrumbList":
                    continue
                items = node.get("itemListElement", [])
                got = [(str(i.get("name", "")), str(i.get("item", ""))) for i in items]
                for i, it in enumerate(items):
                    if not it.get("item"):
                        bad.append((u, "breadcrumb item without URL"))
                    if it.get("position") != i + 1:
                        bad.append((u, f"breadcrumb position {it.get('position')} out of order"))
                if visible and got != visible:
                    bad.append((u, f"breadcrumb JSON-LD {[g[0] for g in got]} != visible {[v[0] for v in visible]}"))
    return bad


@check("headings", "Exactly one H1 and no skipped heading levels")
def c_headings():
    bad = []
    for p, s in CP.pages():
        u = C.rel_url(p)
        h1 = re.findall(r"<h1\b", s)
        if len(h1) != 1:
            bad.append((u, f"{len(h1)} H1 elements"))
        levels = [int(m) for m in re.findall(r"<h([1-6])\b", s)]
        prev = 0
        for lv in levels:
            if prev and lv > prev + 1:
                bad.append((u, f"heading jumps from h{prev} to h{lv}"))
                break
            prev = lv
    return bad


@check("meta", "Title and meta description present and within sane length")
def c_meta():
    bad = []
    for p, s in CP.pages():
        u = C.rel_url(p)
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        d = re.search(r'<meta content="([^"]*)" name="description"', s) or re.search(
            r'<meta name="description" content="([^"]*)"', s
        )
        if not t or not t.group(1).strip():
            bad.append((u, "missing title"))
        elif len(_html.unescape(t.group(1))) > 95:
            bad.append((u, f"title {len(t.group(1))} chars"))
        if not d or not d.group(1).strip():
            bad.append((u, "missing meta description"))
        elif not (50 <= len(_html.unescape(d.group(1))) <= 185):
            bad.append((u, f"meta description {len(d.group(1))} chars"))
    return bad


@check("images", "Images declare dimensions, alt text and sane loading hints")
def c_images():
    bad = []
    for p, s in CP.pages():
        u = C.rel_url(p)
        imgs = re.findall(r"<img\b[^>]*>", s)
        hi = 0
        for tag in imgs:
            if 'alt="' not in tag:
                bad.append((u, f"img without alt: {tag[:90]}"))
            if "width=" not in tag or "height=" not in tag:
                bad.append((u, f"img without intrinsic size: {tag[:90]}"))
            if 'fetchpriority="high"' in tag:
                hi += 1
        if hi > 1:
            bad.append((u, f"{hi} images marked fetchpriority=high"))
    return bad


@check("banner", "PT-BR advertising banner on every PT page, none on ES, after first useful section")
def c_banner():
    bad = []
    for p, s in CP.pages():
        u = C.rel_url(p)
        lang = C.page_lang(p)
        has = 'class="mnpb"' in s or "mnpb-card" in s
        if lang == "es" and has:
            bad.append((u, "advertising banner present on a Spanish page"))
        if lang == "pt-br" and not has:
            bad.append((u, "advertising banner missing on a Brazilian page"))
        if lang == "pt-br" and has:
            if 'rel="sponsored' not in s:
                bad.append((u, "banner link lacks rel=sponsored"))
            if "Publicidade" not in s:
                bad.append((u, "banner lacks a Publicidade label"))
            b = s.find("mnpb")
            first = s.find('class="company"')
            if first > 0 and b < first:
                bad.append((u, "banner precedes the first professional result"))
    return bad


@check("doorway", "Category pages inside a city are substantively different from each other")
def c_doorway():
    """Flags city/category clusters whose main content is near-identical."""
    bad = []
    THRESH = 0.62
    for lang, seg in C.BUY_SEGMENT.items():
        base = os.path.join(C.SITE, lang, seg)
        if not os.path.isdir(base):
            continue
        for dept in sorted(os.listdir(base)):
            dpath = os.path.join(base, dept)
            if not os.path.isdir(dpath):
                continue
            for city in sorted(os.listdir(dpath)):
                cpath = os.path.join(dpath, city)
                if not os.path.isdir(cpath):
                    continue
                cats = [
                    (cat, os.path.join(cpath, cat, "index.html"))
                    for cat in sorted(os.listdir(cpath))
                    if os.path.exists(os.path.join(cpath, cat, "index.html"))
                ]
                if len(cats) < 2:
                    continue
                sh = {
                    cat: C.shingles(C.visible_text(CP.src[fp], main_only=True))
                    for cat, fp in cats
                    if fp in CP.src
                }
                keys = sorted(sh)
                for i in range(len(keys)):
                    for j in range(i + 1, len(keys)):
                        v = C.jaccard(sh[keys[i]], sh[keys[j]])
                        if v > THRESH:
                            bad.append(
                                (
                                    f"/{lang}/{seg}/{dept}/{city}/",
                                    f"{keys[i]} vs {keys[j]} similarity {v:.2f} > {THRESH}",
                                )
                            )
    return bad


@check("doorway_cities", "Same-category pages in different cities carry city-specific substance")
def c_doorway_cities():
    """The second doorway axis: one category compared across municipalities.

    These pages legitimately share the category guidance, so a high score is
    not automatically a defect; what matters is that each page still carries
    its own municipal data. The check samples within each department, where
    similarity is highest, and reports the worst pairs.
    """
    THRESH = 0.72
    bad = []
    for lang, seg in C.BUY_SEGMENT.items():
        base = os.path.join(C.SITE, lang, seg)
        if not os.path.isdir(base):
            continue
        for cat in ("terrenos", "casas"):
            for dept in sorted(os.listdir(base)):
                dpath = os.path.join(base, dept)
                if not os.path.isdir(dpath):
                    continue
                files = []
                for city in sorted(os.listdir(dpath)):
                    fp = os.path.join(dpath, city, cat, "index.html")
                    if fp in CP.src:
                        files.append((city, fp))
                if len(files) < 2:
                    continue
                sh = {c: C.shingles(C.visible_text(CP.src[fp], main_only=True)) for c, fp in files}
                keys = sorted(sh)
                for i in range(len(keys)):
                    for j in range(i + 1, len(keys)):
                        v = C.jaccard(sh[keys[i]], sh[keys[j]])
                        if v > THRESH:
                            bad.append((f"/{lang}/{seg}/{dept}/*/{cat}/",
                                        f"{keys[i]} vs {keys[j]} similarity {v:.2f} > {THRESH}"))
    return bad


@check("orphans", "No indexable page is unreachable from internal links")
def c_orphans():
    inbound = collections.Counter()
    for _p, s in CP.pages():
        for href in set(re.findall(r'href="(/[^"#?]*)', s)):
            inbound[urllib.parse.unquote(href)] += 1
    bad = []
    for u in sorted(CP.urls):
        if u in ("/", "/es/", "/pt-br/"):
            continue
        if inbound[u] == 0:
            bad.append((u, "no internal inbound links"))
    return bad


@check("noplaceholder", "No development notes, placeholders or invented credentials in public HTML")
def c_noplaceholder():
    # Case-sensitive for the code markers: "todo"/"todos" are ordinary words
    # in both Spanish and Portuguese.
    cased = [r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b", r"\bTBD\b"]
    loose = [
        r"\blorem ipsum\b", r"\bplaceholder\b", r"\bem breve\b",
        r"\bpr[oó]ximamente\b", r"\bcoming soon\b", r"\bRUC\s*[:n]\b",
    ]
    bad = []
    for p, s in CP.pages():
        txt = C.visible_text(s)
        for pat in cased:
            m = re.search(pat, txt)
            if m:
                bad.append((C.rel_url(p), f"suspicious copy {m.group(0)!r}"))
        for pat in loose:
            m = re.search(pat, txt, re.I)
            if m:
                bad.append((C.rel_url(p), f"suspicious copy {m.group(0)!r}"))
    return bad


@check("splash", "Site root sends visitors straight to a real homepage")
def c_splash():
    p = os.path.join(C.SITE, "index.html")
    if not os.path.exists(p):
        return [("/", "missing root index.html")]
    s = C.read(p)
    txt = C.visible_text(s)
    bad = []
    if re.search(r"Eleg[íi] tu idioma|Escolha seu idioma", txt):
        bad.append(("/", "root still renders an interstitial language chooser"))
    if not re.search(r'http-equiv="refresh"|<link rel="canonical" href="https://inmueblespy\.com\.py/es/"', s, re.I):
        if 'content="0; url=/es/"' not in s and "0;url=/es/" not in s.replace(" ", ""):
            bad.append(("/", "root does not redirect to /es/"))
    return bad


@check("robots", "robots.txt is present, allows search and AI search crawlers, and points at the sitemap")
def c_robots():
    p = os.path.join(C.SITE, "robots.txt")
    if not os.path.exists(p):
        return [("/robots.txt", "missing")]
    s = C.read(p)
    bad = []
    if "Sitemap:" not in s:
        bad.append(("/robots.txt", "no Sitemap directive"))
    if C.CANONICAL_HOST not in s:
        bad.append(("/robots.txt", "sitemap not on the canonical host"))
    low = s.lower()
    for agent in ("googlebot", "bingbot", "oai-searchbot"):
        # a named block that disallows everything would be a blocker
        m = re.search(rf"user-agent:\s*{agent}\s*\n(.*?)(?=\nuser-agent:|\Z)", low, re.S)
        if m and re.search(r"disallow:\s*/\s*$", m.group(1), re.M):
            bad.append(("/robots.txt", f"{agent} is fully disallowed"))
    return bad


@check("llms", "llms.txt, when present, is factual and uses canonical URLs", blocking=False)
def c_llms():
    p = os.path.join(C.SITE, "llms.txt")
    if not os.path.exists(p):
        return [("/llms.txt", "not present")]
    s = C.read(p)
    bad = []
    for u in re.findall(r"https?://[^\s)\]]+", s):
        if not u.startswith(C.CANONICAL_HOST) and "ine.gov.py" not in u:
            bad.append(("/llms.txt", f"non-canonical URL {u}"))
            continue
        if u.startswith(C.CANONICAL_HOST):
            rel = u[len(C.CANONICAL_HOST):]
            if rel and rel not in CP.urls and not rel.startswith("/sitemap") and rel != "/robots.txt":
                bad.append(("/llms.txt", f"URL does not exist: {rel}"))
    # Only affirmative claims are a problem: the file legitimately states that
    # the portal does NOT deal in rentals and does NOT certify anyone.
    low = s.lower()
    for pat, why in (
        (r"(?<!no )(?<!não )(?:ofrece|publica|incluye) [^.\n]*alqu", "appears to offer rentals"),
        (r"(?<!não )(?:oferece|publica|inclui) [^.\n]*alugu", "appears to offer rentals"),
        (r"(?<!no )garantiza", "unsupported guarantee"),
        (r"(?<!no )certifica", "unsupported certification"),
        (r"recomendaci[oó]n (?:garantizada|asegurada)", "claims guaranteed AI recommendation"),
    ):
        m = re.search(pat, low)
        if m:
            bad.append(("/llms.txt", f"{why}: {m.group(0)[:60]!r}"))
    return bad


# --------------------------------------------------------------------------- #
def main() -> int:
    global CP
    wanted = sys.argv[1:] or list(CHECKS)
    unknown = [w for w in wanted if w not in CHECKS]
    if unknown:
        print(f"unknown checks: {unknown}\navailable: {list(CHECKS)}")
        return 2
    print("loading corpus ...", flush=True)
    CP = Corpus()
    print(f"{len(CP.paths)} pages\n")

    failed_blocking = 0
    summary = []
    for key in wanted:
        chk = CHECKS[key]
        issues = chk.fn()
        status = "PASS" if not issues else ("FAIL" if chk.blocking else "WARN")
        if issues and chk.blocking:
            failed_blocking += 1
        summary.append((status, key, chk.title, len(issues)))
        print(f"[{status}] {key:14} {chk.title}")
        if issues:
            print(f"         {len(issues)} issue(s); showing up to 8:")
            for u, msg in issues[:8]:
                print(f"           - {u}: {msg}")
            if len(issues) > 8:
                print(f"           ... {len(issues) - 8} more")
        print()

    print("=" * 72)
    for status, key, _title, n in summary:
        print(f"{status:5} {key:16} {n} issue(s)")
    print("=" * 72)
    print(f"{failed_blocking} blocking check(s) failed")
    return 1 if failed_blocking else 0


if __name__ == "__main__":
    sys.exit(main())
