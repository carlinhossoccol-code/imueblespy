# -*- coding: utf-8 -*-
"""Consolidate the repeated disclaimers into one clear statement per page.

A category page carried about ten separate variations of "this does not prove /
we do not confirm / we do not guarantee". Each was defensible on its own, but
together they read as a portal arguing against its own usefulness, and they
filled roughly 100 words of identical text on every one of 1,900 pages.

The limitations are kept once, where a reader is actually about to act on the
listing, and point to the methodology page for detail. The remaining sentences
are rewritten to say the same thing in the affirmative: where a professional is
seated, and what to confirm before closing a deal.

One contradiction is also removed: 162 pages published an observed price
reference while simultaneously stating that no quotation is published. The
price block carries its own caveat, so the conflicting note goes; on the 82
pages that show no price block the note is accurate and stays.
"""
import re

ORDER = 70
TITLE = "Consolidate repeated disclaimers and rewrite them in the affirmative"
SELECT = r"^/(es/venta|pt-br/comprar|es/zonas|pt-br/regioes|es/inmobiliarias|pt-br/imobiliarias)/"

# (old, new) — new = "" removes the sentence outright as a duplicate.
ES = [
    # the single consolidated statement
    ('<p class="disclosure">Este directorio no publica inmuebles individuales ni garantiza que cada empresa atienda una zona o categoría. Verificá los datos antes de decidir.</p>',
     '<p class="disclosure">InmueblesPY reúne información pública de profesionales inmobiliarios y no publica anuncios de propiedades. Antes de cerrar una operación, confirmá los datos de contacto y la documentación del inmueble. <a href="/es/metodologia/">Cómo se elabora este directorio</a></p>'),
    # affirmative rewrites
    ('<p class="section-lead">Directorio según ciudad de sede declarada. Los contactos deben ser confirmados.</p>',
     '<p class="section-lead">Profesionales con sede declarada en esta ciudad según el relevamiento del directorio.</p>'),
    ('<p class="hint">No se presume cobertura comercial de esta localidad.</p>',
     '<p class="hint">Tienen sede en otra localidad del departamento: consultá si atienden esta ciudad.</p>'),
    ('¿Querés contrastar otras opciones por tu cuenta? Abrí una búsqueda pública; los resultados son externos y no están verificados por InmueblesPY.',
     '¿Querés contrastar otras opciones por tu cuenta? Los resultados de esta búsqueda son externos a InmueblesPY.'),
    ('Se listan por población dentro de la base, no por proximidad o cobertura confirmada.',
     'Ordenadas por población dentro de la base.'),
    # duplicates of the consolidated statement
    (' No se afirma que estén especializados en esta categoría.', ''),
    (' Este portal no muestra anuncios individuales ni confirma inventario disponible.', ''),
    (' No se publican cantidades de inmuebles en venta sin inventario comprobado.', ''),
]

PT = [
    ('<p class="disclosure">Este diretório não publica imóveis individuais nem garante atendimento em cada região ou categoria. Confirme os dados antes de decidir.</p>',
     '<p class="disclosure">A InmueblesPY reúne informações públicas de profissionais imobiliários e não publica anúncios de imóveis. Antes de fechar negócio, confirme os dados de contato e a documentação do imóvel. <a href="/pt-br/metodologia/">Como este diretório é elaborado</a></p>'),
    ('<p class="section-lead">Diretório pela cidade de sede informada. Confirme os contatos antes de contratar.</p>',
     '<p class="section-lead">Profissionais com sede informada nesta cidade, conforme o levantamento do diretório.</p>'),
    ('<p class="hint">Não presumimos atendimento comercial nesta cidade.</p>',
     '<p class="hint">Têm sede em outra cidade do departamento: pergunte se atendem esta cidade.</p>'),
    ('Quer conferir outras opções por conta própria? Abra uma pesquisa pública; os resultados são externos e não são verificados pelo InmueblesPY.',
     'Quer conferir outras opções por conta própria? Os resultados desta pesquisa são externos à InmueblesPY.'),
    ('Listadas por população na base, não por proximidade ou cobertura de atendimento confirmada.',
     'Ordenadas por população na base.'),
    (' Isso não comprova especialização na categoria.', ''),
    (' Este portal não exibe anúncios individuais nem confirma estoque disponível.', ''),
    (' Não são publicadas quantidades de imóveis à venda sem inventário comprovado.', ''),
]

# Removed only where a price reference is actually shown on the page.
PRICE_CONTRADICTION = [
    '<p class="ep-note">En el relevamiento aportado existe una referencia observada para esta categoría, pero no se publica una cotización sin verificar licencia, actualidad y metodología.</p>',
    '<p class="ep-note">O levantamento fornecido possui uma referência observada para esta categoria, mas não publicamos cotação sem verificar licença, atualização e metodologia.</p>',
]


def apply(path, src, ctx):
    pairs = ES if "/es/" in path.replace("\\", "/") else PT
    for old, new in pairs:
        src = src.replace(old, new)
    if "v10-price-evidence" in src:
        for frag in PRICE_CONTRADICTION:
            src = src.replace(frag, "")
    return src
