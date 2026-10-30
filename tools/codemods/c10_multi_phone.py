# -*- coding: utf-8 -*-
"""Make a recorded second phone number usable instead of dropping it.

Seven profiles record two numbers in one field, separated by a pipe or slash.
The page printed them exactly as stored - "+595 21 3284900 | +595 983999998",
which reads as a data artefact - and offered no dial action at all, because a
tel: link containing both numbers would not dial. A buyer therefore saw a phone
number they could not tap on the one profile that had one.

Both numbers are recorded, so both are shown, separated readably, and the first
becomes a dial action. Nothing is invented: the second number is published
exactly as it was recorded, just legibly.
"""
import csv
import html as _html
import os
import re
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C

# Runs last: a90 rebuilds the nearby-professional cards from markup it reads
# off disk, so anything added to a card before it runs is discarded.
ORDER = 200
TITLE = "Show both recorded phone numbers legibly and make the first dialable"
SELECT = None

# Includes the separator this codemod itself writes, so a re-extracted
# dataset is still recognised as holding two numbers.
SPLIT = re.compile(r"\s*[|/;·]\s*")
CALL = {"es": "Llamar", "pt-br": "Ligar"}

_MULTI = None


def _multi():
    """profile id -> (display text, first number as digits)"""
    global _MULTI
    if _MULTI is None:
        _MULTI = {}
        path = os.path.join(C.DATA, "professionals.csv")
        with open(path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                raw = (r["phone"] or "").strip()
                parts = [p.strip() for p in SPLIT.split(raw) if p.strip()]
                if len(parts) < 2:
                    continue
                first = "+" + re.sub(r"\D", "", parts[0])
                _MULTI[r["id"]] = (" · ".join(parts), first, r["slug"])
    return _MULTI


def apply(path, src, ctx):
    lang = C.page_lang(path)
    if lang not in CALL:
        return src
    multi = _multi()
    if not multi:
        return src

    # 1. legible separator wherever the stored string is printed
    for pid, (display, _first, _slug) in multi.items():
        raw = display.replace(" · ", " | ")
        alt = display.replace(" · ", " / ")
        src = src.replace(raw, display).replace(alt, display)

    # 2. a dial action where the profile has none
    def add_call(block, pid):
        if "tel:" in block or 'class="actions"' not in block:
            return block
        _display, first, _slug = multi[pid]
        btn = f'<a class="btn" href="tel:{first}">{_html.escape(CALL[lang], quote=False)}</a>'
        # Appended, not prepended: every card puts the ghost "view profile"
        # link first, and inserting ahead of it broke that order.
        i = block.find('<div class="actions">')
        j = block.find("</div>", i)
        if j <= i:
            return block
        actions = block[i:j]
        # Calling is the stronger action, so an existing website button steps
        # down to the ghost style. Two buttons of equal weight in one colour
        # read as a single control.
        actions = re.sub(r'<a class="btn"(\s+href="https?://)', r'<a class="btn ghost"\1', actions)
        return block[:i] + actions + btn + block[j:]

    for pid, (_d, _f, slug) in multi.items():
        # the professional's own page
        if C.rel_url(path).rstrip("/").endswith("/" + slug):
            src = add_call(src, pid)
            continue
        # and any card for them elsewhere
        card_re = re.compile(
            r'<article class="company">(?:(?!</article>).)*?' + re.escape(slug)
            + r'(?:(?!</article>).)*?</article>', re.S)
        src = card_re.sub(lambda m: add_call(m.group(0), pid), src)
    return src
