"""Remove Portuguese-authored fragments that leaked into the Spanish pages.

The provenance labels ("Fuente consultada", "Origen del registro") and the
published-fields lists were authored in Portuguese and reused verbatim on
/es/ pages. Translating the label preserves the underlying fact while making
the Spanish edition genuinely Spanish. Agency names are unaffected: none of
them contain any of these fragments.
"""
import re

ORDER = 10
TITLE = "Translate Portuguese provenance labels and field names on /es/ pages"
SELECT = r"^/es/"

# Longest first so compound values resolve correctly.
ES_FIXES = [
    # provenance values
    ("associação de imobiliárias", "asociación de inmobiliarias"),
    ("ACIP — associados", "ACIP — asociados"),
    ("registro empresarial de setor imobiliário", "registro empresarial del sector inmobiliario"),
    ("ficha de agência e imóveis publicados", "ficha de agencia e inmuebles publicados"),
    ("agência/corretor com imóveis anunciados", "agencia/agente con inmuebles anunciados"),
    ("Equipe de vendas identificada no site oficial", "Equipo de ventas identificado en el sitio oficial"),
    ("Anúncio imobiliário publicado com nome e telefone do responsável",
     "Anuncio inmobiliario publicado con nombre y teléfono del responsable"),
    ("imobiliária com oferta em", "inmobiliaria con oferta en"),
    ("agência com 41 anúncios publicados, inclusive 18 outubro 2026",
     "agencia con 41 anuncios publicados, incluido el 18 de octubre de 2026"),
    ("SlideProp Paraguai", "SlideProp Paraguay"),
    ("sucursales no site oficial", "sucursales en el sitio oficial"),
    ("Site oficial com telefone e link WhatsApp", "Sitio oficial con teléfono y enlace de WhatsApp"),
    ("Site oficial com endereço e ofertas", "Sitio oficial con dirección y ofertas"),
    ("Site próprio, seção de contato", "Sitio propio, sección de contacto"),
    ("Site oficial; contato e anúncios", "Sitio oficial; contacto y anuncios"),
    ("Perfil e anúncios em", "Perfil y anuncios en"),
    ("Cybo ficha de corretor", "Cybo ficha de agente"),
    ("lista setorial local", "lista sectorial local"),
    ("lista imobiliária", "lista inmobiliaria"),
    ("Diretório imobiliário público", "Directorio inmobiliario público"),
    ("Diretório público", "Directorio público"),
    ("(rede oficial)", "(red oficial)"),
    ("equipe de agentes", "equipo de agentes"),
    ("— imóveis publicados", "— inmuebles publicados"),
    ("site oficial", "sitio oficial"),
    ("Site oficial", "Sitio oficial"),
    ("imobiliárias", "inmobiliarias"),
    ("imobiliária", "inmobiliaria"),
]

# Field tokens inside the "Campos publicados / no informados" lists and the
# "Contactos presentes" fact. Bounded by punctuation so nothing else matches.
# Word-boundary guarded: a bare "da empresa" also occurs inside "cada empresa".
GUARDED_ES_FIXES = [
    (r"(?<![\wá-úÁ-Ú])da imobiliária", "de la inmobiliaria"),
    (r"(?<![\wá-úÁ-Ú])da empresa", "de la empresa"),
]

FIELD_FIXES = [
    (r"(?<![\w>])Telefone(?![\w<])", "Teléfono"),
    (r"(?<![\w>])Website(?![\w<])", "Sitio web"),
    (r"<dd>telefone</dd>", "<dd>teléfono</dd>"),
    (r"<dd>telefone, site</dd>", "<dd>teléfono, sitio web</dd>"),
    (r"<dd>site</dd>", "<dd>sitio web</dd>"),
]


def apply(path, src, ctx):
    # Repair the earlier over-broad replacement before applying the guarded one.
    src = src.replace("cade la empresa", "cada empresa")
    src = src.replace("cade la inmobiliaria", "cada inmobiliaria")
    for a, b in ES_FIXES:
        src = src.replace(a, b)
    for pat, rep in GUARDED_ES_FIXES:
        src = re.sub(pat, rep, src)
    for pat, rep in FIELD_FIXES:
        src = re.sub(pat, rep, src)
    # "telefone" / "site" inside a comma-joined channel list
    def chan(m):
        parts = [p.strip() for p in m.group(1).split(",")]
        tr = {"telefone": "teléfono", "site": "sitio web", "whatsapp": "WhatsApp"}
        return "<dd>" + ", ".join(tr.get(p.lower(), p) for p in parts) + "</dd>"

    src = re.sub(r"<dd>((?:telefone|site|whatsapp)(?:,\s*(?:telefone|site|whatsapp))*)</dd>",
                 chan, src, flags=re.I)
    return src
