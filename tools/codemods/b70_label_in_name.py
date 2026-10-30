# -*- coding: utf-8 -*-
"""Make accessible names contain their visible text (WCAG 2.5.3 Label in Name).

Lighthouse flagged two cases. The language switch reads "ES" on screen but
announced "Ver versão em espanhol", so a speech-input user asking for "ES"
could not activate it. The advertising card carried a summary aria-label that
replaced all of its visible text with different words.
"""
import re

ORDER = 160
TITLE = "Accessible names include the visible label"
SELECT = None

LANG_RE = re.compile(r'<a aria-label="([^"]+)"([^>]*class="lang switcher"[^>]*)>([^<]+)</a>')
BANNER_RE = re.compile(r'(<a )aria-label="[^"]*"(\s*class="mnpb-card")')
CTA_RE = re.compile(r'(<span class="mnpb-cta">)(?!<span class="sr-only")')
NEWTAB = {"es": "Abre en una pestaña nueva.", "pt-br": "Abre em nova aba."}


def apply(path, src, ctx):
    def lang(m):
        label, attrs, text = m.group(1), m.group(2), m.group(3)
        if label.startswith(text):
            return m.group(0)
        return f'<a aria-label="{text} — {label}"{attrs}>{text}</a>'

    src = LANG_RE.sub(lang, src)

    if 'class="mnpb-card"' in src:
        # the surrounding <aside aria-label="Publicidade..."> already names the
        # region; the link takes its name from its own visible content
        src = BANNER_RE.sub(r"\1\2", src)
        src = CTA_RE.sub(
            lambda m: m.group(1) + f'<span class="sr-only">{NEWTAB["pt-br"]} </span>', src, count=1)
    return src
