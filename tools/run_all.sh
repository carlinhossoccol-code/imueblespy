#!/usr/bin/env bash
# Full pipeline in the only order that is correct: data -> pages -> sitemaps ->
# checks. Running the audit before rebuilding sitemaps reports every edited page
# as having a stale lastmod, which is the check doing its job, not a defect.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== validate data =="      && python3 -I tools/validate_data.py
echo "== apply codemods =="     && python3 -I tools/apply_codemods.py | tail -3
echo "== build sitemaps =="     && python3 -I tools/build_sitemaps.py | head -3
echo "== static audit =="       && python3 -I tools/audit.py | tail -26
echo "== environment =="        && python3 -I tools/check_environment.py | tail -2

if [ "${WITH_BROWSER:-1}" = "1" ]; then
  if curl -fsS -o /dev/null "http://127.0.0.1:8899/es/" 2>/dev/null; then
    echo "== journeys =="       && node tools/browser/journeys.mjs | tail -3
    echo "== responsiveness ==" && node tools/browser/check.mjs | sed -n '1,3p'
    echo "== accessibility =="  && node tools/browser/a11y.mjs | tail -3
    if [ "${WITH_LIGHTHOUSE:-0}" = "1" ]; then
      echo "== lighthouse ==" && node tools/browser/lighthouse.mjs | tail -3
    fi
  else
    echo "== browser checks skipped: start 'python3 -I tools/serve.py 8899' =="
  fi
fi
