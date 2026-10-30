"""Give each property-category page its own substantive content.

Within one municipality the four category pages shared about 70% of their main
text: the same directory cards, the same municipal panorama, the same three
generic questions and the same three-row verification table. That is the shape
of a doorway cluster, and it left a buyer no reason to prefer one page.

Three changes, all driven by tools/lib/category_content.py:

1. The generic question list becomes four questions that only make sense for
   this category.
2. The three-row verification table becomes five category-specific rows.
3. A new module sets out what makes up the cost of this particular kind of
   purchase.

One removal: the department table repeated the city page's content verbatim on
all four category pages. It stays on both city-level pages, and the related
cities list below it keeps the internal links, so nothing is orphaned.
"""
import html as _html
import os
import re
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C
import category_content as CC

ORDER = 60
TITLE = "Differentiate each category page with its own checks, questions and costs"
SELECT = r"^/(es/venta|pt-br/comprar)/"

CAT_URL_RE = re.compile(r"^/(es)/venta/(?:[a-z0-9-]+/)+?([a-z]+)/$|^/(pt-br)/comprar/(?:[a-z0-9-]+/)+?([a-z]+)/$")

DEPT_TABLE_RE = re.compile(
    r"<h3>(?:Otras localidades del departamento|Outras localidades do departamento)</h3>"
    r'<div class="ep-table-wrap"><table class="ep-table">.*?</table></div>',
    re.S,
)
QUESTIONS_RE = re.compile(
    r"(<h2>(?:Preguntas para hacerle a un profesional|Perguntas para fazer ao profissional)</h2>)<ul>.*?</ul>",
    re.S,
)
CHECKS_TABLE_RE = re.compile(
    r'(<div class="ep-table-wrap"><table class="ep-table"><thead><tr>'
    r'<th scope="col">(?:Aspecto a verificar|O que verificar)</th>'
    r'<th scope="col">(?:Preguntas concretas para esta compra|Perguntas práticas nesta compra)</th>'
    r"</tr></thead><tbody>).*?(</tbody></table></div>)",
    re.S,
)
COSTS_ID = 'class="ep-module ep-costs"'


def _category(url):
    m = CAT_URL_RE.match(url)
    if not m:
        return None, None
    lang = m.group(1) or m.group(3)
    slug = m.group(2) or m.group(4)
    return lang, slug


def _esc(t):
    return _html.escape(t, quote=False)


def apply(path, src, ctx):
    url = C.rel_url(path)
    lang, slug = _category(url)
    if not lang:
        return src
    data = CC.get(lang, slug)
    if not data:
        return src
    L = CC.LABELS[lang]

    # 1. category-specific questions
    def q_sub(m):
        items = "".join(f"<li>{_esc(q)}</li>" for q in data["questions"])
        return f"{m.group(1)}<ul>{items}</ul>"

    src = QUESTIONS_RE.sub(q_sub, src, count=1)

    # 2. category-specific verification rows
    def t_sub(m):
        rows = "".join(
            f"<tr><td><strong>{_esc(a)}</strong></td><td>{_esc(b)}</td></tr>"
            for a, b in data["checks"]
        )
        return m.group(1) + rows + m.group(2)

    src = CHECKS_TABLE_RE.sub(t_sub, src, count=1)

    # 3. drop the department table duplicated from the city page
    src = DEPT_TABLE_RE.sub("", src, count=1)

    # 4. cost-composition module, inserted before the data-area footnote
    if COSTS_ID not in src:
        rows = "".join(
            f"<tr><td><strong>{_esc(a)}</strong></td><td>{_esc(b)}</td></tr>"
            for a, b in data["costs"]
        )
        module = (
            f'<section {COSTS_ID}><h2>{_esc(L["costs_h2"])}</h2>'
            f'<p>{_esc(data["costs_lead"])}</p>'
            f'<div class="ep-table-wrap"><table class="ep-table"><thead><tr>'
            f'<th scope="col">{_esc(L["concept"])}</th>'
            f'<th scope="col">{_esc(L["what"])}</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="ep-note">{_esc(L["note"])}</p></section>'
        )
        anchor = src.find('<p class="ep-footnote">')
        if anchor > 0:
            src = src[:anchor] + module + src[anchor:]
    return src
