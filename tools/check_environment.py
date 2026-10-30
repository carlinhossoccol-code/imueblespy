#!/usr/bin/env python3
"""Verify what the static host will actually publish and send.

Render serves site/ as-is, so anything in that directory is public. These
checks look for files that should never ship, headers that must be present,
and external references that the Content-Security-Policy would silently block.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import corpus as C  # noqa: E402

ROOT = C.ROOT
problems: list[str] = []
notes: list[str] = []


def fail(msg):
    problems.append(msg)


def ok(msg):
    notes.append(msg)


# --------------------------------------------------------------- publishable
JUNK = re.compile(r"(^|/)(\.DS_Store|Thumbs\.db|\.git|\.env|.*\.bak|.*\.orig|.*~|.*\.swp)$")
SOURCEMAP = re.compile(r"\.map$")
published = []
for dirpath, dirnames, files in os.walk(C.SITE):
    for f in files:
        rel = os.path.relpath(os.path.join(dirpath, f), C.SITE).replace(os.sep, "/")
        published.append(rel)
        if JUNK.search("/" + rel):
            fail(f"site/{rel} would be published but should not be")
        if SOURCEMAP.search(rel):
            fail(f"site/{rel} exposes a source map")
ok(f"{len(published)} files publishable under site/")

# secrets that must never appear in a published file
SECRET = re.compile(
    r"(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|"
    r"(?:api[_-]?key|secret|passwd|password|bearer)\s*[:=]\s*['\"][^'\"]{8,})", re.I)
for rel in published:
    if not rel.endswith((".html", ".js", ".css", ".json", ".txt", ".xml", ".webmanifest")):
        continue
    try:
        body = C.read(os.path.join(C.SITE, rel))
    except (UnicodeDecodeError, OSError):
        continue
    m = SECRET.search(body)
    if m:
        fail(f"site/{rel} contains something that looks like a credential: {m.group(0)[:30]}")
ok("no credential-shaped strings in published text files")

# ------------------------------------------------------------------- headers
render = C.read(os.path.join(ROOT, "render.yaml"))
REQUIRED = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": None,
    "X-Frame-Options": None,
    "Content-Security-Policy": None,
    "Permissions-Policy": None,
}
for name, value in REQUIRED.items():
    if f"name: {name}" not in render:
        fail(f"render.yaml does not set {name}")
    elif value and value not in render:
        fail(f"render.yaml sets {name} but not to {value}")
if "name: Strict-Transport-Security" not in render:
    fail("render.yaml does not set Strict-Transport-Security")
if "type: redirect" not in render:
    fail("render.yaml has no redirect route for the site root")
ok("security headers declared in render.yaml")

# --------------------------------------------------------- CSP compatibility
csp = re.search(r'value:\s*"(default-src[^"]*)"', render)
if not csp:
    fail("Content-Security-Policy value could not be parsed from render.yaml")
else:
    policy = csp.group(1)
    img_allow = re.search(r"img-src ([^;]*)", policy)
    allowed_hosts = set(re.findall(r"https://[^\s;]+", img_allow.group(1) if img_allow else ""))
    inline_js = inline_css = 0
    external = set()
    for rel in published:
        if not rel.endswith(".html"):
            continue
        body = C.read(os.path.join(C.SITE, rel))
        for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", body, re.S):
            if "application/ld+json" in m.group(1):
                continue
            if "src=" not in m.group(1) and m.group(2).strip():
                inline_js += 1
        inline_css += len(re.findall(r"\sstyle=\"", body))
        # Only elements that actually fetch something count. A <link> with
        # rel=canonical or rel=alternate declares a relationship; it loads
        # nothing and the CSP does not apply to it.
        for m in re.finditer(r'<(?:img|script|source)\b[^>]*?\s(?:src|srcset)="(https?://[^"]+)"', body):
            external.add(re.match(r'https?://[^/]+', m.group(1)).group(0))
        for m in re.finditer(r'<link\b([^>]*)>', body):
            attrs = m.group(1)
            rel = re.search(r'rel="([^"]*)"', attrs)
            href = re.search(r'href="(https?://[^"]+)"', attrs)
            if not rel or not href:
                continue
            loading = {'stylesheet', 'icon', 'preload', 'manifest', 'apple-touch-icon'}
            if loading & set(rel.group(1).split()):
                external.add(re.match(r'https?://[^/]+', href.group(1)).group(0))
    if inline_js:
        fail(f"{inline_js} inline script block(s) would be blocked by script-src 'self'")
    if inline_css:
        fail(f"{inline_css} inline style attribute(s) present; style-src 'self' blocks them")
    blocked = {h for h in external if h not in allowed_hosts}
    for h in sorted(blocked):
        fail(f"{h} is loaded as a subresource but not allowed by the CSP")
    ok(f"no inline scripts or styles; subresource hosts allowed: {sorted(allowed_hosts) or 'self only'}")

# ----------------------------------------------------------------- 404 page
p404 = os.path.join(C.SITE, "404.html")
if not os.path.exists(p404):
    fail("site/404.html is missing")
else:
    body = C.read(p404)
    if "noindex" not in body:
        fail("404.html is not marked noindex")
    if not re.search(r'href="/(es|pt-br)/"', body):
        fail("404.html offers no way back into the site")
    ok("404 page present, noindex, with a route back")

# ------------------------------------------------------- robots and sitemaps
for f in ("robots.txt", "sitemap.xml", "llms.txt"):
    if not os.path.exists(os.path.join(C.SITE, f)):
        fail(f"site/{f} is missing")
ok("robots.txt, sitemap.xml and llms.txt are present")

# --------------------------------------------------------------- mixed content
for rel in published:
    if not rel.endswith(".html"):
        continue
    body = C.read(os.path.join(C.SITE, rel))
    for m in re.finditer(r'(?:src|href)="(http://[^"]+)"', body):
        fail(f"site/{rel} references insecure {m.group(1)[:60]}")
ok("no http:// subresources")

# ------------------------------------------------------------------- report
print("ENVIRONMENT CHECKS")
for n in notes:
    print("  ok   ", n)
if problems:
    print(f"\n{len(problems)} problem(s):")
    for p in problems:
        print("  FAIL ", p)
    sys.exit(1)
print("\nall environment checks passed")
