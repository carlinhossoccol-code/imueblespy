# -*- coding: utf-8 -*-
"""Rank nearby professionals by real distance instead of by department.

Every municipality in a department previously showed the same firms in the
same order, because "nearby" could only mean "somewhere in this department".
With coordinates from GeoNames each page can now list the seats that are
actually closest, and say how far away they are.

This is the differentiation the data supports: Mbaracayú's nearest seat is in
San Alberto 22 km away, Ñacunday's is in Santa Rita 48 km away, so the two
pages stop being interchangeable. A distance states where a firm is; it never
claims the firm covers this municipality, which the directory cannot show.

Cards are reused verbatim from the corpus so logos, badges and contact actions
stay exactly as they were; only their selection, order and the location line
change.
"""
import html as _html
import os
import re
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C
import facts as FA

ORDER = 90
TITLE = "List the geographically nearest professionals, with distances"
SELECT = r"^/(es|pt-br)/"

LIMIT = 6

HEAD = {
    "es": ("Profesionales más cercanos",
           "Distancia aproximada en línea recta entre los puntos de referencia de "
           "{city} y del municipio donde la empresa declara su sede; no es la "
           "distancia a una dirección. Tener la sede cerca no confirma que "
           "atiendan esta localidad: consultá antes de avanzar."),
    "pt-br": ("Profissionais mais próximos",
              "Distância aproximada em linha reta entre os pontos de referência de "
              "{city} e do município onde a empresa informa sua sede; não é a "
              "distância até um endereço. Ter sede por perto não confirma "
              "atendimento nesta cidade: confirme antes de avançar."),
}
# Matches the original department-based block and the one this codemod emits,
# so the list is regenerated whenever the data behind it changes. Matching only
# the original meant a coordinate or seat correction never reached the pages.
OLD_HEAD = re.compile(
    r"<h3>(?:Profesionales en otras ciudades del departamento|"
    r"Profissionais em outras cidades do departamento|"
    r"Profesionales más cercanos|Profissionais mais próximos)</h3>"
    r'<p class="hint">[^<]*</p><div class="stack">(.*?)</div>(?=<p class="disclosure")',
    re.S,
)
CARD_RE = re.compile(r"<article class=\"company\">.*?</article>", re.S)
ID_RE = re.compile(r'href="/(?:es/(?:inmobiliaria|agente)|pt-br/(?:imobiliaria|corretor))/(\d+)-')
META_RE = re.compile(r'<p class="meta">([^<]*)</p>')

_F = None
_CARDS: dict[str, dict[str, str]] = {}


def _facts():
    global _F
    if _F is None:
        _F = FA.Facts()
    return _F


def _cards(lang: str) -> dict:
    """professional id -> its rendered card, harvested once from the corpus."""
    if lang in _CARDS:
        return _CARDS[lang]
    idx: dict[str, str] = {}
    for p in C.all_pages():
        if C.page_lang(p) != lang:
            continue
        src = C.read(p)
        if 'class="company"' not in src:
            continue
        for card in CARD_RE.findall(src):
            m = ID_RE.search(card)
            if m and m.group(1) not in idx:
                idx[m.group(1)] = card
    _CARDS[lang] = idx
    return idx


def _km(d: float) -> str:
    if d >= 100:
        return f"{d:.0f}".replace(".", ",")
    return f"{d:.1f}".replace(".", ",")


def _city_key(url: str, F):
    """Resolve any page URL that shows a nearby block to a municipality."""
    m = re.match(r"^/(?:es/venta|pt-br/comprar)/(.+?)/?$", url)
    if m:
        return F.city_key_from_url(url)
    m = re.match(r"^/(?:es/zonas|pt-br/regioes)/([a-z0-9-]+)(?:/([a-z0-9-]+))?", url)
    if m:
        a, b = m.group(1), m.group(2)
        a = {"assuncao": "asuncion"}.get(a, a)
        if b and f"{a}/{b}" in F.cities:
            return f"{a}/{b}"
        if a in F.cities:
            return a
    m = re.match(r"^/(?:es/inmobiliarias|pt-br/imobiliarias)/([a-z0-9-]+)(?:/([a-z0-9-]+))?/$", url)
    if m:
        a, b = m.group(1), m.group(2)
        a = {"assuncao": "asuncion"}.get(a, a)
        for cand in (f"{a}/{b}" if b else None, a):
            if cand and cand in F.cities:
                return cand
        for key in F.cities:
            if key.endswith("/" + a):
                return key
    return None


def apply(path, src, ctx):
    m = OLD_HEAD.search(src)
    if not m:
        return src
    F = _facts()
    lang = C.page_lang(path)
    key = _city_key(C.rel_url(path), F)
    if not lang or not key:
        return src
    near = F.nearest_professionals(key, LIMIT)
    if not near:
        return src

    cards = _cards(lang)
    local = set(F.local_professionals(key))
    out = []
    for pid, seat, dist in near:
        card = cards.get(pid)
        if not card or pid in local:
            continue
        seat_name = F.name_by_key.get(seat, seat)
        dept = F.cities[seat]["department_slug"].replace("-", " ").title()

        def meta(mm, _s=seat_name, _d=dist):
            kept = mm.group(1)
            place = kept.split("·")[0].strip()
            if not place:
                place = _s
            return f'<p class="meta">{_html.escape(place, quote=False)} · ~{_km(_d)} km</p>'

        out.append(META_RE.sub(meta, card, count=1))
    if not out:
        return src

    title, hint = HEAD[lang]
    city_name = F.name_by_key.get(key, key)
    block = (f"<h3>{_html.escape(title, quote=False)}</h3>"
             f'<p class="hint">{_html.escape(hint.format(city=city_name), quote=False)}</p>'
             f'<div class="stack">{"".join(out)}</div>')
    return src[: m.start()] + block + src[m.end():]
