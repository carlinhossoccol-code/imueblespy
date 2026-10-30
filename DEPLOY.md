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

## Only then, the definitive domain

Point `inmueblespy.com.py` at the service once the temporary host passes, and
re-run `check_http.py` against it. Cloudflare sits in front of the production
domain: confirm it is not challenging Googlebot, Bingbot or OAI-SearchBot,
which cannot be verified from this repository.
