# -*- coding: utf-8 -*-
"""Show why a professional is listed, using only evidence the data contains.

Proximity is not expertise. The directory records where a firm declares its
seat and, for 21 brands, that the same brand has seats in several
municipalities. It records nothing at all about specialisation by property
type, so the pages state that plainly instead of letting the reader infer that
a firm shown on a "terrenos" page sells land.

Three labels, each backed by a field in data/professionals.csv:

  Sede aquí            the declared seat is this municipality
  N sedes · sitio      the company's own website lists N locations, and every
                       record for it was recovered from that domain
  (no label)           neither applies; the distance already says where it is

The second label deliberately describes the evidence rather than asserting a
corporate relationship. Sharing a name across municipalities proves nothing,
and a franchise's offices are independent businesses, so franchise brands and
groups known only from directory listings carry no label at all.
"""
import html as _html
import os
import re
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C
import facts as FA

ORDER = 140
TITLE = "Label seat and documented network, and state that specialisation is unrecorded"
SELECT = None

CARD_RE = re.compile(r'<article class="company">.*?</article>', re.S)
ID_RE = re.compile(r'href="/(?:es/(?:inmobiliaria|agente)|pt-br/(?:imobiliaria|corretor))/(\d+)-')
BADGE_RE = re.compile(r'(<span class="badge">[^<]*</span>)((?:<span class="badge [^"]*">[^<]*</span>)*)')

T = {
    "es": {"seat": "Sede aquí", "net": "{n} sedes · sitio oficial",
           "lead_local": "Profesionales con sede declarada en esta ciudad. "
                         "El directorio no registra especialización por tipo de inmueble; "
                         "«sedes · sitio oficial» indica cuántas ubicaciones publica la "
                         "propia empresa en su web."},
    "pt-br": {"seat": "Sede aqui", "net": "{n} sedes · site oficial",
              "lead_local": "Profissionais com sede informada nesta cidade. "
                            "O diretório não registra especialização por tipo de imóvel; "
                            "«sedes · site oficial» indica quantos endereços a própria "
                            "empresa publica no site dela."},
}
OLD_LEAD = re.compile(
    r'<p class="section-lead">(?:Profesionales con sede declarada en esta ciudad|'
    r'Profissionais com sede informada nesta cidade)[^<]*</p>')

_F = None


def _facts():
    global _F
    if _F is None:
        _F = FA.Facts()
    return _F


def _city_key(url, F):
    if re.match(r"^/(?:es/venta|pt-br/comprar)/", url):
        return F.city_key_from_url(url)
    m = re.match(r"^/(?:es/zonas|pt-br/regioes)/([a-z0-9-]+)(?:/([a-z0-9-]+))?", url)
    if m:
        a, b = {"assuncao": "asuncion"}.get(m.group(1), m.group(1)), m.group(2)
        if b and f"{a}/{b}" in F.cities:
            return f"{a}/{b}"
        if a in F.cities:
            return a
    m = re.match(r"^/(?:es/inmobiliarias|pt-br/imobiliarias)/([a-z0-9-]+)(?:/([a-z0-9-]+))?/$", url)
    if m:
        a, b = {"assuncao": "asuncion"}.get(m.group(1), m.group(1)), m.group(2)
        for cand in ((f"{a}/{b}" if b else None), a):
            if cand and cand in F.cities:
                return cand
    return None


def apply(path, src, ctx):
    lang = C.page_lang(path)
    if lang not in T:
        return src
    F = _facts()
    t = T[lang]
    key = _city_key(C.rel_url(path), F)
    local = set(F.local_professionals(key)) if key else set()

    def card(m):
        block = m.group(0)
        pid_m = ID_RE.search(block)
        if not pid_m:
            return block
        pid = pid_m.group(1)
        chips = []
        if pid in local:
            chips.append(f'<span class="badge seat">{_html.escape(t["seat"], quote=False)}</span>')
        net = F.network_of.get(pid)
        if net:
            label = t["net"].format(n=len(net["ids"]))
            chips.append(f'<span class="badge net">{_html.escape(label, quote=False)}</span>')
        # rebuild deterministically: drop previous chips, then add current ones
        return BADGE_RE.sub(lambda b: b.group(1) + "".join(chips), block, count=1)

    src = CARD_RE.sub(card, src)
    src = OLD_LEAD.sub(
        f'<p class="section-lead">{_html.escape(t["lead_local"], quote=False)}</p>', src)
    return src
