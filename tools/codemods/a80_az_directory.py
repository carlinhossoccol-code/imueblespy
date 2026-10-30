# -*- coding: utf-8 -*-
"""Group the full professional index by initial letter.

Both "all professionals" pages rendered 500 links as one undifferentiated list:
nothing to scan, nothing to link to, and an H1 followed by the footer's H3s with
no H2 in between. The links are regrouped under a heading per initial, with a
jump index above them, which fixes the heading order and makes the page usable.
"""
import html as _html
import re
import unicodedata

ORDER = 80
TITLE = "Group the full professional index under per-letter headings"
SELECT = r"^/(es/todos-los-profesionales|pt-br/todos-os-profissionais)/$"

LIST_RE = re.compile(r'<div class="ep-list">(.*?)</div>', re.S)
LINK_RE = re.compile(r'<a href="([^"]+)">(.*?)</a>', re.S)

LABELS = {
    "es": {"index": "Ir a la letra", "digits": "0–9", "back": "Volver al índice"},
    "pt-br": {"index": "Ir para a letra", "digits": "0–9", "back": "Voltar ao índice"},
}


def _initial(name: str) -> str:
    t = _html.unescape(name).strip()
    if not t:
        return "#"
    ch = unicodedata.normalize("NFD", t[0])[0].upper()
    if ch.isdigit():
        return "0-9"
    return ch if "A" <= ch <= "Z" else "#"


def apply(path, src, ctx):
    if 'class="az-index"' in src:
        return src
    m = LIST_RE.search(src)
    if not m:
        return src
    links = LINK_RE.findall(m.group(1))
    if len(links) < 40:
        return src
    lang = "es" if "/es/" in path.replace("\\", "/") else "pt-br"
    L = LABELS[lang]

    groups: dict[str, list] = {}
    for href, label in links:
        groups.setdefault(_initial(label), []).append((href, label))

    def sort_key(k):
        return (k == "#", k == "0-9", k)

    keys = sorted(groups, key=sort_key)

    def slug(k):
        return "letra-0-9" if k == "0-9" else ("letra-otros" if k == "#" else f"letra-{k.lower()}")

    def title(k):
        return L["digits"] if k == "0-9" else ("#" if k == "#" else k)

    index = "".join(f'<a href="#{slug(k)}">{title(k)}</a>' for k in keys)
    out = [f'<nav aria-label="{L["index"]}" class="az-index">{index}</nav>']
    for k in keys:
        items = "".join(f'<a href="{h}">{t}</a>' for h, t in groups[k])
        out.append(
            f'<section class="az-group" id="{slug(k)}">'
            f'<h2 class="az-letter">{title(k)}</h2>'
            f'<div class="ep-list">{items}</div></section>'
        )
    return src[: m.start()] + "".join(out) + src[m.end():]
