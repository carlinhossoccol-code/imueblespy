// Lighthouse against a local copy of the site, mobile and desktop.
// Start the server first: python3 -I tools/serve.py 8899
// These are lab measurements on loopback. They are not field data and must not
// be reported as Core Web Vitals from real users.
import { execFileSync } from 'node:child_process';
import { readFileSync, mkdirSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8899';
const OUT = process.env.OUT || '/tmp/lh-out';
const LH = process.env.LH_DIR || '/private/tmp/claude-501/lh';
mkdirSync(OUT, { recursive: true });

const PAGES = [
  ['home-es', '/es/'],
  ['category', '/es/venta/central/luque/terrenos/'],
  ['thin-city', '/es/venta/alto-parana/mbaracayu/terrenos/'],
  ['profile', '/es/inmobiliaria/366-nisa-inmobiliaria-luque/'],
  ['home-pt', '/pt-br/'],
  ['all-prof', '/es/todos-los-profesionales/'],
  ['directory', '/es/inmobiliarias/asuncion/'],
];

const rows = [];
for (const [name, path] of PAGES) {
  for (const preset of ['mobile', 'desktop']) {
    const json = `${OUT}/${name}-${preset}.json`;
    try {
      execFileSync('npx', ['--no-install', 'lighthouse', BASE + path, '--quiet',
        '--output=json', `--output-path=${json}`,
        ...(preset === 'desktop' ? ['--preset=desktop'] : []),
        '--only-categories=performance,accessibility,best-practices,seo',
        '--chrome-flags=--headless=new --no-sandbox'],
        { cwd: LH, stdio: ['ignore', 'ignore', 'pipe'], timeout: 180000 });
      const r = JSON.parse(readFileSync(json, 'utf8'));
      const c = r.categories, a = r.audits;
      rows.push({ name, preset,
        perf: Math.round(c.performance.score * 100),
        a11y: Math.round(c.accessibility.score * 100),
        bp: Math.round(c['best-practices'].score * 100),
        seo: Math.round(c.seo.score * 100),
        lcp: a['largest-contentful-paint'].displayValue,
        cls: a['cumulative-layout-shift'].displayValue,
        tbt: a['total-blocking-time'].displayValue,
        lat: a['network-server-latency']?.displayValue ?? '-' });
    } catch (e) {
      rows.push({ name, preset, error: String(e).slice(0, 100) });
    }
  }
}
console.log('page          preset   perf a11y  bp  seo   LCP      CLS    TBT      srv-latency');
let worst = 100;
for (const r of rows) {
  if (r.error) { console.log(`${r.name.padEnd(13)} ${r.preset.padEnd(8)} ERROR ${r.error}`); continue; }
  worst = Math.min(worst, r.perf, r.a11y, r.bp, r.seo);
  console.log(`${r.name.padEnd(13)} ${r.preset.padEnd(8)} ${String(r.perf).padStart(4)} ${String(r.a11y).padStart(4)} ${String(r.bp).padStart(3)} ${String(r.seo).padStart(4)}   ${r.lcp.padEnd(8)} ${r.cls.padEnd(6)} ${r.tbt.padEnd(8)} ${r.lat}`);
}
console.log(`\nlowest category score: ${worst}`);
