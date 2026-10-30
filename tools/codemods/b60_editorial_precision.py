# -*- coding: utf-8 -*-
"""Remove copy that is empty, duplicated or contradicted by the page's own data.

Reading a municipality page with no seated firm end to end surfaced three
problems that no similarity measure would catch:

1. The section lead announced "professionals with a declared seat in this
   city" above a box saying there are none.
2. The caveat that a nearby seat does not confirm coverage appeared twice in
   consecutive blocks.
3. Facts whose value is zero were printed anyway ("Zonas registradas en la
   base 0"), and a generic sentence told the reader to weigh neighbourhoods on
   pages where no neighbourhood is registered.
"""
import os
import re
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C
import facts as FA

ORDER = 150
TITLE = "Drop empty, duplicated and self-contradicted copy"
SELECT = None

_F = None


def _facts():
    global _F
    if _F is None:
        _F = FA.Facts()
    return _F


NO_LOCAL = re.compile(r'<div class="callout"><strong>(?:Sin empresa local identificada[^<]*|'
                      r'Nenhuma empresa local identificada[^<]*)</strong>')
LEAD = re.compile(r'<p class="section-lead">(?:Profesionales con sede declarada en esta ciudad\.|'
                  r'Profissionais com sede informada nesta cidade\.)[^<]*</p>')
LEAD_REPLACE = {
    "es": '<p class="section-lead">El directorio no registra especialización por tipo de inmueble.</p>',
    "pt-br": '<p class="section-lead">O diretório não registra especialização por tipo de imóvel.</p>',
}
# the second half of the callout repeats the hint under the nearby list
DUP_CAVEAT = [
    (" Su atención en esta localidad no está confirmada.", ""),
    (" O atendimento nesta cidade não está confirmado.", ""),
]
ZERO_FACT = re.compile(r'<div class="ep-fact"><dt>(?:Zonas registradas en la base|'
                       r'Regiões cadastradas na base)</dt><dd>0</dd></div>')
GENERIC_HOODS = [
    "<p>La evaluación de la zona debe considerar los barrios, el estado de los accesos "
    "y las condiciones de cada inmueble.</p>",
    "<p>A avaliação local deve considerar bairros, acessos e as condições de cada imóvel.</p>",
]


def apply(path, src, ctx):
    lang = C.page_lang(path)
    if lang not in LEAD_REPLACE:
        return src
    F = _facts()

    # 1. a lead that promises local firms above a box saying there are none
    if NO_LOCAL.search(src):
        src = LEAD.sub(LEAD_REPLACE[lang], src, count=1)
        for a, b in DUP_CAVEAT:
            src = src.replace(a, b)

    # 2. facts worth nothing when the value is zero
    src = ZERO_FACT.sub("", src)

    # 3. advice to weigh neighbourhoods where none are registered
    key = None
    for pat in (r"^/(?:es/venta|pt-br/comprar)/",):
        if re.match(pat, C.rel_url(path)):
            key = F.city_key_from_url(C.rel_url(path))
    if key and not F.neighbourhoods(key):
        for frag in GENERIC_HOODS:
            src = src.replace(frag, "")
    return src
