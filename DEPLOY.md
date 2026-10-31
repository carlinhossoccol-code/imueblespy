# Homologation on Render

The working tree is ready to deploy. **Nothing has been deployed from here**:
this session has no Render credentials, and publishing is your decision.

## Before deploying

```sh
python3 -I tools/serve.py 8899 &      # threaded server, required for timings
./tools/run_all.sh                     # data, pages, sitemaps, 23 checks
WITH_LIGHTHOUSE=1 ./tools/run_all.sh   # the above plus performance
```

All 23 blocking checks, 18 journeys, the environment checks and the
accessibility suite must pass before the branch is deployed.

## Deploy to the temporary environment first

`render.yaml` already declares the production domain, the root redirect and
the security headers. Deploy the branch to the Render service and let it serve
`inmueblespy.onrender.com` **before** pointing the definitive domain at it.

The temporary host serves the same files, so every page there carries a
canonical URL on `inmueblespy.com.py`. That is what keeps the preview out of
the index; it is deliberate and must not be changed to make the preview
"work".

## After deploying, verify over real HTTP

```sh
python3 -I tools/check_http.py https://inmueblespy.onrender.com
```

36 checks. Locally 25 pass and 11 report `PLATFORM`, because they depend on
what Render adds rather than on the files in this repository:

| Check | Supplied by |
| --- | --- |
| `root-redirect` | `routes:` in render.yaml — expect 301/302 to `/es/` |
| `404 serves the site page` | Render serving `site/404.html` |
| six `header …` checks | `headers:` in render.yaml |
| `cache-assets`, `cache-pages` | `Cache-Control` rules in render.yaml |
| `compression` | Render's gzip/brotli |

**All eleven must pass against the deployed host.** If any reports `FAIL`
there, the configuration did not take effect and the deployment is not
homologated.

## Then confirm by eye

```sh
BASE=https://inmueblespy.onrender.com node tools/browser/journeys.mjs
BASE=https://inmueblespy.onrender.com node tools/browser/check.mjs
```

Both read `BASE`, so the same 18 journeys and the same nine widths run against
the deployed host.

## The site root: a known platform limitation

`/` does not answer with an HTTP redirect, and on Render it cannot. Their
documentation states that Render "does not apply redirect or rewrite rules to a
path if a resource exists at that path", and that rules cannot be applied to
the domain root at all. Verified against production: both `/` and
`/index.html` answer `200` and serve the file.

What ships instead is `site/index.html`: a `noindex` stub whose canonical points
at `/es/` and which refreshes there immediately. A visitor lands on the Spanish
homepage either way; a crawler follows the canonical. It costs one extra round
trip and is a weaker signal than a `301`.

**To get a real 301**, add a Redirect Rule at Cloudflare, which already sits in
front of this domain:

| Field | Value |
| --- | --- |
| When incoming requests match | `http.request.uri.path eq "/"` |
| Then | Static redirect |
| Type | Permanent (301) |
| Target URL | `https://inmueblespy.com.py/es/` |

Leave `site/index.html` in place as the fallback. After adding the rule,
re-run `python3 -I tools/check_http.py https://inmueblespy.com.py`; the
`root-redirect` line should then read `301 -> …/es/` instead of naming the stub.

Nothing in this repository changes Cloudflare, and nothing here should: that
rule is yours to add.

## Only then, the definitive domain

Point `inmueblespy.com.py` at the service once the temporary host passes, and
re-run `check_http.py` against it. Cloudflare sits in front of the production
domain: confirm it is not challenging Googlebot, Bingbot or OAI-SearchBot,
which cannot be verified from this repository.
