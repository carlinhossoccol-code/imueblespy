#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the advertising policy page in both editions.

Section 9 of the brief lists an advertising policy among the pages the site
should maintain, and it did not exist. Every statement on the page is checked
against the code rather than asserted: which pages carry the banner, how its
link is marked up, where it sits in the document, and what it loads.

The page is built from an existing editorial page so the header, footer,
breadcrumb and hero markup stay identical to the rest of the site.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import corpus as C  # noqa: E402

SRC = {"es": "es/metodologia", "pt-br": "pt-br/metodologia"}
DEST = {"es": "es/politica-de-publicidad", "pt-br": "pt-br/politica-de-publicidade"}

META = {
    "es": {
        "title": "Política de publicidad | InmueblesPY",
        "desc": "Cómo InmueblesPY identifica la publicidad, dónde aparece y por qué no "
                "influye en los profesionales listados.",
        "h1": "Política de publicidad",
        "lead": "Qué se publica como publicidad, cómo se identifica y qué separa el "
                "contenido comercial del directorio.",
        "crumb": "Política de publicidad",
    },
    "pt-br": {
        "title": "Política de publicidade | InmueblesPY",
        "desc": "Como a InmueblesPY identifica a publicidade, onde ela aparece e por que "
                "não influencia os profissionais listados.",
        "h1": "Política de publicidade",
        "lead": "O que é publicado como publicidade, como é identificado e o que separa "
                "o conteúdo comercial do diretório.",
        "crumb": "Política de publicidade",
    },
}

BODY = {
    "es": """<section class="reading"><h2>Publicidad propia, no una red de anuncios</h2>
<p>InmueblesPY vende y publica su propio espacio publicitario. El sitio no utiliza Google AdSense ni ninguna otra red de anuncios, y no carga scripts publicitarios de terceros.</p>
<p>Hoy el único anunciante es <strong>Morar no Paraguai</strong>, un servicio de orientación documental para brasileños, publicado en <a href="https://morarnoparaguai.com.br/" rel="sponsored nofollow noopener noreferrer" target="_blank">morarnoparaguai.com.br</a>.</p></section>
<section class="reading"><h2>Cómo se identifica</h2>
<p>Cada pieza publicitaria lleva la etiqueta visible <strong>Publicidade</strong> y un nombre accesible que la anuncia como publicidad a los lectores de pantalla. Los enlaces se marcan con <code>rel="sponsored nofollow"</code> y se abren en una pestaña nueva.</p>
<p>La publicidad nunca se presenta como un perfil del directorio ni como una recomendación editorial.</p></section>
<section class="reading"><h2>Dónde aparece</h2>
<p>El anuncio se muestra únicamente en las páginas en portugués, porque se dirige a compradores brasileños. Las páginas en español no lo incluyen.</p>
<p>Nunca precede a los resultados profesionales ni separa a una empresa de sus datos de contacto. En la portada aparece después de las ciudades y las categorías; en las páginas de municipio y categoría, después del listado de profesionales; en los perfiles, después de la ficha y los contactos de la empresa.</p></section>
<section class="reading"><h2>Independencia editorial</h2>
<p>La publicidad no influye en qué profesionales figuran en el directorio ni en el orden en que aparecen. Los profesionales se listan por ciudad de sede declarada y, cuando no hay sede local, por distancia real desde el municipio consultado.</p>
<p>Ningún profesional paga por ser incluido, por su posición ni por ser destacado. Ninguna página comercial del directorio es contenido pagado.</p></section>
<section class="reading"><h2>Datos y privacidad</h2>
<p>El anuncio no instala cookies ni ejecuta scripts de seguimiento en este sitio. Está compuesto por texto y por el logotipo del anunciante, que se carga desde su dominio: al abrir una página en portugués, el servidor del anunciante recibe esa solicitud de imagen, como ocurre con cualquier recurso alojado fuera del sitio.</p>
<p>InmueblesPY no comparte datos personales con anunciantes. Consultá la <a href="/es/privacidad/">política de privacidad</a> para el tratamiento de datos del sitio.</p></section>
<section class="reading"><h2>Anunciar o reportar un anuncio</h2>
<p>Para consultas comerciales, o para señalar un anuncio que considerés engañoso o inadecuado, escribinos a <a href="mailto:contacto@inmueblespy.com.py">contacto@inmueblespy.com.py</a> (contacto@inmueblespy.com.py).</p>
<p>Revisamos los anuncios antes de publicarlos y retiramos los que no cumplan esta política.</p></section>""",
    "pt-br": """<section class="reading"><h2>Publicidade própria, não uma rede de anúncios</h2>
<p>A InmueblesPY vende e publica seu próprio espaço publicitário. O site não utiliza Google AdSense nem qualquer outra rede de anúncios, e não carrega scripts publicitários de terceiros.</p>
<p>Hoje o único anunciante é o <strong>Morar no Paraguai</strong>, um serviço de orientação documental para brasileiros, publicado em <a href="https://morarnoparaguai.com.br/" rel="sponsored nofollow noopener noreferrer" target="_blank">morarnoparaguai.com.br</a>.</p></section>
<section class="reading"><h2>Como é identificada</h2>
<p>Cada peça publicitária traz o rótulo visível <strong>Publicidade</strong> e um nome acessível que a anuncia como publicidade para leitores de tela. Os links são marcados com <code>rel="sponsored nofollow"</code> e abrem em uma nova aba.</p>
<p>A publicidade nunca é apresentada como um perfil do diretório nem como recomendação editorial.</p></section>
<section class="reading"><h2>Onde aparece</h2>
<p>O anúncio é exibido somente nas páginas em português, porque se dirige a compradores brasileiros. As páginas em espanhol não o incluem.</p>
<p>Ele nunca precede os resultados profissionais nem separa uma empresa de seus dados de contato. Na página inicial aparece depois das cidades e das categorias; nas páginas de município e categoria, depois da lista de profissionais; nos perfis, depois da ficha e dos contatos da empresa.</p></section>
<section class="reading"><h2>Independência editorial</h2>
<p>A publicidade não influencia quais profissionais constam no diretório nem a ordem em que aparecem. Os profissionais são listados pela cidade de sede informada e, quando não há sede local, por distância real a partir do município consultado.</p>
<p>Nenhum profissional paga para ser incluído, pela posição ou por destaque. Nenhuma página comercial do diretório é conteúdo pago.</p></section>
<section class="reading"><h2>Dados e privacidade</h2>
<p>O anúncio não instala cookies nem executa scripts de rastreamento neste site. Ele é composto por texto e pelo logotipo do anunciante, carregado a partir do domínio dele: ao abrir uma página em português, o servidor do anunciante recebe essa requisição de imagem, como acontece com qualquer recurso hospedado fora do site.</p>
<p>A InmueblesPY não compartilha dados pessoais com anunciantes. Consulte a <a href="/pt-br/privacidade/">política de privacidade</a> para o tratamento de dados do site.</p></section>
<section class="reading"><h2>Anunciar ou reportar um anúncio</h2>
<p>Para contato comercial, ou para sinalizar um anúncio que você considere enganoso ou inadequado, escreva para <a href="mailto:contacto@inmueblespy.com.py">contacto@inmueblespy.com.py</a> (contacto@inmueblespy.com.py).</p>
<p>Revisamos os anúncios antes da publicação e retiramos os que não cumprirem esta política.</p></section>""",
}


def build(lang: str) -> str:
    src = C.read(os.path.join(C.SITE, SRC[lang], "index.html"))
    m = META[lang]
    old_url = f"{C.CANONICAL_HOST}/{SRC[lang]}/"
    new_url = f"{C.CANONICAL_HOST}/{DEST[lang]}/"
    other = "pt-br" if lang == "es" else "es"

    out = src
    # URLs: canonical, og:url, and both hreflang targets
    out = out.replace(old_url, new_url)
    out = out.replace(f"{C.CANONICAL_HOST}/{SRC[other]}/", f"{C.CANONICAL_HOST}/{DEST[other]}/")
    # title and description everywhere they are repeated
    old_title = re.search(r"<title>(.*?)</title>", src, re.S).group(1)
    old_desc = re.search(r'<meta content="([^"]*)" name="description"', src).group(1)
    out = out.replace(old_title, m["title"]).replace(old_desc, m["desc"])
    # hero copy
    out = re.sub(r"<h1>.*?</h1>", f"<h1>{m['h1']}</h1>", out, count=1, flags=re.S)
    out = re.sub(r"(<h1>.*?</h1>)<p>.*?</p>", rf"\1<p>{m['lead']}</p>", out, count=1, flags=re.S)
    # breadcrumb leaf
    out = re.sub(r"(<nav aria-label=\"Breadcrumb\".*?<strong>).*?(</strong>)",
                 rf"\g<1>{m['crumb']}\g<2>", out, count=1, flags=re.S)
    # body: replace everything between the breadcrumb wrapper and the data area
    i = out.find('<div class="content reading">')
    j = out.find("</main>")
    if i < 0 or j < 0:
        raise SystemExit(f"unexpected template for {lang}")
    tail_start = out.rfind("</div>", i, j)
    # The Portuguese template carries the advertising banner at the end of the
    # main element; keep it, since it must appear on every Brazilian page.
    banner = re.search(
        r'<div class="shell ad-wrap">\s*<aside\b[^>]*class="mnpb"[^>]*>.*?</aside>\s*</div>',
        out[i:j], re.S)
    out = out[: i + len('<div class="content reading">')] + BODY[lang] + out[tail_start:]
    if banner and "mnpb" not in out:
        k = out.find("</main>")
        out = out[:k] + banner.group(0) + out[k:]
    return out


def main() -> int:
    for lang in ("es", "pt-br"):
        d = os.path.join(C.SITE, DEST[lang])
        os.makedirs(d, exist_ok=True)
        page = build(lang)
        C.write(os.path.join(d, "index.html"), page)
        print(f"  wrote /{DEST[lang]}/  ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
