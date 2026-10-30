# -*- coding: utf-8 -*-
"""Remove empty elements, and give the buying guides somewhere to go next.

Two things reading the guides surfaced. 406 pages render an empty paragraph,
which is markup noise with no content. And the guides, which are where a
buyer arrives before they know what to ask, ended on a list of external
sources with a single internal link: having just learned what to verify, the
reader had no route to anyone who could help.
"""
import html as _html
import os
import re
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C
import facts as FA

ORDER = 180
TITLE = "Drop empty elements; link the guides on to the directory"
SELECT = None

# Only bare <p></p>. An empty element that carries attributes is usually a
# container something else fills in: an earlier version of this rule also
# matched <div class="suggestions" data-suggestions hidden></div> and
# deleted the box the search script writes its results into.
EMPTY = re.compile(r"<p>\s*</p>")
MARK = 'class="section guide-next"'

GUIDE_URLS = {
    "es": ("/es/guias/", "/es/inmobiliarias/", "/es/zonas/", "/es/venta/"),
    "pt-br": ("/pt-br/guias/", "/pt-br/imobiliarias/", "/pt-br/regioes/", "/pt-br/comprar/"),
}
T = {
    "es": {
        "h2": "Seguir desde acá",
        "lead": "Con esto revisado, el paso siguiente es hablar con un profesional de la zona que te interesa.",
        "dir": "Directorio de inmobiliarias",
        "zones": "Ciudades y departamentos",
        "buy": "Comprar por tipo de propiedad",
        "cities": "Ciudades más consultadas",
    },
    "pt-br": {
        "h2": "Continuar a partir daqui",
        "lead": "Com isso conferido, o próximo passo é falar com um profissional da região que você procura.",
        "dir": "Diretório de imobiliárias",
        "zones": "Cidades e departamentos",
        "buy": "Comprar por tipo de imóvel",
        "cities": "Cidades mais procuradas",
    },
}
ZONE_SEG = {"es": "/es/zonas/", "pt-br": "/pt-br/regioes/"}
PT_DEPT = {"asuncion": "assuncao"}

_F = None


def _facts():
    global _F
    if _F is None:
        _F = FA.Facts()
    return _F


def _is_guide_leaf(url):
    return bool(re.match(r"^/(?:es|pt-br)/guias/[a-z0-9-]+/$", url))


def _city_url(key, lang):
    dept, _, rest = key.partition("/")
    if lang == "pt-br":
        dept = PT_DEPT.get(dept, dept)
    return ZONE_SEG[lang] + dept + "/" + (rest + "/" if rest else "")


def apply(path, src, ctx):
    src = EMPTY.sub("", src)

    url = C.rel_url(path)
    lang = C.page_lang(path)
    if lang not in T or not _is_guide_leaf(url) or MARK in src:
        return src

    F = _facts()
    t = T[lang]
    _, dir_u, zones_u, buy_u = GUIDE_URLS[lang]
    top = sorted(F.cities, key=lambda k: -(F.population(k) or 0))[:6]
    city_links = "".join(
        f'<a href="{_city_url(k, lang)}">{_html.escape(F.name_by_key.get(k, k), quote=False)}</a>'
        for k in top)

    block = (
        f'<section {MARK}><div class="section-header"><div>'
        f'<h2>{_html.escape(t["h2"], quote=False)}</h2>'
        f'<p class="section-lead">{_html.escape(t["lead"], quote=False)}</p></div></div>'
        f'<div class="gridlist">'
        f'<a href="{dir_u}">{_html.escape(t["dir"], quote=False)}</a>'
        f'<a href="{zones_u}">{_html.escape(t["zones"], quote=False)}</a>'
        f'<a href="{buy_u}">{_html.escape(t["buy"], quote=False)}</a></div>'
        f'<h3>{_html.escape(t["cities"], quote=False)}</h3>'
        f'<div class="gridlist">{city_links}</div></section>')

    i = src.find("</main>")
    return src[:i] + block + src[i:] if i > 0 else src
