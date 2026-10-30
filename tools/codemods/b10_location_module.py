# -*- coding: utf-8 -*-
"""Publish each municipality's verifiable location facts.

Until now a page about a small municipality carried its population and nothing
else that was specific to it. With GeoNames coordinates every municipality can
state where it is and what is near it, and those facts are genuinely its own:
all 195 municipalities have a different set of three nearest neighbours.

Everything here is computed from data/municipality_coordinates.csv and cites
the GeoNames identifier it came from. Distances are straight-line and say so,
because this project has no routing data and should not imply it. The
Portuguese edition adds the distance to the nearest border crossing into
Brazil, which is the question a Brazilian buyer actually asks.
"""
import html as _html
import os
import re
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C
import facts as FA

ORDER = 100
TITLE = "Add a verifiable location and distances module per municipality"
SELECT = r"^/(es/venta|pt-br/comprar|es/zonas|pt-br/regioes)/"

MARK = 'class="ep-module ep-location"'
ZONE = {"es": "/es/zonas/", "pt-br": "/pt-br/regioes/"}
PT_DEPT = {"asuncion": "assuncao"}

# Crossings into Brazil that exist as municipalities in the dataset.
BORDER = ["alto-parana/ciudad-del-este", "canindeyu/salto-del-guaira",
          "amambay/pedro-juan-caballero"]

T = {
    "es": {
        "h2": "Ubicación y distancias de {city}",
        "lead": ("Punto de referencia del municipio y distancias en línea recta hasta "
                 "otras localidades. No son distancias por ruta."),
        "coords": "Coordenadas", "to_capital": "Distancia a Asunción",
        "nearest": "Municipio más cercano", "near_h3": "Localidades cercanas para ampliar la búsqueda",
        "c_place": "Localidad", "c_dist": "Distancia", "c_pop": "Habitantes (2022)",
        "c_prof": "Perfiles con sede",
        "note": "Coordenadas: GeoNames (CC BY 4.0), identificador {gid}; el punto es "
                "{kind}. Distancia en línea recta entre puntos de referencia.",
        "kind_adm2": "el centro del distrito",
        "kind_place": "la localidad cabecera",
        "border": "Distancia a la frontera con Brasil",
        "seat": "Respecto de {seat}", "seat_val": "{km} km al {dir}",
        "natrank": "Posición nacional por población",
        "natrank_val": "{r} de {n} municipios relevados",
        "dirs": ["norte", "noreste", "este", "sureste", "sur", "suroeste", "oeste", "noroeste"],
    },
    "pt-br": {
        "h2": "Localização e distâncias de {city}",
        "lead": ("Ponto de referência do município e distâncias em linha reta até "
                 "outras localidades. Não são distâncias por estrada."),
        "coords": "Coordenadas", "to_capital": "Distância até Assunção",
        "nearest": "Município mais próximo", "near_h3": "Localidades próximas para ampliar a busca",
        "c_place": "Localidade", "c_dist": "Distância", "c_pop": "Habitantes (2022)",
        "c_prof": "Perfis com sede",
        "note": "Coordenadas: GeoNames (CC BY 4.0), identificador {gid}; o ponto é "
                "{kind}. Distância em linha reta entre pontos de referência.",
        "kind_adm2": "o centro do distrito",
        "kind_place": "a localidade sede",
        "border": "Distância até a fronteira com o Brasil",
        "seat": "Em relação a {seat}", "seat_val": "{km} km a {dir}",
        "natrank": "Posição nacional por população",
        "natrank_val": "{r} de {n} municípios pesquisados",
        "dirs": ["norte", "nordeste", "leste", "sudeste", "sul", "sudoeste", "oeste", "noroeste"],
    },
}

_F = None
_GID = None


def _facts():
    global _F, _GID
    if _F is None:
        _F = FA.Facts()
        _GID = {}
        import csv
        p = os.path.join(C.DATA, "municipality_coordinates.csv")
        if os.path.exists(p):
            with open(p, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    _GID[r["municipality_key"]] = (r["geonames_id"], r["geonames_feature"])
    return _F


def _num(v, dec=1):
    return f"{v:.{dec}f}".replace(".", ",")


def _pop(n):
    """Thousands separated with a dot, as both editions already render it."""
    return f"{n:,}".replace(",", ".") if n else "—"


def _km(d):
    return _num(d, 0) if d >= 100 else _num(d, 1)


def _url(key, lang):
    dept = key.split("/")[0]
    rest = key.split("/")[1] if "/" in key else None
    if lang == "pt-br":
        dept = PT_DEPT.get(dept, dept)
    return ZONE[lang] + dept + "/" + (rest + "/" if rest else "")


def _city_key(url, F):
    m = re.match(r"^/(?:es/venta|pt-br/comprar)/", url)
    if m:
        return F.city_key_from_url(url)
    m = re.match(r"^/(?:es/zonas|pt-br/regioes)/([a-z0-9-]+)(?:/([a-z0-9-]+))?/$", url)
    if m:
        a, b = m.group(1), m.group(2)
        a = {"assuncao": "asuncion"}.get(a, a)
        if b and f"{a}/{b}" in F.cities:
            return f"{a}/{b}"
        if a in F.cities and not b:
            return a
    return None


LOC_RE = re.compile(r'<section class="ep-module ep-location">.*?</section>', re.S)


def apply(path, src, ctx):
    src = LOC_RE.sub("", src)
    F = _facts()
    lang = C.page_lang(path)
    key = _city_key(C.rel_url(path), F)
    if not lang or not key or key not in F.coords:
        return src
    anchor = src.find('<p class="ep-footnote">')
    if anchor < 0:
        return src

    t = T[lang]
    lat, lon = F.coords[key]
    city = F.name_by_key.get(key, key)
    near = F.nearest_municipalities(key, 5)
    if not near:
        return src

    facts = [(t["coords"], f"{_num(lat, 4)} · {_num(lon, 4)}")]
    d_cap = F.distance_km(key, "asuncion")
    if d_cap is not None and key != "asuncion":
        facts.append((t["to_capital"], f"{_km(d_cap)} km"))
    nk, nd = near[0]
    facts.append((t["nearest"], f"{F.name_by_key.get(nk, nk)} ({_km(nd)} km)"))

    # Orientation relative to the department's largest municipality: the
    # quickest way for a reader to place a district they do not know.
    seat = F.dept_seat(key)
    if seat and seat != key:
        d_seat = F.distance_km(key, seat)
        brg = F.bearing_deg(seat, key)
        if d_seat is not None and brg is not None:
            card = t["dirs"][int((brg + 22.5) % 360 // 45)]
            facts.append((t["seat"].format(seat=F.name_by_key.get(seat, seat)),
                          t["seat_val"].format(km=_km(d_seat), dir=card)))
    r, n = F.national_rank(key)
    if r:
        facts.append((t["natrank"], t["natrank_val"].format(r=r, n=n)))
    if lang == "pt-br":
        cands = [(b, F.distance_km(key, b)) for b in BORDER if F.distance_km(key, b) is not None]
        if cands:
            bk, bd = min(cands, key=lambda x: x[1])
            facts.append((t["border"], f"{F.name_by_key.get(bk, bk)} ({_km(bd)} km)"))

    gid, feat = _GID.get(key, ("", ""))
    note = t["note"].format(gid=gid, kind=t["kind_adm2"] if feat == "ADM2" else t["kind_place"])
    dl = "".join(
        f"<div class=\"ep-fact\"><dt>{_html.escape(a, quote=False)}</dt>"
        f"<dd>{_html.escape(b, quote=False)}</dd></div>" for a, b in facts)
    # A comparison table rather than a bare list: distance, population and how
    # many professionals are seated there are the three things a buyer uses to
    # decide where else to look, and all three come from the dataset.
    rows = "".join(
        f'<tr><td><a href="{_url(k, lang)}">'
        f'{_html.escape(F.name_by_key.get(k, k), quote=False)}</a></td>'
        f"<td>{_km(d)} km</td>"
        f"<td>{_pop(F.population(k))}</td>"
        f"<td>{F.profiles[k]}</td></tr>" for k, d in near)
    items = (
        f'<div class="ep-table-wrap"><table class="ep-table"><thead><tr>'
        f'<th scope="col">{_html.escape(t["c_place"], quote=False)}</th>'
        f'<th scope="col">{_html.escape(t["c_dist"], quote=False)}</th>'
        f'<th scope="col">{_html.escape(t["c_pop"], quote=False)}</th>'
        f'<th scope="col">{_html.escape(t["c_prof"], quote=False)}</th>'
        f"</tr></thead><tbody>{rows}</tbody></table></div>")

    mod = (
        f'<section {MARK}><h2>{_html.escape(t["h2"].format(city=city), quote=False)}</h2>'
        f'<p>{_html.escape(t["lead"], quote=False)}</p>'
        f'<dl class="ep-facts">{dl}</dl>'
        f'<h3>{_html.escape(t["near_h3"], quote=False)}</h3>'
        f'{items}'
        f'<p class="ep-note">{_html.escape(note, quote=False)}</p>'
        f"</section>")
    return src[:anchor] + mod + src[anchor:]
