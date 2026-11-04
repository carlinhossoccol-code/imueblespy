# -*- coding: utf-8 -*-
"""Show approved real images of a profile, and only those.

Input is ``data/profile_images.json``, written by ``tools/images/pipeline.py``.
An entry exists only for images whose identity was confirmed and whose right of
use is documented in ``data/image_rights.csv``; this codemod trusts nothing
else and invents nothing.

For a profile with approved images:

* the generic identifier in every directory card (``img.identity``, 62x62) and
  on the profile page (``img.profile-logo``, 96x96) becomes the primary image,
  with the same intrinsic size - so the layout cannot shift - and a 1x/2x
  ``srcset``;
* the profile page gains a light gallery of the other approved images, lazily
  loaded (none of them is the LCP image, which stays the hero).

For every other profile the generic identifier stays exactly as it is. The
replacement keeps the placeholder's src and alt in data attributes, so when an
approval is withdrawn the next run restores the original tag byte for byte.
Both languages reuse the same files.
"""
import html as _html
import json
import os
import re
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C

# After c10 (ORDER 200): a90 rebuilds nearby-profile cards from markup it reads
# off disk, so the card image must be set after every card is final.
ORDER = 210
TITLE = "Use approved real profile images in cards and profile galleries"
SELECT = None

SLOTS = {  # class -> (CSS box, placeholder template)
    "identity": (62, '<img alt="{alt}" class="identity" decoding="async" height="62" loading="lazy" src="{src}" width="62"/>'),
    "profile-logo": (96, '<img alt="{alt}" class="profile-logo" height="96" src="{src}" width="96"/>'),
}
PLACEHOLDER_RE = re.compile(
    r'<img alt="(?P<alt>[^"]*)" class="(?P<cls>identity|profile-logo)"[^>]*?'
    r'src="(?P<src>/assets/identities/[^"]+)"[^>]*/>')
REPLACED_RE = re.compile(r'<img [^>]*data-pimg="(?P<pid>\d+)"[^>]*/>')
GALLERY_RE = re.compile(r'<section class="pimg-gallery" data-pimg-gallery="\d+">.*?</section>', re.S)
PROFILE_SEG = {lang: (C.AGENCY_SEGMENT[lang], C.AGENT_SEGMENT[lang]) for lang in C.LANGS}
GALLERY_TITLE = {"es": "Imágenes de la empresa", "pt-br": "Imagens da empresa"}
GALLERY_NOTE = {"es": "Imágenes publicadas con autorización documentada.",
                "pt-br": "Imagens publicadas com autorização documentada."}

_STATE = None


def _attr(s):
    return _html.escape(s, quote=True)


def _state():
    """(manifest profiles, placeholder src -> profile id)."""
    global _STATE
    if _STATE is None:
        path = os.path.join(C.DATA, "profile_images.json")
        try:
            with open(path, encoding="utf-8") as fh:
                profiles = json.load(fh).get("profiles", {})
        except FileNotFoundError:
            profiles = {}
        by_placeholder = {}
        for pid, entry in profiles.items():
            if not entry.get("images"):
                continue
            for lang in C.LANGS:
                for seg in PROFILE_SEG[lang]:
                    page = os.path.join(C.SITE, lang, seg, entry["slug"], "index.html")
                    if os.path.exists(page):
                        m = re.search(r'class="profile-logo"[^>]*src="(/assets/identities/[^"]+)"', C.read(page))
                        if m:
                            by_placeholder[m.group(1)] = pid
                        else:  # already replaced on a previous run
                            m = re.search(r'data-pimg="%s"[^>]*data-placeholder="([^"]+)"' % pid, C.read(page))
                            if m:
                                by_placeholder[m.group(1)] = pid
        _STATE = (profiles, by_placeholder)
    return _STATE


def _primary_tag(cls, pid, img, lang, placeholder_src, placeholder_alt):
    box, _ = SLOTS[cls]
    v1, v2 = img["variants"]["p124"], img["variants"]["p192"]
    small = v1 if box <= 62 else v2
    alt = img["alt_es"] if lang == "es" else img["alt_pt"]
    lazy = ' loading="lazy"' if cls == "identity" else ""
    kind = " pimg-logo" if img["type"] == "logo" else " pimg-photo"
    return (f'<img alt="{_attr(alt)}" class="{cls}{kind}" data-pimg="{pid}" '
            f'data-placeholder="{placeholder_src}" data-placeholder-alt="{placeholder_alt}" '
            f'decoding="async" height="{box}"{lazy} sizes="{box}px" src="{small["src"]}" '
            f'srcset="{v1["src"]} {v1["w"]}w, {v2["src"]} {v2["w"]}w" width="{box}"/>')


def _gallery(pid, images, lang):
    figs = []
    for img in images:
        a, b = img["variants"]["g480"], img["variants"]["g960"]
        alt = img["alt_es"] if lang == "es" else img["alt_pt"]
        figs.append(f'<figure><img alt="{_attr(alt)}" decoding="async" height="{a["h"]}" loading="lazy" '
                    f'sizes="(max-width: 760px) 100vw, 320px" src="{a["src"]}" '
                    f'srcset="{a["src"]} {a["w"]}w, {b["src"]} {b["w"]}w" width="{a["w"]}"/></figure>')
    return (f'<section class="pimg-gallery" data-pimg-gallery="{pid}"><h2 class="profile-heading">'
            f'{GALLERY_TITLE[lang]}</h2><div class="pimg-grid">{"".join(figs)}</div>'
            f'<p class="pimg-note">{GALLERY_NOTE[lang]}</p></section>')


def apply(path, src, ctx):
    lang = C.page_lang(path)
    if lang not in C.LANGS:
        return src
    profiles, by_placeholder = _state()
    if not by_placeholder and "data-pimg" not in src:
        return src  # nothing approved and nothing to restore: page untouched

    # 1. Restore every replaced tag; step 2 re-applies what is still approved.
    def restore(m):
        tag = m.group(0)
        cls = "profile-logo" if 'class="profile-logo' in tag else "identity"
        ph = re.search(r'data-placeholder="([^"]*)"', tag).group(1)
        alt = re.search(r'data-placeholder-alt="([^"]*)"', tag).group(1)
        return SLOTS[cls][1].format(alt=alt, src=ph)

    out = REPLACED_RE.sub(restore, src)
    out = GALLERY_RE.sub("", out)

    # 2. Replace placeholders of approved profiles.
    gallery_for = None

    def replace(m):
        nonlocal gallery_for
        pid = by_placeholder.get(m.group("src"))
        entry = profiles.get(pid) if pid else None
        if not entry or not entry.get("images"):
            return m.group(0)
        if m.group("cls") == "profile-logo":
            gallery_for = pid
        return _primary_tag(m.group("cls"), pid, entry["images"][0], lang,
                            m.group("src"), m.group("alt"))

    out = PLACEHOLDER_RE.sub(replace, out)

    # 3. Gallery of the remaining images, after the profile's data table.
    if gallery_for:
        rest = profiles[gallery_for]["images"][1:]
        if rest:
            i = out.find('data-pimg="%s"' % gallery_for)
            j = out.find("</table>", i)
            if j != -1:
                j += len("</table>")
                out = out[:j] + _gallery(gallery_for, rest, lang) + out[j:]
    return out
