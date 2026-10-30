"""Rewrite every published profile count from the dataset.

Three municipalities were over-counted by exactly one in the department table
and in the summary sentence, and one of them (Benjamín Aceval) was credited
with a profile it does not have. Numbers are now emitted from data/dataset.json
so the several blocks on a page cannot disagree with each other again.
"""
import os
import re
import sys

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
sys.path.insert(0, LIB)
import corpus as C
import facts as FA

ORDER = 30
TITLE = "Emit profile counts from the dataset instead of per-block values"
SELECT = r"^/(es/venta|pt-br/comprar)/"

_F = None


def _facts():
    global _F
    if _F is None:
        _F = FA.Facts()
    return _F


ROW_RE = re.compile(
    r'(<td><a href="/(?:es/zonas|pt-br/regioes)/([a-z0-9-]+(?:/[a-z0-9-]+)?)/">[^<]*</a></td>'
    r"<td>[^<]*</td><td>)(\d+)(</td>)"
)
V6_RE = re.compile(
    r'(<a href="/(?:es/zonas|pt-br/regioes)/([a-z0-9-]+(?:/[a-z0-9-]+)?)/">[^<]*</a>\s*<span>\()(\d+)( perfi)'
)


def apply(path, src, ctx):
    F = _facts()
    url = C.rel_url(path)
    key = F.city_key_from_url(url)
    if not key:
        return src

    local = F.profiles[key]
    others = F.others_in_dept(key)
    chans = F.with_channel[key]

    # 1. department table: "Perfiles identificados" / "Perfis identificados"
    src = ROW_RE.sub(lambda m: m.group(1) + str(F.profiles[m.group(2)]) + m.group(4), src)
    # 2. related-cities list
    src = V6_RE.sub(lambda m: m.group(1) + str(F.profiles[m.group(2)]) + m.group(4), src)

    # 3. "Perfiles con sede indicada en la ciudad" fact
    src = re.sub(
        r"(>(?:Perfiles con sede indicada en la ciudad|Perfis com sede informada na cidade)</dt><dd>)\d+(</dd>)",
        lambda m: m.group(1) + str(local) + m.group(2),
        src,
    )
    # 4. "Zonas registradas" / "Regiões cadastradas"
    src = re.sub(
        r"(>(?:Zonas registradas en la base|Regiões cadastradas na base)</dt><dd>)\d+(</dd>)",
        lambda m: m.group(1) + str(len(F.neighbourhoods(key))) + m.group(2),
        src,
    )
    # 5. summary sentence
    src = re.sub(
        r"(reúne )\d+( perfiles con ciudad declarada en [^<]*? y )\d+( en otras localidades)",
        lambda m: m.group(1) + str(local) + m.group(2) + str(others) + m.group(3),
        src,
    )
    src = re.sub(
        r"(reúne )\d+( perfis com sede informada em [^<]*? e )\d+( em outras cidades)",
        lambda m: m.group(1) + str(local) + m.group(2) + str(others) + m.group(3),
        src,
    )
    # 6. proof paragraph
    src = re.sub(
        r"(Se identificaron )\d+( perfiles con sede declarada en la ciudad; )\d+( tienen)",
        lambda m: m.group(1) + str(local) + m.group(2) + str(chans) + m.group(3),
        src,
    )
    src = re.sub(
        r"(Foram encontrados )\d+( perfis com sede informada na cidade; )\d+( possuem)",
        lambda m: m.group(1) + str(local) + m.group(2) + str(chans) + m.group(3),
        src,
    )
    return src
