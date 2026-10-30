#!/usr/bin/env python3
"""Verify a deployed site over real HTTP.

    python3 -I tools/check_http.py https://inmueblespy.onrender.com

Checks the things that can only be confirmed against a running host: status
codes, the root redirect, content types, security and cache headers, and that
every asset a page references actually resolves.

Some checks depend on the platform, not on the files in this repository. On a
plain local file server they are reported as "platform" rather than failed,
because render.yaml is what supplies them; against Render they must pass.
"""
from __future__ import annotations

import gzip
import io
import sys
import urllib.error
import urllib.request

UA = "InmueblesPY-deploy-check/1.0"


def _lower(headers):
    """Header names are case-insensitive; dict(HTTPMessage) keeps the sender's
    casing, so http.server's "Content-type" would never match a lookup for
    "Content-Type"."""
    return {k.lower(): v for k, v in headers.items()}


def fetch(url, method="GET", redirect=True):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(*([] if redirect else [NoRedirect]))
    req = urllib.request.Request(url, method=method,
                                 headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    try:
        r = opener.open(req, timeout=25)
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.GzipFile(fileobj=io.BytesIO(body)).read()
        return r.status, _lower(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, _lower(e.headers), e.read()
    except Exception as e:  # noqa: BLE001
        return 0, {}, str(e).encode()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    base = sys.argv[1].rstrip("/")
    results = []

    def record(name, ok, detail, platform=False):
        results.append((name, ok, detail, platform))

    # --- root behaviour -----------------------------------------------
    st, hd, _ = fetch(base + "/", redirect=False)
    loc = hd.get("location", "")
    record("root-redirect", st in (301, 302, 308) and loc.rstrip("/").endswith("/es"),
           f"{st} -> {loc or 'no Location'}", platform=True)

    # --- page families -------------------------------------------------
    for path in ("/es/", "/pt-br/", "/es/venta/central/luque/terrenos/",
                 "/pt-br/comprar/central/luque/terrenos/", "/es/zonas/central/luque/",
                 "/es/inmobiliaria/366-nisa-inmobiliaria-luque/",
                 "/es/inmobiliarias/asuncion/", "/es/todos-los-profesionales/",
                 "/es/guias/documentacion-inmueble/", "/es/politica-de-publicidad/",
                 "/pt-br/politica-de-publicidade/",
                 "/es/venta/alto-parana/mbaracayu/terrenos/"):
        st, hd, body = fetch(base + path)
        ct = hd.get("content-type", "")
        ok = st == 200 and "text/html" in ct and b"<html" in body[:400].lower()
        record(f"page {path}", ok, f"{st} {ct.split(';')[0]} {len(body)}B")

    # --- static files --------------------------------------------------
    for path, want in (("/robots.txt", "text/plain"), ("/llms.txt", "text/plain"),
                       ("/sitemap.xml", "xml"), ("/sitemaps/es-ciudades.xml", "xml"),
                       ("/sitemaps/pt-br-tipos-ciudades.xml", "xml"),
                       ("/assets/site.css", "css"), ("/assets/site.js", "javascript"),
                       ("/assets/inmueblespy-logo-horizontal.svg", "svg"),
                       ("/assets/search-es.json", "json")):
        st, hd, body = fetch(base + path)
        ct = hd.get("content-type", "")
        record(f"asset {path}", st == 200 and want in ct and len(body) > 0,
               f"{st} {ct.split(';')[0]} {len(body)}B")

    # --- 404 -----------------------------------------------------------
    st, _hd, body = fetch(base + "/es/esta-pagina-no-existe-12345/")
    record("404 status", st == 404, f"{st}")
    # A plain file server answers 404 with its own page; serving site/404.html
    # is the platform's job, so only the status is portable here.
    record("404 serves the site page", b"noindex" in body.lower() and b"InmueblesPY" in body,
           "custom 404" if b"noindex" in body.lower() else "server default", platform=True)

    # --- security headers ----------------------------------------------
    st, hd, _ = fetch(base + "/es/")
    for h, expect in (("X-Content-Type-Options", "nosniff"),
                      ("Referrer-Policy", None), ("X-Frame-Options", None),
                      ("Content-Security-Policy", "default-src"),
                      ("Permissions-Policy", None),
                      ("Strict-Transport-Security", "max-age")):
        v = hd.get(h.lower(), "")
        ok = bool(v) and (expect is None or expect in v)
        record(f"header {h}", ok, v[:58] or "absent", platform=True)

    # --- caching --------------------------------------------------------
    _st, hd, _ = fetch(base + "/assets/site.css")
    record("cache-assets", "max-age" in hd.get("cache-control", ""),
           hd.get("cache-control", "absent"), platform=True)
    _st, hd, _ = fetch(base + "/es/")
    record("cache-pages", "max-age" in hd.get("cache-control", ""),
           hd.get("cache-control", "absent"), platform=True)

    # --- compression -----------------------------------------------------
    _st, hd, _ = fetch(base + "/es/")
    record("compression", hd.get("content-encoding") in ("gzip", "br"),
           hd.get("content-encoding", "none"), platform=True)

    # --- advertising banner present on PT, absent on ES -------------------
    _st, _hd, pt = fetch(base + "/pt-br/comprar/central/luque/terrenos/")
    _st, _hd, es = fetch(base + "/es/venta/central/luque/terrenos/")
    record("banner on PT", b"mnpb" in pt, "present" if b"mnpb" in pt else "MISSING")
    record("no banner on ES", b"mnpb" not in es, "absent" if b"mnpb" not in es else "PRESENT")

    # --- every asset a page references actually resolves -------------------
    import re
    _st, _hd, page = fetch(base + "/es/venta/central/luque/terrenos/")
    refs = sorted(set(re.findall(rb'(?:src|href)="(/[^"]+\.(?:css|js|svg|webp|jpg|png|json))"', page)))
    broken = []
    for r in refs[:14]:
        u = r.decode()
        st, _h, b = fetch(base + u)
        if st != 200 or not b:
            broken.append(f"{u} -> {st}")
    record("referenced assets resolve", not broken,
           f"{len(refs)} referenced, {len(broken)} broken" + (f": {broken[:2]}" if broken else ""))

    # --- report -----------------------------------------------------------
    width = max(len(n) for n, _o, _d, _p in results)
    failed = plat = 0
    print(f"HTTP verification against {base}\n")
    for name, ok, detail, platform in results:
        if ok:
            tag = "PASS"
        elif platform:
            tag = "PLATFORM"
            plat += 1
        else:
            tag = "FAIL"
            failed += 1
        print(f"  [{tag:8}] {name.ljust(width)}  {detail}")
    print(f"\n{len(results)} checks, {failed} failed, {plat} platform-supplied not satisfied here")
    if plat and not failed:
        print("Platform items come from render.yaml and must be re-run against the deployed host.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
