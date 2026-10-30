"""Move the Morar no Paraguai banner below the first useful content.

The banner sat immediately after the hero on all 2,011 Brazilian pages, so it
preceded the first professional result on directory pages and pushed the
company's own identification and contact details below it on profile pages. On
a phone it owned most of the first screen.

It keeps its markup, destination, "Publicidade" label, rel="sponsored" and
accessible name; only its position in the document changes:

  * homepage            -> after the cities and property-type sections
  * pages with a data    -> immediately before that area, i.e. after the
    and methodology area    directory listing, profile panel and contacts
  * everything else     -> at the end of the main content
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import corpus as C

ORDER = 50
TITLE = "Place the PT-BR advertising banner after the first useful section"
SELECT = r"^/pt-br/"

BLOCK_RE = re.compile(
    r'<div class="shell ad-wrap">\s*<aside\b[^>]*class="mnpb"[^>]*>.*?</aside>\s*</div>', re.S
)
EP_AREA_RE = re.compile(r'<div class="shell ep-area"')
# The homepage's property-type section, whose close tag is the insertion point.
HOME_ANCHOR_RE = re.compile(
    r"<h2[^>]*>Qual tipo de imóvel você procura\?</h2>.*?</section>", re.S
)


def apply(path, src, ctx):
    m = BLOCK_RE.search(src)
    if not m:
        return src
    block = m.group(0)
    body = src[: m.start()] + src[m.end():]

    url = C.rel_url(path)
    if url == "/pt-br/":
        a = HOME_ANCHOR_RE.search(body)
        if a:
            return body[: a.end()] + block + body[a.end():]
    a = EP_AREA_RE.search(body)
    if a:
        return body[: a.start()] + block + body[a.start():]
    i = body.find("</main>")
    if i > 0:
        return body[:i] + block + body[i:]
    return src
