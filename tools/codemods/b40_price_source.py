# -*- coding: utf-8 -*-
"""Name the source of a price reference, rather than only linking to it.

Every published reference comes from one external survey on the same date. A
reader judging whether to trust the figure should see whose number it is
without having to hover the link, and should see that it is a single external
observation rather than a market average this project computed.
"""
import os
import re
import sys
from urllib.parse import urlparse

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C

ORDER = 130
TITLE = "State the price reference's source and that it is a single observation"
SELECT = r"^/(es/venta|pt-br/comprar)/"

BLOCK = re.compile(r'(<section[^>]*class="v10-price-evidence[^"]*"[^>]*>)(.*?)(</section>)', re.S)
SRC_LINK = re.compile(r'<p class="v10-source">\s*<a href="(https?://[^"]+)"')
NOTE = re.compile(r"(<p>Valor de referencia[^<]*|<p>Valor de referência[^<]*)")

ADD = {
    "es": " Es una observación puntual de {host}, no un promedio de mercado calculado por InmueblesPY.",
    "pt-br": " É uma observação pontual de {host}, não uma média de mercado calculada pela InmueblesPY.",
}


def apply(path, src, ctx):
    lang = C.page_lang(path)
    if lang not in ADD:
        return src

    def fix(m):
        head, body, tail = m.group(1), m.group(2), m.group(3)
        link = SRC_LINK.search(body)
        if not link:
            return m.group(0)
        host = urlparse(link.group(1)).netloc.replace("www.", "")
        extra = ADD[lang].format(host=host)
        # keep the block regenerable: drop a previously added sentence first
        body = re.sub(r"\s*(?:Es una observación puntual de|É uma observação pontual de)[^<]*", "", body)
        if extra.strip() in body:
            return head + body + tail
        body = NOTE.sub(lambda n: n.group(1).rstrip() + extra, body, count=1)
        return head + body + tail

    return BLOCK.sub(fix, src)
