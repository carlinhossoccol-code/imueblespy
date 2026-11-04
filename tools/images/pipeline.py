#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconcile, review and optimise real profile images - never on the wrong business.

Input is the ZIP of photos collected from Google Maps (one folder per profile
with an ``info.json`` and up to ten photos). Nothing from that ZIP is written
into the repository as is: it is extracted into a work directory that must live
*outside* the repository, and only reviewed images are optimised into
``site/assets/profiles/``.

An image is published when both gates pass (see tools/images/README.md):

1. **Profile identity** - the Google place is the profile, not a namesake, a
   sibling branch, another franchise office or a development (``match``, then
   ``data/images_review/identidade.csv`` for the cases rules left pending).
2. **Content** - a reviewer classified it as logo, facade, interior, team or
   institutional (``data/images_review/conteudo.csv``). Photos of listed
   properties and lots never ship; alt text comes from the class only.

Stages (checkpointed in the work directory):

    extract    verify the ZIP (size, SHA-256, CRC of every member), unpack it
    inventory  hash, dimensions, perceptual hash, logo hints - per image
    match      profile identity per folder (+ manual decisions)
    select     <= 8 distinct candidates per accepted profile for review
    sheets     numbered contact sheets of unreviewed candidates (--sheets)
    optimize   WebP variants (work dir)
    publish    reviewed images -> site/assets/profiles + data/profile_images.json
    report     reports/imagens-*.csv|json

Usage:
    python3 -I tools/images/pipeline.py --zip /path/imagens.zip \\
        --work /path/outside/repo [--sha256 <expected>] [--sheets]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 80_000_000  # refuse decompression bombs, allow 48 MP photos

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
SITE = REPO / "site"
ASSET_DIR = SITE / "assets" / "profiles"
ASSET_URL = "/assets/profiles"
MANIFEST = DATA / "profile_images.json"
REVIEW_DIR = DATA / "images_review"
IDENTITY_REVIEW = REVIEW_DIR / "identidade.csv"   # manual identity decisions
CONTENT_REVIEW = REVIEW_DIR / "conteudo.csv"      # what each candidate shows
REPORTS = REPO / "reports"
REVIEW_POOL = 10      # candidates per profile shown for content review (every photo of a folder)

VERSION = 1           # bump to invalidate every checkpoint
EXTRACT_VERSION = 2   # 2: ZIP names decoded as UTF-8
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PER_PROFILE = 5
MIN_SIDE = 200        # below this a photo is not usable at gallery size
NEAR_DUP = 6          # dHash Hamming distance treated as the same picture

# What a reviewer may record, in display priority order.
TYPES = ["logo", "fachada", "interior", "equipe", "institucional"]

# Variants: (name, box, max_bytes). Box sizes come from the components:
# .identity is 62x62 in directory cards, .profile-logo 96x96 on the profile,
# both object-fit:contain; 2x covers high-density screens. The gallery column
# is at most ~320 CSS px on desktop and full width (<= 480) on phones.
PRIMARY_VARIANTS = [("124", 124, 30_000), ("192", 192, 60_000)]
GALLERY_VARIANTS = [("480", 480, 80_000), ("960", 960, 180_000)]



# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace("&", " y ").replace("’", "").replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\bre max\b", "remax", text)
    text = re.sub(r"\bcentury 21\b", "century21", text)
    return " ".join(text.split())


def slugify(text: str) -> str:
    return norm(text).replace(" ", "-")[:60].strip("-") or "perfil"


GENERIC = set("""
inmobiliaria inmobiliarias inmobiliario inmobiliarios imobiliaria imobiliarias imoveis imovel
real estate state realty realtor s a sa srl r l eas sae sociedad anonima responsabilidad limitada
unipersonal sucursal casa central matriz agencia oficina oficinas representacion bienes raices
propiedades propiedad negocios inmuebles inmueble de del la las los el y e en group grupo py
paraguay paraguaya paraguayo asesor asesora agente consultora emprendimientos emprendimiento
servicios inversiones inversion gestion gestiones gestoria soluciones desarrollo desarrollos
constructora arquitectura juridico venta ventas the and corporacion compania asesoria
suc constructor inmobilaria agentes mision
""".split())
FRANCHISES = {"century21", "remax", "era", "skyone", "keymex"}

# Spellings Google uses for the same municipality.
CITY_ALIASES = {
    "ciudad del este": ["ciudad del este", "cd del este", "cde"],
    "pedro juan caballero": ["pedro juan caballero", "pjc"],
    "doctor juan eulogio estigarribia": ["juan eulogio estigarribia", "campo 9", "campo nueve"],
    "san estanislao": ["san estanislao", "santani"],
    "tomas romero pereira": ["tomas romero pereira", "maria auxiliadora"],
    "juan emilio oleary": ["oleary", "juan e oleary"],
    "san pedro del ycuamandiyu": ["san pedro del ycuamandiyu", "ycuamandiyu", "san pedro"],
    "san ignacio guazu": ["san ignacio"],
    "coronel oviedo": ["coronel oviedo", "cnel oviedo"],
    "presidente franco": ["presidente franco", "pdte franco"],
    "mariano roque alonso": ["mariano roque alonso", "m r alonso"],
    "yguazu": ["yguazu"],
}


def city_variants(city: str) -> list[str]:
    n = norm(city)
    return CITY_ALIASES.get(n, [n]) if n else []


def contains_phrase(hay: str, needle: str) -> bool:
    return bool(needle) and re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", hay) is not None


def registrable(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"com", "net", "org", "gov", "edu"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def dhash(img: Image.Image) -> str:
    g = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = g.tobytes()  # one byte per pixel in mode L
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# ---------------------------------------------------------------------------
# profiles
# ---------------------------------------------------------------------------
def load_profiles() -> dict[str, dict]:
    with open(DATA / "professionals.csv", encoding="utf-8", newline="") as fh:
        rows = {r["id"]: r for r in csv.DictReader(fh)}
    official = {}
    for r in rows.values():
        if "sitio oficial" in (r.get("source") or "").lower() and r.get("source_url"):
            official[r["id"]] = registrable(r["source_url"])
    try:
        with open(DATA / "networks.csv", encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("professional_id") and r.get("evidence_domain"):
                    official.setdefault(r["professional_id"], registrable("https://" + r["evidence_domain"]))
    except FileNotFoundError:
        pass
    for pid, r in rows.items():
        r["official_domain"] = official.get(pid, "")
    return rows


def split_name(name: str) -> tuple[str, str]:
    """'X — Sucursal Y' -> ('X', 'Sucursal Y'). Only an em/en dash or a spaced hyphen splits."""
    m = re.split(r"\s+[—–]\s+|\s+-\s+", name, maxsplit=1)
    return (m[0], m[1]) if len(m) == 2 else (name, "")


def distinctive(text: str, extra_generic: set[str] = frozenset()) -> list[str]:
    return [t for t in norm(text).split() if t not in GENERIC and t not in extra_generic]


# ---------------------------------------------------------------------------
# stage: extract
# ---------------------------------------------------------------------------
def stage_extract(zip_path: Path, work: Path, expected_sha: str | None) -> Path:
    raw = work / "raw"
    ck = work / "checkpoints" / "extract.json"
    st = zip_path.stat()
    prev = read_json(ck, {})
    key = {"size": st.st_size, "mtime": int(st.st_mtime), "version": EXTRACT_VERSION}
    if prev.get("key") == key and (raw / prev.get("root", "_")).is_dir():
        if expected_sha and prev.get("sha256") != expected_sha:
            sys.exit(f"ZIP SHA-256 {prev.get('sha256')} differs from expected {expected_sha}")
        log(f"extract: checkpoint ok ({prev['members']} members, sha256 {prev['sha256'][:12]}…)")
        return raw / prev["root"]

    log("extract: hashing ZIP …")
    digest = sha256_file(zip_path)
    if expected_sha and digest != expected_sha:
        sys.exit(f"ZIP SHA-256 {digest} differs from expected {expected_sha}; refusing to process")
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad:
            sys.exit(f"ZIP member failed its CRC check: {bad}; refusing to process")
        names = zf.namelist()
        for n in names:
            p = Path(n)
            if p.is_absolute() or ".." in p.parts:
                sys.exit(f"unsafe path in ZIP: {n}")
        # Names without the UTF-8 flag are CP437 by the ZIP spec; this archive
        # stored UTF-8 bytes without the flag, so 'Katueté' read as 'Katuet├⌐'.
        for info in zf.infolist():
            if not info.flag_bits & 0x800:
                try:
                    info.filename = info.filename.encode("cp437").decode("utf-8")
                except UnicodeError:
                    pass
        names = [i.filename for i in zf.infolist()]
        if raw.exists():
            shutil.rmtree(raw)
        raw.mkdir(parents=True)
        for info in zf.infolist():
            zf.extract(info, raw)
    roots = {Path(n).parts[0] for n in names}
    root = roots.pop() if len(roots) == 1 else "."
    write_json(ck, {"key": key, "sha256": digest, "members": len(names), "root": root})
    log(f"extract: {len(names)} members verified and unpacked")
    return raw / root


# ---------------------------------------------------------------------------
# stage: inventory
# ---------------------------------------------------------------------------
def analyse_image(path: Path) -> dict:
    rec = {"bytes": path.stat().st_size}
    try:
        rec["sha256"] = sha256_file(path)
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            rec["format"] = (im.format or "").lower()
            im = ImageOps.exif_transpose(im)
            im.load()
            rec["width"], rec["height"] = im.size
            rec["mode"] = im.mode
            alpha = False
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                a = im.convert("RGBA").getchannel("A")
                alpha = a.getextrema()[0] < 250
            rec["alpha"] = alpha
            rec["dhash"] = dhash(im)
            small = im.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
            raw = small.tobytes()
            q = Counter((raw[i] >> 3, raw[i + 1] >> 3, raw[i + 2] >> 3) for i in range(0, len(raw), 3))
            rec["colors"] = len(q)
            rec["top8_share"] = round(sum(c for _, c in q.most_common(8)) / 4096, 3)
            # A hint only: flat artwork or transparency usually means a logo.
            rec["logo_hint"] = bool(alpha or (rec["top8_share"] >= 0.55 and rec["colors"] <= 400))
            rec["ok"] = True
    except Exception as e:  # corrupt, truncated or not an image
        rec["ok"] = False
        rec["error"] = f"{type(e).__name__}: {e}"[:200]
    return rec


def stage_inventory(root: Path, work: Path) -> tuple[list[dict], dict[str, dict]]:
    ck_path = work / "checkpoints" / "inventory.json"
    cache = read_json(ck_path, {})
    if cache.get("version") != VERSION:
        cache = {"version": VERSION, "files": {}}
    files = cache["files"]
    images, infos = [], {}
    fresh = 0
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        info = read_json(folder / "info.json")
        if info is None:
            continue
        infos[folder.name] = info
        listed = {f["arquivo"]: f for f in info.get("fotos", [])}
        on_disk = sorted(p.name for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT)
        for name in sorted(set(listed) | set(on_disk)):
            p = folder / name
            rel = f"{folder.name}/{name}"
            if not p.exists():
                images.append({"rel": rel, "folder": folder.name, "file": name, "ok": False,
                               "error": "listada no info.json mas ausente no ZIP", "bytes": 0})
                continue
            st = p.stat()
            k = f"{st.st_size}:{int(st.st_mtime)}"
            rec = files.get(rel)
            if not rec or rec.get("_k") != k:
                rec = analyse_image(p)
                rec["_k"] = k
                files[rel] = rec
                fresh += 1
                if fresh % 200 == 0:
                    write_json(ck_path, cache)
            meta = listed.get(name, {})
            authors = meta.get("autores") or []
            images.append({**{k2: v for k2, v in rec.items() if k2 != "_k"},
                           "rel": rel, "folder": folder.name, "file": name,
                           "listed": name in listed, "authors": authors})
    seen = {im["rel"] for im in images}
    for stale in [k for k in files if k not in seen]:   # renamed or removed files
        del files[stale]
    write_json(ck_path, cache)
    log(f"inventory: {len(images)} images in {len(infos)} folders ({fresh} analysed, rest from checkpoint)")
    return images, infos


# ---------------------------------------------------------------------------
# stage: match (profile identity)
# ---------------------------------------------------------------------------
def token_hits(want: list[str], have_tokens: list[str], have_joined: str) -> float:
    if not want:
        return 0.0
    total = sum(len(t) for t in want)
    got = 0
    for t in want:
        if t in have_tokens or (len(t) >= 4 and t in have_joined):
            got += len(t)
        elif len(t) >= 5 and any(SequenceMatcher(None, t, h).ratio() >= 0.86 for h in have_tokens):
            got += len(t)
    return got / total


def match_folder(info: dict, profiles: dict, by_name: dict) -> dict:
    out = {"folder": None, "profile_id": "", "decision": "pendente", "reasons": []}
    name = info.get("nome_csv", "")
    cands = by_name.get(norm(name), [])
    loc = info.get("cidade_departamento_csv", "")
    if len(cands) > 1:
        cands = [p for p in cands if norm(p["city"]) and norm(p["city"]) in norm(loc)] or cands
    if len(cands) != 1:
        out["decision"] = "pendente"
        out["reasons"].append("perfil_nao_identificado" if not cands else "perfil_homonimo")
        return out
    prof = cands[0]
    out["profile_id"] = prof["id"]

    g_name = info.get("nome_google") or ""
    g_addr = info.get("endereco_google") or ""
    g_tokens = norm(g_name).split()
    g_joined = norm(g_name).replace(" ", "")
    addr_n = norm(g_addr)

    base, branch = split_name(prof["name"])
    city = prof.get("city") or ""
    city_tokens = set(norm(city).split())
    m = re.match(r"(.*?)\s*\(([^)]+)\)\s*(.*)", base)       # 'Inmobiliaria del Este (IDESA)'
    alternatives = [base] + ([m.group(1) + " " + m.group(3), m.group(2)] if m else [])
    best = 0.0
    for alt in alternatives:
        want = distinctive(alt)
        best = max(best, token_hits(want, g_tokens, g_joined))
    want_main = distinctive(base)
    weak = sum(len(t) for t in want_main) < 4
    out["name_score"] = round(best, 2)

    # Words the Google name adds that the profile does not have: another office.
    branch_tokens = set(norm(branch).split())
    prof_all = set(norm(prof["name"]).split()) | city_tokens | set(norm(prof.get("department", "")).split())
    extra = [t for t in g_tokens if t not in GENERIC and t not in prof_all
             and not any(contains_phrase(norm(c), t) for c in city_variants(city))
             and not t.isdigit()]
    franchise = bool(set(want_main) & FRANCHISES)

    city_ok = None
    if city:
        city_ok = any(contains_phrase(addr_n, v) for v in city_variants(city))
    domain_ok = bool(prof.get("official_domain") and info.get("site")
                     and registrable(info["site"]) == prof["official_domain"])
    out.update(city_ok=city_ok, domain_ok=domain_ok)

    if best < 0.5 and not domain_ok:
        out["decision"] = "rejeitado"
        out["reasons"].append("nome_google_de_outro_estabelecimento")
        return out
    if best < 0.99:
        out["reasons"].append("nome_google_parcial")
    if weak and not domain_ok:
        out["reasons"].append("nome_curto_ou_generico")
    if franchise and extra:
        out["reasons"].append("outra_unidade_da_rede:" + " ".join(extra[:3]))
    elif extra and ((len(want_main) <= 1 and not domain_ok) or len(extra) >= 2):
        # The official domain proves the brand, not the unit: it cannot clear this.
        # e.g. 'Buen Barrio Universitario - Crecer Inmobiliaria': a development
        # of the company, whose photos show lots for sale, not the branch.
        out["reasons"].append("nome_google_com_termos_extras:" + " ".join(extra[:3]))
    if city_ok is None:
        if not domain_ok:
            out["reasons"].append("cidade_do_perfil_nao_informada")
    elif not city_ok:
        if franchise or branch_tokens:
            out["reasons"].append("endereco_de_outra_cidade_ou_filial")
        elif not domain_ok:
            out["reasons"].append("endereco_google_sem_a_cidade_do_perfil")
    if branch and city and city_ok is False:
        out["decision"] = "rejeitado"
        return out

    out["decision"] = "confirmado" if not out["reasons"] else "pendente"
    return out


def stage_match(infos: dict, profiles: dict) -> dict[str, dict]:
    by_name = defaultdict(list)
    for p in profiles.values():
        by_name[norm(p["name"])].append(p)
    res = {}
    for folder, info in infos.items():
        r = match_folder(info, profiles, by_name)
        r["folder"] = folder
        r["place_id"] = info.get("place_id", "")
        res[folder] = r

    # One Google place cannot be several profiles. Keep it for the single profile
    # that passed every check; if none or several did, nobody gets it.
    by_place = defaultdict(list)
    for r in res.values():
        if r["place_id"]:
            by_place[r["place_id"]].append(r)
    for group in by_place.values():
        if len(group) < 2:
            continue
        winners = [r for r in group if r["decision"] == "confirmado"]
        for r in group:
            if len(winners) == 1 and r is winners[0]:
                continue
            if r["decision"] == "confirmado":
                r["decision"] = "pendente"
            r["reasons"].append(f"lugar_google_compartilhado_por_{len(group)}_perfis")
    # Documented human review of the cases the rules left pending
    # (data/images_review/identidade.csv). 'aceito_principal' = moderate doubt:
    # the profile gets its single most reliable image and no gallery.
    overrides = {}
    if IDENTITY_REVIEW.exists():
        with open(IDENTITY_REVIEW, encoding="utf-8", newline="") as fh:
            overrides = {r["profile_id"]: r for r in csv.DictReader(fh)}
    for r in res.values():
        o = overrides.get(r["profile_id"])
        if not o:
            continue
        r["override"] = f"{o['decisao']}: {o['motivo']}"
        r["override_decision"] = o["decisao"]
        if o["decisao"] in ("aceito", "aceito_principal"):
            r["decision"] = "confirmado"
            r["scope"] = "principal" if o["decisao"] == "aceito_principal" else "completo"
        elif o["decisao"] == "rejeitado":
            r["decision"] = "rejeitado"
    c = Counter(r["decision"] for r in res.values())
    log(f"match: {dict(c)} ({len(overrides)} manual identity decision(s))")
    return res


# ---------------------------------------------------------------------------
# stage: select
# ---------------------------------------------------------------------------
def is_owner(img: dict, info: dict, prof_name: str) -> bool:
    names = {norm(info.get("nome_google", "")), norm(prof_name), norm(split_name(prof_name)[0])}
    names.discard("")
    for a in img.get("authors") or []:
        an = norm(a.get("nome") or "")
        if an and (an in names or any(SequenceMatcher(None, an, n).ratio() >= 0.9 for n in names)):
            return True
    return False


def stage_select(images, infos, matches, profiles) -> None:
    """Review pool: up to REVIEW_POOL distinct, usable images per accepted profile."""
    by_folder = defaultdict(list)
    for im in images:
        by_folder[im["folder"]].append(im)
    accepted_place = {}
    for m in matches.values():
        if m["decision"] == "confirmado":
            accepted_place[m["profile_id"]] = m["place_id"]
    sha_profiles = defaultdict(set)
    for im in images:
        m = matches.get(im["folder"])
        if im.get("ok") and m and m["profile_id"] in accepted_place:
            sha_profiles[im["sha256"]].add(m["profile_id"])

    for folder, imgs in by_folder.items():
        m = matches.get(folder, {})
        info = infos.get(folder, {})
        prof = profiles.get(m.get("profile_id", ""), {})
        for im in imgs:
            im["profile_id"] = m.get("profile_id", "")
            im["profile_identity"] = m.get("decision", "pendente")
            im["scope"] = m.get("scope", "")
            im["owner"] = bool(prof) and is_owner(im, info, prof.get("name", ""))
            reasons = []
            if not im.get("ok"):
                reasons.append("arquivo_invalido")
            else:
                if min(im["width"], im["height"]) < MIN_SIDE and not im["logo_hint"]:
                    reasons.append("resolucao_insuficiente")
                if max(im["width"], im["height"]) / max(1, min(im["width"], im["height"])) > 3:
                    reasons.append("proporcao_extrema")
                others = sha_profiles.get(im["sha256"], set()) - {im["profile_id"]}
                # Same picture in another accepted profile: fine when both profiles are
                # the same Google place (one office listed twice), otherwise flagged and
                # allowed only as a brand logo at publish time.
                im["shared_with"] = sorted(p for p in others if accepted_place.get(p) != accepted_place.get(im["profile_id"]))
            if im["profile_identity"] == "rejeitado":
                reasons.append("perfil_rejeitado")
            elif im["profile_identity"] == "pendente":
                reasons.append("perfil_pendente")
            im["exclude"] = reasons
            if im["profile_identity"] == "confirmado":
                im["image_identity"] = "confirmada" if im["owner"] else "lugar_confirmado_autor_terceiro"
            elif im["profile_identity"] == "rejeitado":
                im["image_identity"] = "rejeitada"
            else:
                im["image_identity"] = "pendente_perfil"

        pool = [im for im in imgs if not im["exclude"]]
        pool.sort(key=lambda i: (not i["owner"], not i["logo_hint"], -(i["width"] * i["height"]), i["file"]))
        kept, hashes = [], []
        for im in pool:
            if any(hamming(im["dhash"], h) <= NEAR_DUP for h in hashes):
                im["exclude"].append("duplicata")
                continue
            if len(kept) >= REVIEW_POOL:
                im["exclude"].append(f"fora_do_lote_de_revisao_{REVIEW_POOL}")
                continue
            hashes.append(im["dhash"])
            kept.append(im)
        for rank, im in enumerate(kept, 1):
            im["candidate_rank"] = rank
    n = sum(1 for i in images if i.get("candidate_rank"))
    log(f"select: {n} candidates for review (<= {REVIEW_POOL} per accepted profile, duplicates removed)")


def load_content_review() -> dict[tuple[str, str], str]:
    out = {}
    if CONTENT_REVIEW.exists():
        with open(CONTENT_REVIEW, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                out[(r["sha256"].strip(), r["profile_id"].strip())] = r["classe"].strip()
    return out


def stage_sheets(images, root: Path, work: Path) -> int:
    """Numbered contact sheets of candidates still lacking a content decision."""
    from PIL import ImageDraw
    review = load_content_review()
    todo = [i for i in images if i.get("candidate_rank") and (i["sha256"], i["profile_id"]) not in review]
    todo.sort(key=lambda i: (int(i["profile_id"]), i["candidate_rank"]))
    out = work / "sheets"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    cols, rows, tw, th = 8, 6, 190, 175
    index = []
    for s in range(0, len(todo), cols * rows):
        sheet = Image.new("RGB", (cols * tw, rows * th), "white")
        d = ImageDraw.Draw(sheet)
        for k, im in enumerate(todo[s:s + cols * rows]):
            n = s + k
            with Image.open(root / im["rel"]) as src:
                t = ImageOps.exif_transpose(src).convert("RGB")
                t.thumbnail((tw - 6, th - 30))
            x, y = (k % cols) * tw, (k // cols) * th
            sheet.paste(t, (x + 3, y + 3))
            d.text((x + 3, y + th - 26), f"{n} #{im['profile_id']} {'P' if im['owner'] else 'T'}", fill="black")
            d.text((x + 3, y + th - 14), split_name(im.get("_pname", ""))[0][:30], fill="black")
            index.append({"n": n, "sheet": s // (cols * rows), "sha256": im["sha256"], "profile_id": im["profile_id"]})
        sheet.save(out / f"sheet-{s // (cols * rows):02d}.jpg", quality=80)
    write_csv(out / "index.csv", index, ["n", "sheet", "sha256", "profile_id"])
    log(f"sheets: {len(todo)} image(s) awaiting content review in {out}")
    return len(todo)


# ---------------------------------------------------------------------------
# stage: optimize
# ---------------------------------------------------------------------------
def encode_webp(im: Image.Image, max_bytes: int, keep_alpha: bool) -> bytes:
    """Highest quality that fits the budget; never below q=50."""
    import io
    best = None
    for q in (86, 82, 78, 74, 70, 65, 60, 55, 50):
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=q, method=6, exact=keep_alpha)
        data = buf.getvalue()
        best = data
        if len(data) <= max_bytes:
            break
    if keep_alpha:
        buf = io.BytesIO()
        im.save(buf, "WEBP", lossless=True, method=6)
        if len(buf.getvalue()) < len(best):
            best = buf.getvalue()
    return best


def trim_logo(im: Image.Image) -> Image.Image:
    """Drop uniform borders (letterbox bars, transparent margins) around a logo."""
    from PIL import ImageChops
    if im.mode == "RGBA":
        bbox = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    else:
        rgb = im.convert("RGB")
        bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
        bbox = ImageChops.difference(rgb, bg).convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not bbox or (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) > 0.97 * im.width * im.height:
        return im
    pad = round(0.04 * max(bbox[2] - bbox[0], bbox[3] - bbox[1]))
    return im.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                    min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad)))


def render_variant(src: Path, box: int, max_bytes: int, square: bool, logo: bool) -> tuple[bytes, int, int]:
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        alpha = logo and (im.mode in ("RGBA", "LA", "P"))
        im = im.convert("RGBA" if alpha else "RGB")
        if logo:
            im = trim_logo(im)
        if square and not logo:
            im = ImageOps.fit(im, (box, box), Image.Resampling.LANCZOS)
        else:
            im.thumbnail((box, box) if square else (box, box * 4), Image.Resampling.LANCZOS)
        data = encode_webp(im, max_bytes, alpha)
        # Still over budget at the lowest quality: shrink a little rather than
        # ship a heavy file or an ugly one.
        while len(data) > max_bytes and min(im.size) > 160:
            im = im.resize((round(im.width * 0.85), round(im.height * 0.85)), Image.Resampling.LANCZOS)
            data = encode_webp(im, max_bytes, alpha)
        return data, im.width, im.height


def _encode_job(job):
    src, dst, box, max_bytes, square, logo = job
    data, w, h = render_variant(Path(src), box, max_bytes, square, logo)
    tmp = Path(dst).with_suffix(".part")
    tmp.write_bytes(data)
    write_json(Path(dst).with_suffix(".json"), {"w": w, "h": h})
    tmp.replace(dst)            # the .webp appears last: its presence is the checkpoint
    return dst


def stage_optimize(images, root: Path, work: Path) -> None:
    from concurrent.futures import ProcessPoolExecutor
    review = load_content_review()
    out = work / "optimized"
    out.mkdir(parents=True, exist_ok=True)
    specs = [("p" + n, b, mb, True) for n, b, mb in PRIMARY_VARIANTS] + \
            [("g" + n, b, mb, False) for n, b, mb in GALLERY_VARIANTS]
    jobs, todo = [], []
    for im in images:
        if not im.get("candidate_rank"):
            continue
        for name, box, max_bytes, square in specs:
            # The reviewed class decides the rendering: a logo is fitted whole and
            # trimmed, a photo is cropped. Renderings that differ from the original
            # automatic guess get their own cache name, so nothing else re-encodes.
            cls = review.get((im["sha256"], im["profile_id"]), "")
            logo = cls == "logo" if cls else im["logo_hint"]
            tag = "-L2" if cls == "logo" else ("-P2" if im["logo_hint"] and not logo else "")
            im["render_logo"] = logo
            dst = out / f"{im['sha256'][:20]}-{name}{tag}-v{VERSION}.webp"
            todo.append((im, name, dst))
            if not (dst.exists() and dst.with_suffix(".json").exists()) or dst.stat().st_size > max_bytes:
                jobs.append((str(root / im["rel"]), str(dst), box, max_bytes, square, logo))
    jobs = list(dict.fromkeys(jobs))   # the same picture in two folders is encoded once
    if jobs:
        with ProcessPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
            for n, _ in enumerate(ex.map(_encode_job, jobs, chunksize=4), 1):
                if n % 500 == 0:
                    log(f"optimize: {n}/{len(jobs)}")
    for im, name, dst in todo:
        m = read_json(dst.with_suffix(".json"))
        im.setdefault("variants", {})[name] = {"path": str(dst), "bytes": dst.stat().st_size,
                                               "w": m["w"], "h": m["h"]}
    log(f"optimize: {len(jobs)} variant(s) encoded, {len(todo) - len(jobs)} from checkpoint")


# ---------------------------------------------------------------------------
# stage: publish
# ---------------------------------------------------------------------------
ALT = {
    "logo": ("Logotipo de {n}", "Logomarca de {n}"),
    "fachada": ("Fachada de {n}{en}", "Fachada de {n}{em}"),
    "interior": ("Oficina de {n}{en}", "Escritório de {n}{em}"),
    "equipe": ("Equipo de {n}", "Equipe de {n}"),
    "institucional": ("Imagen institucional de {n}", "Imagem institucional de {n}"),
}
TYPE_CAP = {"logo": 1, "fachada": 2, "interior": 2, "equipe": 2, "institucional": 1}


def maps_link(url: str) -> str:
    m = re.search(r"[?&]cid=(\d+)", url or "")
    return f"https://maps.google.com/?cid={m.group(1)}" if m else ""


def stage_publish(images, infos, matches, profiles) -> dict:
    review = load_content_review()
    by_pid = defaultdict(list)
    for im in images:
        cls = review.get((im.get("sha256", ""), im.get("profile_id", "")))
        im["content"] = cls or ""
        if not im.get("candidate_rank"):
            continue
        if cls is None:
            im["exclude"].append("sem_revisao_de_conteudo")
            continue
        if cls not in TYPES:
            im["exclude"].append(cls)          # e.g. rejeitar:imovel_anunciado
            continue
        if im.get("shared_with") and cls != "logo":
            im["exclude"].append("mesma_foto_em_outro_perfil")
            continue
        by_pid[im["profile_id"]].append(im)

    city_ok = {m["profile_id"]: m.get("city_ok") for m in matches.values()}
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    manifest, keep = {}, set()
    for pid in sorted(by_pid, key=int):
        prof = profiles[pid]
        items = sorted(by_pid[pid], key=lambda i: (TYPES.index(i["content"]), i["candidate_rank"]))
        chosen, per_type = [], Counter()
        for im in items:
            if per_type[im["content"]] >= TYPE_CAP[im["content"]] or len(chosen) >= MAX_PER_PROFILE:
                im["exclude"].append("excedente_por_tipo_ou_total")
                continue
            per_type[im["content"]] += 1
            chosen.append(im)
        if chosen and chosen[0]["scope"] == "principal":   # moderate doubt: main image only
            for im in chosen[1:]:
                im["exclude"].append("perfil_somente_imagem_principal")
            chosen = chosen[:1]
        base_name = split_name(prof["name"])[0]
        city = prof.get("city") or ""
        # The city goes into alt text and slug only when it is the profile's own.
        say_city = city if city and city_ok.get(pid) is not False else ""
        entries, seen = [], Counter()
        for im in chosen:
            t = im["content"]
            seen[t] += 1
            slug = f"{slugify(base_name)}-{slugify(say_city or 'paraguay')}-{t}-{pid}"
            if seen[t] > 1:
                slug += f"-{seen[t]}"
            fmt = {"n": base_name, "en": f" en {say_city}" if say_city else "", "em": f" em {say_city}" if say_city else ""}
            entry = {"type": t, "sha256": im["sha256"], "alt_es": ALT[t][0].format(**fmt),
                     "alt_pt": ALT[t][1].format(**fmt), "author": "estabelecimento" if im["owner"] else "terceiro",
                     "source": maps_link(infos.get(im["folder"], {}).get("google_maps", "")), "variants": {}}
            # Logos fill the identity slot only; photos always go to the gallery and
            # also fill the slot when they are the profile's primary image.
            wanted = [n for n in im["variants"] if (n.startswith("p") and (t == "logo" or not entries))
                      or (n.startswith("g") and t != "logo")]
            for vname, v in ((n, im["variants"][n]) for n in wanted):
                fname = f"{slug}-{vname[1:]}.webp" if vname.startswith("p") else f"{slug}-g{vname[1:]}.webp"
                dst = ASSET_DIR / fname
                if not dst.exists() or dst.read_bytes() != Path(v["path"]).read_bytes():
                    shutil.copyfile(v["path"], dst)
                keep.add(fname)
                entry["variants"][vname] = {"src": f"{ASSET_URL}/{fname}", "w": v["w"], "h": v["h"],
                                            "bytes": v["bytes"]}
            entries.append(entry)
            im["published"] = True
        manifest[pid] = {"slug": prof["slug"], "images": entries}

    for f in ASSET_DIR.iterdir():          # idempotent: nothing stale survives
        if f.name not in keep:
            f.unlink()
    if not any(ASSET_DIR.iterdir()):
        ASSET_DIR.rmdir()
    write_json(MANIFEST, {"version": VERSION, "profiles": manifest})
    log(f"publish: {sum(len(v['images']) for v in manifest.values())} image(s) for {len(manifest)} profile(s)")
    return manifest


# ---------------------------------------------------------------------------
# stage: report
# ---------------------------------------------------------------------------
def stage_report(images, infos, matches, profiles, manifest, zip_meta) -> dict:
    REPORTS.mkdir(parents=True, exist_ok=True)
    pub_files = {(e["sha256"], pid): e for pid, v in manifest.items() for e in v["images"]}

    def row(im):
        info = infos.get(im["folder"], {})
        e = pub_files.get((im.get("sha256", ""), im.get("profile_id", "")))
        return {
            "image_id": (im.get("sha256") or "")[:12], "profile_id": im.get("profile_id", ""),
            "perfil": profiles.get(im.get("profile_id", ""), {}).get("name", ""),
            "pasta": im["folder"], "arquivo": im["file"],
            "identidade_perfil": im.get("profile_identity", ""), "identidade_imagem": im.get("image_identity", ""),
            # Third-party contributors are private people: no names or profile links here.
            "autor": "estabelecimento" if im.get("owner") else "terceiro",
            "origem": maps_link(info.get("google_maps", "")), "place_id": info.get("place_id", ""),
            "largura": im.get("width", ""), "altura": im.get("height", ""), "bytes_original": im.get("bytes", 0),
            "sha256": im.get("sha256", ""), "classe": im.get("content", ""),
            "motivo": ";".join(im.get("exclude", [])),
            "bytes_publicados": sum(v["bytes"] for v in e["variants"].values()) if e else "",
        }

    rows = [row(i) for i in sorted(images, key=lambda i: (int(i.get("profile_id") or 0), i["rel"]))]
    fields = list(rows[0].keys())
    approved = [r for r in rows if r["bytes_publicados"] != ""]
    # Pending = could still be used: unresolved identity, or an accepted profile's
    # image that was never put in front of a reviewer. Everything else not
    # published was decided against, with the reason in 'motivo'.
    def is_pending(r):
        return r["identidade_perfil"] == "pendente" or (
            r["identidade_perfil"] == "confirmado" and not r["classe"]
            and any(k in r["motivo"] for k in ("fora_do_lote", "sem_revisao")))
    pending = [r for r in rows if r["bytes_publicados"] == "" and is_pending(r)]
    rejected = [r for r in rows if r["bytes_publicados"] == "" and not is_pending(r)]
    write_csv(REPORTS / "imagens-aprovadas.csv", approved, fields)
    write_csv(REPORTS / "imagens-pendentes.csv", pending, fields)
    write_csv(REPORTS / "imagens-rejeitadas.csv", rejected, fields)

    man_rows = []
    for pid, v in sorted(manifest.items(), key=lambda kv: int(kv[0])):
        for pos, e in enumerate(v["images"]):
            for vname, var in e["variants"].items():
                man_rows.append({"profile_id": pid, "slug_perfil": v["slug"], "posicao": pos, "tipo": e["type"],
                                 "uso": "principal" if vname.startswith("p") else "galeria",
                                 "arquivo": var["src"], "largura": var["w"], "altura": var["h"], "bytes": var["bytes"],
                                 "alt_es": e["alt_es"], "alt_pt": e["alt_pt"], "autor": e["author"],
                                 "origem": e["source"], "sha256_original": e["sha256"]})
    write_csv(REPORTS / "imagens-manifest.csv", man_rows, list(man_rows[0].keys()) if man_rows else ["profile_id"])

    # Origin and rights risk, kept apart from identity: a photo can be certainly
    # of the right business and still carry a rights risk, and vice versa.
    RISK = {
        "estabelecimento": ("medio", "Enviada pelo proprio estabelecimento ao Google Maps; sem autorizacao "
                                     "direta registrada; os termos da Google Maps Platform nao permitem "
                                     "republicar fotos fora da API"),
        "terceiro": ("alto", "Enviada por um usuario do Google Maps (pessoa fisica); sem licenca do autor; "
                             "os termos da Google Maps Platform nao permitem republicar fotos fora da API"),
    }
    rights_rows = []
    for pid, v in sorted(manifest.items(), key=lambda kv: int(kv[0])):
        for e in v["images"]:
            lvl, why = RISK[e["author"]]
            rights_rows.append({"profile_id": pid, "slug_perfil": v["slug"], "tipo": e["type"],
                                "arquivos": " ".join(x["src"] for x in e["variants"].values()),
                                "sha256_original": e["sha256"], "origem": "Google Maps (Places Photos)",
                                "link_origem": e["source"], "autor": e["author"],
                                "risco_direitos": lvl, "observacao": why})
    write_csv(REPORTS / "imagens-origem-direitos.csv", rights_rows,
              list(rights_rows[0].keys()) if rights_rows else ["profile_id"])

    # Coverage: every accepted profile, and why it has no image when it has none.
    imgs_by_pid = defaultdict(list)
    for im in images:
        imgs_by_pid[im.get("profile_id", "")].append(im)
    cov_rows = []
    for m in sorted((m for m in matches.values() if m["decision"] == "confirmado"), key=lambda m: int(m["profile_id"])):
        pid = m["profile_id"]
        imgs, pub_n = imgs_by_pid[pid], len(manifest.get(pid, {}).get("images", []))
        ex = Counter(r.split(":")[0] for i in imgs for r in i.get("exclude", []))
        cls = Counter((i.get("content") or "").split(":")[0] for i in imgs if i.get("content"))
        if pub_n:
            why = "com_imagens"
        elif not imgs:
            why = "pasta_sem_fotos"
        elif cls and set(cls) == {"rejeitar"}:
            why = "todas_as_fotos_eram_imoveis_loteamentos_ou_irrelevantes"
        elif ex.get("mesma_foto_em_outro_perfil"):
            why = "fotos_validas_so_compartilhadas_com_outro_perfil"
        elif ex.get("sem_revisao_de_conteudo") or ex.get(f"fora_do_lote_de_revisao_{REVIEW_POOL}"):
            why = "fotos_ainda_nao_revisadas"
        else:
            why = "fotos_sem_qualidade_tecnica"
        cov_rows.append({"profile_id": pid, "nome": profiles[pid]["name"], "cidade": profiles[pid]["city"],
                         "origem_identidade": "revisao_manual" if m.get("override_decision") else "regras",
                         "escopo": m.get("scope") or "completo", "fotos_na_pasta": len(imgs),
                         "aproveitadas": pub_n, "tipos": ",".join(e["type"] for e in manifest.get(pid, {}).get("images", [])),
                         "situacao": why, "rejeitadas_conteudo": cls.get("rejeitar", 0)})
    write_csv(REPORTS / "imagens-cobertura.csv", cov_rows, list(cov_rows[0].keys()))

    by_pid = defaultdict(list)
    for m in matches.values():
        by_pid[m["profile_id"]].append(m)
    prof_rows = []
    for pid in sorted(profiles, key=int):
        p, m = profiles[pid], (by_pid.get(pid) or [{}])[0]
        info = infos.get(m.get("folder", ""), {})
        imgs = manifest.get(pid, {}).get("images", [])
        prof_rows.append({
            "profile_id": pid, "slug": p["slug"], "nome": p["name"], "cidade": p["city"],
            "departamento": p["department"], "identidade": m.get("decision", "sem_pasta_no_zip"),
            "revisao_manual": m.get("override", ""), "motivos_regras": ";".join(m.get("reasons", [])),
            "nome_google": info.get("nome_google", ""), "endereco_google": info.get("endereco_google", ""),
            "place_id": info.get("place_id", ""), "imagens_publicadas": len(imgs),
            "tipos": ",".join(e["type"] for e in imgs),
        })
    write_csv(REPORTS / "imagens-perfis.csv", prof_rows, list(prof_rows[0].keys()))

    pub = [e for v in manifest.values() for e in v["images"]]
    pub_shas = {e["sha256"] for e in pub}
    typ = Counter(e["type"] for e in pub)
    has = lambda t: sum(1 for v in manifest.values() if any(e["type"] == t for e in v["images"]))
    summary = {
        "zip": zip_meta,
        "imagens_processadas": len(images),
        "imagens_validas": sum(1 for i in images if i.get("ok")),
        "perfis_no_site": len(profiles),
        "pastas_no_zip": len(infos),
        "identidade_perfil": dict(Counter(m["decision"] for m in matches.values())),
        "revisoes_manuais_de_identidade": dict(Counter(m.get("override_decision", "") for m in matches.values()
                                                       if m.get("override_decision"))),
        "candidatas_revisadas": sum(1 for i in images if i.get("candidate_rank")),
        "classes_revisao_conteudo": dict(Counter(i["content"].split(":")[0] if ":" in i["content"] else i["content"]
                                                 for i in images if i.get("content"))),
        "imagens_aproveitadas": len(pub),
        "imagens_aproveitadas_por_tipo": dict(typ),
        "imagens_aproveitadas_autor_estabelecimento": sum(1 for e in pub if e["author"] == "estabelecimento"),
        "risco_direitos": {"medio_enviada_pelo_estabelecimento": sum(1 for e in pub if e["author"] == "estabelecimento"),
                           "alto_enviada_por_terceiro": sum(1 for e in pub if e["author"] == "terceiro"),
                           "perfis_com_alguma_foto_de_terceiro": sum(1 for v in manifest.values()
                                                                     if any(e["author"] == "terceiro" for e in v["images"]))},
        "perfis_com_imagem": len(manifest),
        "perfis_com_logo": has("logo"),
        "perfis_com_fachada": has("fachada"),
        "perfis_com_galeria": sum(1 for v in manifest.values() if any(e["type"] != "logo" for e in v["images"])),
        "perfis_sem_imagem": len(profiles) - len(manifest),
        "cobertura_perfis_aceitos": dict(Counter(r["situacao"] for r in cov_rows)),
        "bytes_originais_acervo": sum(i.get("bytes", 0) for i in images),
        "bytes_originais_aproveitadas": sum(i.get("bytes", 0) for i in images if i.get("published")),
        "bytes_publicados": sum(v["bytes"] for e in pub for v in e["variants"].values()),
        "arquivos_publicados": sum(len(e["variants"]) for e in pub),
        "exclusoes": dict(Counter(r.split(":")[0] for i in images for r in i.get("exclude", []))),
        "regras": {"max_por_perfil": MAX_PER_PROFILE, "limite_por_tipo": TYPE_CAP, "lote_revisao": REVIEW_POOL,
                   "lado_minimo_px": MIN_SIDE, "dhash_duplicata": NEAR_DUP,
                   "variantes_principal": PRIMARY_VARIANTS, "variantes_galeria": GALLERY_VARIANTS},
    }
    write_json(REPORTS / "imagens-resumo.json", summary)
    return summary


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", default=os.environ.get("INMUEBLESPY_IMAGES_ZIP"), required=False)
    ap.add_argument("--work", default=os.environ.get("INMUEBLESPY_IMAGES_WORK"), required=False)
    ap.add_argument("--sha256", default=os.environ.get("INMUEBLESPY_IMAGES_SHA256"))
    ap.add_argument("--sheets", action="store_true", help="also draw contact sheets of unreviewed candidates")
    args = ap.parse_args()
    if not args.zip or not args.work:
        sys.exit("--zip and --work are required (or INMUEBLESPY_IMAGES_ZIP / INMUEBLESPY_IMAGES_WORK)")
    zip_path, work = Path(args.zip).resolve(), Path(args.work).resolve()
    for p in (zip_path, work):
        if p == REPO or REPO in p.parents:
            sys.exit(f"{p} is inside the repository; raw images and the ZIP must stay outside it")
    work.mkdir(parents=True, exist_ok=True)

    root = stage_extract(zip_path, work, args.sha256)
    profiles = load_profiles()
    images, infos = stage_inventory(root, work)
    matches = stage_match(infos, profiles)
    for im in images:
        im["_pname"] = profiles.get(matches.get(im["folder"], {}).get("profile_id", ""), {}).get("name", "")
    stage_select(images, infos, matches, profiles)
    if args.sheets:
        stage_sheets(images, root, work)
    stage_optimize(images, root, work)
    manifest = stage_publish(images, infos, matches, profiles)
    ck = read_json(work / "checkpoints" / "extract.json", {})
    summary = stage_report(images, infos, matches, profiles, manifest,
                           {"bytes": zip_path.stat().st_size, "sha256": ck.get("sha256", "")})
    # Full detail (third-party author names included) stays in the work dir.
    write_json(work / "detail.json", {"images": images, "matches": matches})
    log(json.dumps({k: summary[k] for k in ("imagens_processadas", "imagens_aproveitadas", "perfis_com_imagem",
                                            "perfis_com_logo", "perfis_com_fachada", "perfis_com_galeria")},
                   ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
