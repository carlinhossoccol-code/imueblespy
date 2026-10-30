# -*- coding: utf-8 -*-
"""Link the advertising policy from the footer of every page.

Section 9 lists an advertising policy among the pages the site maintains. It
did not exist; now that it does, it belongs in the legal column beside the
privacy policy and terms, which is where a reader looks for it, and which also
keeps it from being an orphan.
"""
ORDER = 110
TITLE = "Link the advertising policy from the site footer"
SELECT = None

LINKS = {
    "es": ('<a href="/es/terminos/">Términos de uso</a>',
           '<a href="/es/politica-de-publicidad/">Política de publicidad</a>'),
    "pt-br": ('<a href="/pt-br/termos/">Termos de uso</a>',
              '<a href="/pt-br/politica-de-publicidade/">Política de publicidade</a>'),
}


def apply(path, src, ctx):
    p = path.replace("\\", "/")
    lang = "es" if "/site/es/" in p else "pt-br" if "/site/pt-br/" in p else None
    if not lang:
        return src
    anchor, link = LINKS[lang]
    if link in src or anchor not in src:
        return src
    return src.replace(anchor, anchor + link, 1)
