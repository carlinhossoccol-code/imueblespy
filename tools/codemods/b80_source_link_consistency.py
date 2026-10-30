# -*- coding: utf-8 -*-
"""Open the INE source link the way every other source link opens.

Each page cites the national statistics office for its population figure. That
link alone navigated away in the same tab, losing the reader's place, while
every other outbound source link on the page opens a new tab with the usual
rel attributes. This makes it consistent.
"""
import re

ORDER = 170
TITLE = "Open the statistics-office link in a new tab, like other source links"
SELECT = None

INE = re.compile(r'<a href="(https://portalgeoestad\.ine\.gov\.py/[^"]*)"(?![^>]*rel=)([^>]*)>')


def apply(path, src, ctx):
    return INE.sub(
        lambda m: f'<a href="{m.group(1)}" rel="noopener noreferrer" '
                  f'target="_blank"{m.group(2)}>', src)
