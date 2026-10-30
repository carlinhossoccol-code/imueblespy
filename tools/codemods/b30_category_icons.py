# -*- coding: utf-8 -*-
"""Give the property categories an icon and a description of their own.

The four category tiles were visually identical and all carried the same
sentence, "Información de compra y directorios por ciudad", so the only thing
distinguishing them was the word in the heading. Each now has a line drawing
and a one-line summary naming what actually differs about buying that kind of
property - the same three concerns the category page then expands on.

Icons are inline SVG: no extra request, no dependency on an icon font, and
they inherit the surrounding colour. They are decorative, so they are hidden
from assistive technology and the link text carries the meaning.
"""
import html as _html
import re

ORDER = 120
TITLE = "Add distinct icons and descriptions to the property categories"
SELECT = None

ICONS = {
    # plot boundary with a corner marker
    "terrenos": '<rect x="3.2" y="7.2" width="17.6" height="12.6" rx="1.4" stroke-dasharray="3.4 2.2"/>'
                '<circle cx="3.2" cy="7.2" r="1.7" fill="currentColor" stroke="none"/>'
                '<path d="M8 13.5h8"/>',
    # pitched roof, walls, doorway
    "casas": '<path d="M3 11.2 12 4l9 7.2"/><path d="M5.4 10v9.6h13.2V10"/>'
             '<path d="M9.9 19.6v-5.2h4.2v5.2"/>',
    # tower block with windows
    "departamentos": '<rect x="5.2" y="3.2" width="13.6" height="17.6" rx="1.3"/>'
                     '<path d="M9 7.4h2M13 7.4h2M9 11.4h2M13 11.4h2M9 15.4h2M13 15.4h2"/>'
                     '<path d="M10.6 20.8v-2.6h2.8v2.6"/>',
    # shopfront with awning
    "comerciales": '<path d="M4.2 9.2h15.6l-1.1-4.4H5.3z"/><path d="M5.4 9.2v11.4h13.2V9.2"/>'
                   '<path d="M9.4 20.6v-6.1h5.2v6.1"/>',
}
# URL slug -> icon key, per language
SLUG = {
    "es": {"terrenos": "terrenos", "casas": "casas",
           "departamentos": "departamentos", "comerciales": "comerciales"},
    "pt-br": {"terrenos": "terrenos", "casas": "casas",
              "apartamentos": "departamentos", "comerciais": "comerciales"},
}
BLURB = {
    "es": {
        "terrenos": "Lotes y terrenos: título, superficie, acceso y servicios.",
        "casas": "Casas: estado de la construcción, documentación y barrio.",
        "departamentos": "Departamentos: expensas, reglamento y propiedad horizontal.",
        "comerciales": "Inmuebles comerciales: uso de suelo, habilitación y acceso.",
    },
    "pt-br": {
        "terrenos": "Lotes e terrenos: título, área, acesso e serviços.",
        "casas": "Casas: estado da construção, documentação e bairro.",
        "departamentos": "Apartamentos: condomínio, convenção e área privativa.",
        "comerciales": "Imóveis comerciais: uso do solo, alvará e acesso.",
    },
}

CAT_HREF = re.compile(r'^/(es)/venta/([a-z]+)/$|^/(pt-br)/comprar/([a-z]+)/$')
TILE_RE = re.compile(r'<a class="tile" href="(/(?:es/venta|pt-br/comprar)/[a-z]+/)">(.*?)</a>', re.S)
GRID_CAT_RE = re.compile(
    r'<a href="(/(?:es/venta|pt-br/comprar)/[a-z0-9-]+/(?:[a-z0-9-]+/)?([a-z]+)/)">([^<]*)</a>')


def _svg(key):
    return ('<svg class="caticon" viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" '
            'focusable="false" fill="none" stroke="currentColor" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[key]}</svg>')


def _key(href):
    m = CAT_HREF.match(href)
    if not m:
        return None, None
    lang = m.group(1) or m.group(3)
    slug = m.group(2) or m.group(4)
    return lang, SLUG.get(lang, {}).get(slug)


def apply(path, src, ctx):
    # 1. homepage tiles: icon plus a description specific to the category
    def tile(m):
        href, inner = m.group(1), m.group(2)
        lang, key = _key(href)
        if not key or "caticon" in inner:
            return m.group(0)
        inner = re.sub(r"<p>.*?</p>",
                       f"<p>{_html.escape(BLURB[lang][key], quote=False)}</p>",
                       inner, count=1, flags=re.S)
        inner = inner.replace('<div class="tilebody">',
                              f'<div class="tilebody">{_svg(key)}', 1)
        return f'<a class="tile cattile" href="{href}">{inner}</a>'

    src = TILE_RE.sub(tile, src)

    # 2. "explore other categories" lists: same icon beside the label
    def grid(m):
        href, slug, label = m.group(1), m.group(2), m.group(3)
        lang = "es" if href.startswith("/es/") else "pt-br"
        key = SLUG.get(lang, {}).get(slug)
        if not key:
            return m.group(0)
        return f'<a class="catlink" href="{href}">{_svg(key)}<span>{label}</span></a>'

    return GRID_CAT_RE.sub(grid, src)
