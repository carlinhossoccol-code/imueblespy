"""Editorial hygiene: keep internal implementation detail out of public copy
and keep titles within the length search engines actually display.

"Ninguno en el CSV" exposed the shape of the source file rather than telling
the reader anything; it becomes a plain statement that no channel is published.
Titles longer than ~95 characters get a shorter but still descriptive suffix.
"""
import html as _html
import re

ORDER = 40
TITLE = "Remove internal data-format wording and shorten over-long titles"
SELECT = None

CSV_WORDING = [
    ("<dd>Ninguno en el CSV</dd>", "<dd>Ninguno publicado</dd>"),
    ("<dd>Nenhum no CSV</dd>", "<dd>Nenhum publicado</dd>"),
    ("Ninguno en el CSV", "Ninguno publicado"),
    ("Nenhum no CSV", "Nenhum publicado"),
]

# Progressively shorter replacements for a title's descriptive suffix.
SUFFIX_LADDER = [
    (": perfil inmobiliaria y contactos ", [": perfil y contactos ", " "]),
    (": perfil de imobiliária e contatos ", [": perfil e contatos ", " "]),
    (": perfil agente inmobiliario y contactos ", [": perfil y contactos ", " "]),
    (": perfil de corretor e contatos ", [": perfil e contatos ", " "]),
    (": guía e inmobiliarias ", [": inmobiliarias ", " "]),
    (": guia e imobiliárias ", [": imobiliárias ", " "]),
]

MAX_TITLE = 95


def _shorten(title: str) -> str:
    if len(_html.unescape(title)) <= MAX_TITLE:
        return title
    for long_sfx, shorter in SUFFIX_LADDER:
        if long_sfx in title:
            for alt in shorter:
                cand = title.replace(long_sfx, alt)
                if len(_html.unescape(cand)) <= MAX_TITLE:
                    return cand
    return title


def apply(path, src, ctx):
    for a, b in CSV_WORDING:
        src = src.replace(a, b)

    m = re.search(r"<title>(.*?)</title>", src, re.S)
    if not m:
        return src
    new = _shorten(m.group(1))
    if new != m.group(1):
        old_t, new_t = m.group(1), new
        src = src.replace(f"<title>{old_t}</title>", f"<title>{new_t}</title>")
        # og:title and twitter title mirror the document title
        src = src.replace(f'<meta content="{old_t}" property="og:title"/>',
                          f'<meta content="{new_t}" property="og:title"/>')
        src = src.replace(f'<meta content="{old_t}" property="og:image:alt"/>',
                          f'<meta content="{new_t}" property="og:image:alt"/>')
    return src
