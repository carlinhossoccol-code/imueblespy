#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconcile, select and optimise real profile images - publishing only what is proven.

Input is the ZIP produced by the Google Places photo collector (one folder per
profile with an ``info.json`` and up to ten photos). Nothing from that ZIP is
ever written into the repository: it is extracted into a work directory that
must live *outside* the repository, and only images that pass every gate below
are optimised into ``site/assets/profiles/``.

Gates, in order. An image is published only if it passes all of them:

1. **Profile identity** - the Google place is the profile, not a namesake, a
   sibling branch or another office of the same franchise (``match``).
2. **Image identity** - the photo was published by the business itself on its
   own listing. A third-party upload at the right place is not proof that the
   picture shows the business.
3. **Right of use** - a row in ``data/image_rights.csv`` documents the basis
   (written authorisation, own photo, licence) with evidence and a reviewer.
   Finding a photo on Google is *not* a basis: Google Maps Platform terms do
   not allow storing Places photos and republishing them outside the API.
   This pipeline never infers or invents a right of use.
4. **Human review of content** - the same row records what the image shows
   (logo, facade, interior, team, institutional). That classification cannot be
   made reliably by a script, and alt text is generated from it, so nothing is
   described that a reviewer did not confirm.

Everything that fails a gate stays in the review queue
(``data/images_audit/fila_revisao.csv``) with the reason.

Stages (each one checkpointed in the work directory, so a re-run only redoes
what changed):

    extract    verify the ZIP (size, SHA-256, CRC of every member), unpack it
    inventory  hash, dimensions, perceptual hash, logo hints - per image
    match      profile identity per folder
    select     <= 5 distinct candidates per profile, duplicates removed
    optimize   WebP variants of the candidates (work dir only, for review)
    publish    approved images -> site/assets/profiles + data/profile_images.json
    report     audit CSV/JSON in data/images_audit/

Usage:
    python3 -I tools/images/pipeline.py --zip /path/imagens.zip \\
        --work /path/outside/repo [--sha256 <expected>] [--stages all]
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
AUDIT = DATA / "images_audit"
SITE = REPO / "site"
ASSET_DIR = SITE / "assets" / "profiles"
ASSET_URL = "/assets/profiles"
MANIFEST = DATA / "profile_images.json"
RIGHTS = DATA / "image_rights.csv"

VERSION = 1           # bump to invalidate every checkpoint
EXTRACT_VERSION = 2   # 2: ZIP names decoded as UTF-8
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PER_PROFILE = 5
MIN_SIDE = 200        # below this a photo is not usable at gallery size
NEAR_DUP = 6          # dHash Hamming distance treated as the same picture

# What a reviewer may record, in display priority order.
TYPES = ["logo", "fachada", "interior", "equipe", "institucional"]
BASES = {"autorizacao_escrita", "foto_propria", "licenca"}
RIGHTS_FIELDS = ["sha256", "profile_id", "image_type", "basis", "evidence",
                 "granted_by", "granted_date", "reviewed_by", "reviewed_date", "notes"]

# Variants: (name, box, max_bytes). Box sizes come from the components:
# .identity is 62x62 in directory cards, .profile-logo 96x96 on the profile,
# both object-fit:contain; 2x covers high-density screens. The gallery column
# is at most ~320 CSS px on desktop and full width (<= 480) on phones.
PRIMARY_VARIANTS = [("124", 124, 30_000), ("192", 192, 60_000)]
GALLERY_VARIANTS = [("480", 480, 80_000), ("960", 960, 180_000)]

GOOGLE_BASIS_NOTE = ("Foto obtida pela Google Places API; os termos da Google Maps Platform "
                     "não permitem armazenar nem republicar a foto fora da API e não há licença "
                     "do autor registrada em data/image_rights.csv")


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
    px = list(g.getdata())
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
        zf.extractall(raw)
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
            q = Counter((r >> 3, g >> 3, b >> 3) for r, g, b in small.getdata())
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
    c = Counter(r["decision"] for r in res.values())
    log(f"match: {dict(c)}")
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
    sha_profiles = defaultdict(set)
    for im in images:
        m = matches.get(im["folder"])
        if im.get("ok") and m and m["profile_id"]:
            sha_profiles[im["sha256"]].add(m["profile_id"])

    by_folder = defaultdict(list)
    for im in images:
        by_folder[im["folder"]].append(im)

    for folder, imgs in by_folder.items():
        m = matches.get(folder, {})
        info = infos.get(folder, {})
        prof = profiles.get(m.get("profile_id", ""), {})
        for im in imgs:
            im["profile_id"] = m.get("profile_id", "")
            im["profile_identity"] = m.get("decision", "pendente")
            im["owner"] = bool(prof) and is_owner(im, info, prof.get("name", ""))
            reasons = []
            if not im.get("ok"):
                reasons.append("arquivo_invalido")
            else:
                if min(im["width"], im["height"]) < MIN_SIDE and not im["logo_hint"]:
                    reasons.append("resolucao_insuficiente")
                if max(im["width"], im["height"]) / max(1, min(im["width"], im["height"])) > 3:
                    reasons.append("proporcao_extrema")
                if len(sha_profiles.get(im["sha256"], ())) > 1:
                    reasons.append("mesma_imagem_em_outro_perfil")
            if im["profile_identity"] == "rejeitado":
                reasons.append("perfil_rejeitado")
            im["exclude"] = reasons
            if im["profile_identity"] == "confirmado" and im["owner"]:
                im["image_identity"] = "confirmada"
            elif im["profile_identity"] == "confirmado":
                im["image_identity"] = "pendente_autor_terceiro"
            elif im["profile_identity"] == "rejeitado":
                im["image_identity"] = "rejeitada"
            else:
                im["image_identity"] = "pendente_perfil"

        # Rank: business's own uploads first, logos first, then resolution.
        pool = [im for im in imgs if not im["exclude"]]
        pool.sort(key=lambda i: (not i["owner"], not i["logo_hint"], -(i["width"] * i["height"]), i["file"]))
        kept, hashes = [], []
        for im in pool:
            if any(hamming(im["dhash"], h) <= NEAR_DUP for h in hashes):
                im["exclude"].append("duplicata")
                continue
            if len(kept) >= MAX_PER_PROFILE:
                im["exclude"].append("excedente_maximo_5")
                continue
            hashes.append(im["dhash"])
            kept.append(im)
        for rank, im in enumerate(kept, 1):
            im["candidate_rank"] = rank
    n = sum(1 for i in images if i.get("candidate_rank"))
    log(f"select: {n} candidates (<= {MAX_PER_PROFILE} per profile, duplicates removed)")


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


def render_variant(src: Path, box: int, max_bytes: int, square: bool, logo: bool) -> tuple[bytes, int, int]:
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        alpha = logo and (im.mode in ("RGBA", "LA", "P"))
        im = im.convert("RGBA" if alpha else "RGB")
        if square and not logo:
            im = ImageOps.fit(im, (box, box), Image.Resampling.LANCZOS)
        else:
            im.thumbnail((box, box) if square else (box, box * 4), Image.Resampling.LANCZOS)
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
    out = work / "optimized"
    out.mkdir(parents=True, exist_ok=True)
    specs = [("p" + n, b, mb, True) for n, b, mb in PRIMARY_VARIANTS] + \
            [("g" + n, b, mb, False) for n, b, mb in GALLERY_VARIANTS]
    jobs, todo = [], []
    for im in images:
        if not im.get("candidate_rank"):
            continue
        for name, box, max_bytes, square in specs:
            dst = out / f"{im['sha256'][:20]}-{name}-v{VERSION}.webp"
            todo.append((im, name, dst))
            if not (dst.exists() and dst.with_suffix(".json").exists()):
                jobs.append((str(root / im["rel"]), str(dst), box, max_bytes, square, im["logo_hint"]))
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
def load_rights() -> list[dict]:
    if not RIGHTS.exists():
        return []
    with open(RIGHTS, encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("sha256") or "").strip()]


ALT = {
    "logo": ("Logotipo de {n}", "Logotipo de {n}"),
    "fachada": ("Fachada de la oficina de {n}{en}", "Fachada do escritório de {n}{em}"),
    "interior": ("Interior de la oficina de {n}", "Interior do escritório de {n}"),
    "equipe": ("Equipo de {n}", "Equipe de {n}"),
    "institucional": ("Imagen institucional de {n}", "Imagem institucional de {n}"),
}


def stage_publish(images, profiles) -> list[dict]:
    by_sha = defaultdict(list)
    for im in images:
        if im.get("ok"):
            by_sha[im["sha256"]].append(im)
    approved = defaultdict(list)
    decisions = []
    for r in load_rights():
        sha, pid = r["sha256"].strip(), r["profile_id"].strip()
        problems = []
        cands = [i for i in by_sha.get(sha, []) if i.get("profile_id") == pid]
        im = cands[0] if cands else None
        if not im:
            problems.append("imagem_nao_pertence_ao_perfil")
        else:
            if im["image_identity"] != "confirmada":
                problems.append("identidade_nao_confirmada:" + im["image_identity"])
            if not im.get("candidate_rank"):
                problems.append("fora_da_selecao:" + ",".join(im["exclude"]))
        if r.get("image_type") not in TYPES:
            problems.append("tipo_nao_revisado")
        if r.get("basis") not in BASES:
            problems.append("base_de_uso_invalida")
        for f in ("evidence", "granted_by", "granted_date", "reviewed_by", "reviewed_date"):
            if not (r.get(f) or "").strip():
                problems.append(f"campo_vazio:{f}")
        decisions.append({"sha256": sha, "profile_id": pid, "ok": not problems, "problems": problems})
        if not problems:
            approved[pid].append((r, im))

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    manifest, keep = {}, set()
    for pid, items in sorted(approved.items(), key=lambda kv: int(kv[0])):
        prof = profiles[pid]
        items.sort(key=lambda ri: (TYPES.index(ri[0]["image_type"]), ri[1]["candidate_rank"]))
        items = items[:MAX_PER_PROFILE]
        entries, seen_type = [], Counter()
        for r, im in items:
            t = r["image_type"]
            seen_type[t] += 1
            base = f"{slugify(split_name(prof['name'])[0])}-{slugify(prof.get('city') or 'paraguay')}-{t}-{pid}"
            if seen_type[t] > 1:
                base += f"-{seen_type[t]}"
            city = prof.get("city") or ""
            alt_es, alt_pt = ALT[t]
            fmt = {"n": prof["name"], "en": f" en {city}" if city else "", "em": f" em {city}" if city else ""}
            entry = {"type": t, "sha256": im["sha256"], "alt_es": alt_es.format(**fmt),
                     "alt_pt": alt_pt.format(**fmt), "basis": r["basis"], "variants": {}}
            for vname, v in im["variants"].items():
                fname = f"{base}-{vname}.webp"
                dst = ASSET_DIR / fname
                if not dst.exists() or dst.read_bytes() != Path(v["path"]).read_bytes():
                    shutil.copyfile(v["path"], dst)
                keep.add(fname)
                entry["variants"][vname] = {"src": f"{ASSET_URL}/{fname}", "w": v["w"], "h": v["h"],
                                            "bytes": v["bytes"]}
            entries.append(entry)
        manifest[pid] = {"slug": prof["slug"], "images": entries}

    for f in ASSET_DIR.iterdir():          # idempotent: nothing stale survives
        if f.name not in keep:
            f.unlink()
    if not any(ASSET_DIR.iterdir()):
        ASSET_DIR.rmdir()
    write_json(MANIFEST, {"version": VERSION, "profiles": manifest})
    log(f"publish: {sum(len(v['images']) for v in manifest.values())} image(s) for {len(manifest)} profile(s); "
        f"{sum(1 for d in decisions if not d['ok'])} rights row(s) refused")
    return decisions


# ---------------------------------------------------------------------------
# stage: report
# ---------------------------------------------------------------------------
def stage_report(images, infos, matches, profiles, decisions, zip_meta) -> dict:
    manifest = read_json(MANIFEST, {"profiles": {}})["profiles"]
    published = {e["sha256"] + ":" + pid for pid, v in manifest.items() for e in v["images"]}
    rights_ok = {d["sha256"] + ":" + d["profile_id"] for d in decisions if d["ok"]}
    rights_rows = {d["sha256"] + ":" + d["profile_id"]: d for d in decisions}

    inv_rows, queue = [], []
    for im in sorted(images, key=lambda i: i["rel"]):
        key = f"{im.get('sha256', '')}:{im.get('profile_id', '')}"
        info = infos.get(im["folder"], {})
        if key in published:
            status, reason = "publicada", ""
        elif key in rights_rows:
            status, reason = "direitos_recusados", ";".join(rights_rows[key]["problems"])
        else:
            status, reason = "sem_base_de_uso_documentada", GOOGLE_BASIS_NOTE
        v = im.get("variants") or {}
        row = {
            "image_id": (im.get("sha256") or "")[:12], "pasta": im["folder"], "arquivo": im["file"],
            "profile_id": im.get("profile_id", ""), "identidade_perfil": im.get("profile_identity", ""),
            "identidade_imagem": im.get("image_identity", ""),
            "autor": "proprio_estabelecimento" if im.get("owner") else "terceiro",
            # Third-party contributors are private people: their names and
            # profile links stay in the work directory, not in the repository.
            "autor_uri": (im.get("authors") or [{}])[0].get("uri", "") if im.get("owner") else "",
            "origem": "Google Maps Platform - Places Photos",
            "google_maps": info.get("google_maps", ""), "place_id": info.get("place_id", ""),
            "largura": im.get("width", ""), "altura": im.get("height", ""), "bytes": im.get("bytes", 0),
            "sha256": im.get("sha256", ""), "dhash": im.get("dhash", ""),
            "logo_provavel": int(bool(im.get("logo_hint"))),
            "candidata": im.get("candidate_rank", ""), "exclusao": ";".join(im.get("exclude", [])),
            "bytes_otimizado": sum(x["bytes"] for x in v.values()) if v else "",
            "direitos": status, "motivo_direitos": reason,
        }
        inv_rows.append(row)
        if status != "publicada" and im.get("candidate_rank"):
            queue.append(row)
    inv_fields = list(inv_rows[0].keys()) if inv_rows else []
    write_csv(AUDIT / "inventario.csv", inv_rows, inv_fields)
    write_csv(AUDIT / "fila_revisao.csv", sorted(queue, key=lambda r: (int(r["profile_id"] or 0), r["candidata"])),
              inv_fields)

    by_pid = defaultdict(list)
    for m in matches.values():
        by_pid[m["profile_id"]].append(m)
    prof_rows = []
    for pid in sorted(profiles, key=int):
        p = profiles[pid]
        ms = by_pid.get(pid, [])
        m = ms[0] if ms else {}
        info = infos.get(m.get("folder", ""), {})
        imgs = [i for i in images if i.get("profile_id") == pid]
        prof_rows.append({
            "profile_id": pid, "slug": p["slug"], "nome": p["name"], "cidade": p["city"],
            "departamento": p["department"], "pasta": m.get("folder", ""),
            "identidade": m.get("decision", "sem_imagens_no_zip"),
            "motivos": ";".join(m.get("reasons", [])),
            "nome_google": info.get("nome_google", ""), "endereco_google": info.get("endereco_google", ""),
            "place_id": info.get("place_id", ""), "pontuacao_nome": m.get("name_score", ""),
            "cidade_confere": {True: "sim", False: "nao", None: ""}.get(m.get("city_ok")),
            "dominio_confere": "sim" if m.get("domain_ok") else "",
            "imagens": len(imgs), "candidatas": sum(1 for i in imgs if i.get("candidate_rank")),
            "publicadas": len(manifest.get(pid, {}).get("images", [])),
        })
    write_csv(AUDIT / "perfis.csv", prof_rows, list(prof_rows[0].keys()))

    cand = [i for i in images if i.get("candidate_rank")]
    pub_imgs = [e for v in manifest.values() for e in v["images"]]
    summary = {
        "zip": zip_meta,
        "imagens_processadas": len(images),
        "imagens_validas": sum(1 for i in images if i.get("ok")),
        "pastas_no_zip": len(infos),
        "perfis_no_site": len(profiles),
        "perfis_com_pasta": len({m["profile_id"] for m in matches.values() if m["profile_id"]}),
        "identidade_perfil": dict(Counter(m["decision"] for m in matches.values())),
        "identidade_imagem": dict(Counter(i.get("image_identity", "") for i in images)),
        "imagens_identidade_confirmada": sum(1 for i in images if i.get("image_identity") == "confirmada"),
        "imagens_com_base_de_uso_documentada": len(rights_ok),
        "linhas_de_direitos_recusadas": sum(1 for d in decisions if not d["ok"]),
        "candidatas_selecionadas": len(cand),
        "candidatas_identidade_confirmada": sum(1 for i in cand if i.get("image_identity") == "confirmada"),
        "imagens_integradas": len(pub_imgs),
        "perfis_com_imagens_integradas": len(manifest),
        "pendentes_identidade": sum(1 for i in cand if i.get("image_identity") != "confirmada"),
        "pendentes_somente_direitos": sum(1 for i in cand if i.get("image_identity") == "confirmada"
                                          and f"{i['sha256']}:{i['profile_id']}" not in published),
        "exclusoes": dict(Counter(r for i in images for r in i.get("exclude", []))),
        "bytes_originais_total": sum(i.get("bytes", 0) for i in images),
        "bytes_originais_candidatas": sum(i.get("bytes", 0) for i in cand),
        "bytes_otimizados_candidatas": sum(sum(v["bytes"] for v in (i.get("variants") or {}).values()) for i in cand),
        "bytes_publicados": sum(v["bytes"] for e in pub_imgs for v in e["variants"].values()),
        "regras": {"max_por_perfil": MAX_PER_PROFILE, "lado_minimo_px": MIN_SIDE,
                   "dhash_duplicata": NEAR_DUP, "variantes_principal": PRIMARY_VARIANTS,
                   "variantes_galeria": GALLERY_VARIANTS, "versao": VERSION},
    }
    write_json(AUDIT / "resumo.json", summary)
    return summary


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", default=os.environ.get("INMUEBLESPY_IMAGES_ZIP"), required=False)
    ap.add_argument("--work", default=os.environ.get("INMUEBLESPY_IMAGES_WORK"), required=False)
    ap.add_argument("--sha256", default=os.environ.get("INMUEBLESPY_IMAGES_SHA256"))
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
    stage_select(images, infos, matches, profiles)
    stage_optimize(images, root, work)
    decisions = stage_publish(images, profiles)
    ck = read_json(work / "checkpoints" / "extract.json", {})
    summary = stage_report(images, infos, matches, profiles, decisions,
                           {"bytes": zip_path.stat().st_size, "sha256": ck.get("sha256", "")})
    # Full detail (third-party author names included) stays in the work dir.
    write_json(work / "detail.json", {"images": images, "matches": matches})
    log(json.dumps({k: summary[k] for k in ("imagens_processadas", "imagens_identidade_confirmada",
                                            "imagens_com_base_de_uso_documentada", "imagens_integradas",
                                            "perfis_com_imagens_integradas")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
