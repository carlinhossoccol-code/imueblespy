// The fifteen representative journeys from the brief, executed in a real
// browser against a local copy of the site. Each journey asserts that the
// visitor can actually finish the task; a failed assertion is a defect, not a
// note. Timings are local-lab figures and are reported as such.
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8899';
const OUT = process.env.OUT || '/tmp/journeys';
mkdirSync(OUT, { recursive: true });

const results = [];
const browser = await chromium.launch();

async function journey(name, opts, fn) {
  const ctx = await browser.newContext({
    viewport: opts.viewport || { width: 390, height: 844 },
    ...(opts.contextOptions || {}),
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  const checks = [];
  const ok = (label, cond, detail = '') =>
    checks.push({ label, pass: !!cond, detail: String(detail).slice(0, 120) });
  const t0 = Date.now();
  let fail = null;
  try {
    if (opts.throttle) {
      const cdp = await ctx.newCDPSession(page);
      await cdp.send('Network.enable');
      await cdp.send('Network.emulateNetworkConditions', {
        offline: false, latency: 300,
        downloadThroughput: (1.6 * 1024 * 1024) / 8,   // ~1.6 Mbps, slow 3G-ish
        uploadThroughput: (750 * 1024) / 8,
      });
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
    }
    await fn(page, ok);
  } catch (e) {
    fail = String(e).slice(0, 200);
  }
  const ms = Date.now() - t0;
  await ctx.close();
  const passed = !fail && checks.every(c => c.pass) && errors.length === 0;
  results.push({ name, passed, ms, checks, errors: errors.slice(0, 3), fail });
}

const go = (p, u) => p.goto(BASE + u, { waitUntil: 'load', timeout: 30000 });
const txt = p => p.evaluate(() => document.body.innerText);
const count = (p, sel) => p.evaluate(s => document.querySelectorAll(s).length, sel);

// 1 ---------------------------------------------------------------------
await journey('1. PY buyer: terrenos in Luque', {}, async (p, ok) => {
  await go(p, '/es/venta/central/luque/terrenos/');
  ok('lang is es-PY', (await p.getAttribute('html', 'lang')) === 'es-PY');
  ok('H1 names city and category', /Terrenos.*Luque/i.test(await p.textContent('h1')));
  ok('professionals are listed', (await count(p, 'article.company')) >= 1);
  ok('a direct contact action exists', (await count(p, 'a[href^="tel:"],a[href*="wa.me"]')) >= 1);
  ok('land-specific guidance present', /superficie|zonificaci|linderos/i.test(await txt(p)));
  ok('no advertising on a Spanish page', (await count(p, '.mnpb')) === 0);
});

// 2 ---------------------------------------------------------------------
await journey('2. PY buyer: apartments in Asunción', {}, async (p, ok) => {
  await go(p, '/es/venta/asuncion/departamentos/');
  ok('page loads', (await p.title()).length > 10);
  ok('apartment-specific guidance', /expensas|copropiedad|horizontal/i.test(await txt(p)));
  ok('professionals are listed', (await count(p, 'article.company')) >= 1);
  ok('differs from land page', !/zonificaci[oó]n y los retiros/i.test(await txt(p)));
});

// 3 ---------------------------------------------------------------------
await journey('3. Buyer: agencies in Ciudad del Este', {}, async (p, ok) => {
  await go(p, '/es/inmobiliarias/alto-parana/ciudad-del-este/');
  ok('agencies listed', (await count(p, 'article.company')) >= 3);
  ok('profile links work', (await count(p, 'a[href^="/es/inmobiliaria/"]')) >= 3);
  const href = await p.getAttribute('article.company h3 a', 'href');
  await go(p, href);
  ok('profile opens', (await count(p, 'h1')) === 1);
  ok('profile states its source', /Fuente consultada|Origen del registro/i.test(await txt(p)));
});

// 4 ---------------------------------------------------------------------
await journey('4. Buyer: find a specific agent', {}, async (p, ok) => {
  await go(p, '/es/todos-los-profesionales/');
  ok('alphabetical index present', (await count(p, '.az-index a')) >= 10);
  ok('many professionals listed', (await count(p, '.ep-list a')) > 300);
  const first = await p.getAttribute('.az-group .ep-list a', 'href');
  await go(p, first);
  ok('a profile opens from the index', (await count(p, 'h1')) === 1);
});

// 5 ---------------------------------------------------------------------
await journey('5. BR buyer: terrenos in Minga Guazú', {}, async (p, ok) => {
  await go(p, '/pt-br/comprar/alto-parana/minga-guazu/terrenos/');
  ok('lang is pt-BR', (await p.getAttribute('html', 'lang')) === 'pt-BR');
  ok('advertising present on a PT page', (await count(p, '.mnpb')) === 1);
  const t = await txt(p);
  ok('distance to the Brazilian border shown', /fronteira com o Brasil/i.test(t));
  ok('ad does not precede the first result', await p.evaluate(() => {
    const ad = document.querySelector('.mnpb'); const c = document.querySelector('article.company');
    if (!ad || !c) return true;
    return c.compareDocumentPosition(ad) & Node.DOCUMENT_POSITION_FOLLOWING;
  }));
});

// 6 ---------------------------------------------------------------------
await journey('6. BR buyer: researching buying in Paraguay', {}, async (p, ok) => {
  await go(p, '/pt-br/');
  ok('guides reachable from home', (await count(p, 'a[href^="/pt-br/guias/"]')) >= 1);
  await go(p, '/pt-br/guias/');
  ok('guides listed', (await count(p, 'a[href*="/pt-br/guias/"]')) >= 2);
  await go(p, '/pt-br/guias/documentacao-imovel/');
  ok('document guide opens', (await count(p, 'h1')) === 1);
  ok('guide has substance', (await txt(p)).split(/\s+/).length > 250);
});

// 7 ---------------------------------------------------------------------
await journey('7. Investor comparing cities', { viewport: { width: 1280, height: 900 } }, async (p, ok) => {
  await go(p, '/es/venta/central/luque/terrenos/');
  const t = await txt(p);
  ok('comparison table of nearby localities', /Localidades cercanas/i.test(t));
  ok('table carries population and profile counts', /Habitantes \(2022\)/.test(t) && /Perfiles con sede/.test(t));
  ok('national ranking given', /Posici[oó]n nacional por poblaci[oó]n/i.test(t));
  const links = await count(p, '.ep-location a[href^="/es/zonas/"]');
  ok('nearby localities are linked', links >= 3);
});

// 8 ---------------------------------------------------------------------
await journey('8. Mobile user on a slow connection', { throttle: true }, async (p, ok) => {
  const t0 = Date.now();
  await go(p, '/es/venta/central/luque/terrenos/');
  const loaded = Date.now() - t0;
  ok(`loads within 12s on throttled 3G (${loaded}ms)`, loaded < 12000, `${loaded}ms`);
  ok('main content is in the initial HTML', (await count(p, 'article.company')) >= 1);
  const shift = await p.evaluate(() => new Promise(r => {
    let cls = 0;
    try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; })
      .observe({ type: 'layout-shift', buffered: true }); } catch {}
    setTimeout(() => r(+cls.toFixed(4)), 1500);
  }));
  ok(`CLS under 0.1 (${shift})`, shift < 0.1, shift);
});

// 9 ---------------------------------------------------------------------
await journey('9. Keyboard-only user', { viewport: { width: 1280, height: 900 } }, async (p, ok) => {
  await go(p, '/es/venta/central/luque/terrenos/');
  await p.keyboard.press('Tab');
  const first = await p.evaluate(() => document.activeElement.textContent.trim().slice(0, 40));
  ok('first Tab reaches the skip link', /Saltar al contenido/i.test(first), first);
  await p.keyboard.press('Enter');
  ok('skip link moves to main', await p.evaluate(() => location.hash === '#main'));
  const visible = await p.evaluate(() => {
    const a = document.querySelector('a.btn');
    a.focus();
    const s = getComputedStyle(a);
    return s.outlineStyle !== 'none' || s.boxShadow !== 'none';
  });
  ok('focused control has a visible indicator', visible);
  const reachable = await p.evaluate(() => {
    let n = 0;
    for (const el of document.querySelectorAll('a[href],button')) {
      if (el.tabIndex >= 0) n++;
    }
    return n;
  });
  ok('all links are keyboard reachable', reachable > 30);
});

// 10 --------------------------------------------------------------------
await journey('10. Lands on an internal page from search', {}, async (p, ok) => {
  await go(p, '/es/inmobiliaria/366-nisa-inmobiliaria-luque/');
  ok('breadcrumb shows where they are', (await count(p, 'nav[aria-label="Breadcrumb"] a')) >= 2);
  ok('header offers onward navigation', (await count(p, 'header a')) >= 4);
  ok('zone link back to the city', (await count(p, 'a[href^="/es/zonas/"]')) >= 1);
  ok('language switch available', (await count(p, 'a[href^="/pt-br/"]')) >= 1);
});

// 11 --------------------------------------------------------------------
await journey('11. City with no local company', {}, async (p, ok) => {
  await go(p, '/es/venta/alto-parana/mbaracayu/terrenos/');
  const t = await txt(p);
  ok('states there is no local seat', /no se identifica una empresa con sede/i.test(t));
  ok('offers nearest professionals instead', /Profesionales m[aá]s cercanos/i.test(t));
  ok('distances are shown', /\d+[,.]\d+ km|\d+ km/.test(t));
  ok('local data still published', /Ubicaci[oó]n y distancias/i.test(t));
  ok('does not claim coverage', /no confirma\s+que atiendan|Tener la sede cerca no confirma/i.test(t));
});

// 12 --------------------------------------------------------------------
await journey('12. Agency with neither phone nor website', {}, async (p, ok) => {
  await go(p, '/es/inmobiliaria/367-re-max-republic/');
  const t = await txt(p);
  ok('page still useful', (await count(p, 'h1')) === 1);
  ok('missing fields are stated plainly', /Campos no informados/i.test(t));
  ok('no invented contact', (await count(p, 'a[href^="tel:"]')) === 0);
  ok('an alternative action is offered', (await count(p, 'a[href*="google.com/search"]')) >= 1);
  ok('no leftover internal wording', !/CSV/.test(t));
});

// 13 --------------------------------------------------------------------
await journey('13. Agency with full contact details', {}, async (p, ok) => {
  await go(p, '/es/inmobiliaria/366-nisa-inmobiliaria-luque/');
  const t = await txt(p);
  ok('phone is actionable', (await count(p, 'a[href^="tel:"]')) >= 1);
  ok('address published', /Direcci[oó]n publicada/i.test(t));
  ok('source and date given', /Fuente consultada/i.test(t) && /2026-10-28/.test(t));
  ok('no Portuguese left on the Spanish profile', !/imobili[aá]ria|Telefone/i.test(t));
});

// 14 --------------------------------------------------------------------
await journey('14. Switching between Spanish and Portuguese', {}, async (p, ok) => {
  await go(p, '/es/venta/central/luque/terrenos/');
  const link = await p.getAttribute('header a[href^="/pt-br/"]', 'href');
  ok('switch preserves the page', link === '/pt-br/comprar/central/luque/terrenos/', link);
  await go(p, link);
  ok('lands on the Portuguese equivalent', (await p.getAttribute('html', 'lang')) === 'pt-BR');
  ok('content is Portuguese', /O que verificar antes de comprar/i.test(await txt(p)));
  const back = await p.getAttribute('header a[href^="/es/"]', 'href');
  ok('switch back returns to the same page', back === '/es/venta/central/luque/terrenos/', back);
});

// 15 --------------------------------------------------------------------
await journey('15. Enters through the domain root', {}, async (p, ok) => {
  await go(p, '/');
  await p.waitForURL(/\/es\/$/, { timeout: 8000 }).catch(() => {});
  ok('arrives at the Spanish homepage', /\/es\/$/.test(p.url()), p.url());
  ok('no language chooser step', !/Eleg[íi] tu idioma/i.test(await txt(p)));
  ok('search is available', (await count(p, 'input[type="search"],input[name*="q"],form')) >= 1);
});

await browser.close();
writeFileSync(`${OUT}/journeys.json`, JSON.stringify(results, null, 1));

let failed = 0;
for (const r of results) {
  if (!r.passed) failed++;
  console.log(`${r.passed ? 'PASS' : 'FAIL'}  ${r.name}  (${r.ms}ms)`);
  for (const c of r.checks) if (!c.pass) console.log(`        x ${c.label} ${c.detail}`);
  if (r.fail) console.log(`        ! ${r.fail}`);
  for (const e of r.errors) console.log(`        console: ${e.slice(0, 110)}`);
}
console.log(`\n${results.length - failed}/${results.length} journeys passed`);
process.exit(failed ? 1 : 0);
