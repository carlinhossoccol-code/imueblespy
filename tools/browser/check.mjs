// Real-browser checks against a locally served copy of site/.
// Measurements are local-lab figures on a desktop machine over loopback; they
// are useful for catching layout and interaction defects, and must not be
// presented as field data or as Lighthouse scores.
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8899';
const OUT = process.env.OUT || '/tmp/shots';
const WIDTHS = [320, 360, 390, 430, 768, 1024, 1280, 1440, 1920];
const SHOT_WIDTHS = new Set([360, 768, 1280]);

const PAGES = [
  ['home-es', '/es/'],
  ['home-pt', '/pt-br/'],
  ['cat-terrenos-es', '/es/venta/central/luque/terrenos/'],
  ['cat-terrenos-pt', '/pt-br/comprar/central/luque/terrenos/'],
  ['city-es', '/es/zonas/central/luque/'],
  ['agency-es', '/es/inmobiliaria/366-nisa-inmobiliaria-luque/'],
  ['agency-nocontact-es', '/es/inmobiliaria/367-re-max-republic/'],
  ['dir-city-es', '/es/inmobiliarias/'],
  ['all-prof-es', '/es/todos-los-profesionales/'],
  ['thin-city-es', '/es/venta/alto-parana/mbaracayu/terrenos/'],
  ['guides-pt', '/pt-br/guias/'],
  ['root', '/'],
];

const results = { overflow: [], a11y: [], metrics: [], interaction: [], errors: [] };

const browser = await chromium.launch();
mkdirSync(OUT, { recursive: true });

// ---------------------------------------------------------------- overflow
for (const [name, path] of PAGES) {
  for (const w of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const consoleErrors = [];
    page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
    page.on('pageerror', e => consoleErrors.push(String(e)));
    try {
      await page.goto(BASE + path, { waitUntil: 'load', timeout: 20000 });
      const info = await page.evaluate(() => {
        const de = document.documentElement;
        const over = [];
        for (const el of document.querySelectorAll('body *')) {
          const r = el.getBoundingClientRect();
          if (r.width === 0 && r.height === 0) continue;
          if (r.right > de.clientWidth + 1.5 || r.left < -1.5) {
            over.push({
              tag: el.tagName.toLowerCase(),
              cls: (el.className || '').toString().slice(0, 48),
              left: Math.round(r.left), right: Math.round(r.right),
            });
          }
        }
        return {
          scrollW: de.scrollWidth, clientW: de.clientWidth,
          offenders: over.slice(0, 5), count: over.length,
        };
      });
      if (info.scrollW > info.clientW + 1) {
        results.overflow.push({ name, path, w, ...info });
      }
      if (consoleErrors.length) results.errors.push({ name, w, errors: consoleErrors.slice(0, 3) });
      if (SHOT_WIDTHS.has(w)) {
        await page.screenshot({ path: `${OUT}/${name}-${w}.png`, fullPage: false });
      }
    } catch (e) {
      results.errors.push({ name, path, w, errors: [String(e).slice(0, 160)] });
    }
    await ctx.close();
  }
}

// ------------------------------------------------- a11y + metrics + interaction
for (const [name, path] of PAGES) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  try {
    await page.goto(BASE + path, { waitUntil: 'load', timeout: 20000 });

    const a = await page.evaluate(() => {
      const q = s => Array.from(document.querySelectorAll(s));
      const focusables = q('a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])');
      const smallTargets = focusables.filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && (r.height < 24 || r.width < 24);
      }).map(el => ({ tag: el.tagName.toLowerCase(), text: (el.textContent || '').trim().slice(0, 30),
                      h: Math.round(el.getBoundingClientRect().height),
                      w: Math.round(el.getBoundingClientRect().width) }));
      return {
        lang: document.documentElement.lang,
        h1: q('h1').length,
        main: q('main').length,
        skipLink: !!document.querySelector('a[href="#main"],a[href^="#main"]'),
        landmarks: { header: q('header').length, nav: q('nav').length, footer: q('footer').length },
        imgNoAlt: q('img:not([alt])').length,
        emptyLinks: q('a[href]').filter(l => !l.textContent.trim() && !l.getAttribute('aria-label') && !l.querySelector('img[alt]:not([alt=""])')).length,
        smallTargets: smallTargets.slice(0, 6),
        smallTargetCount: smallTargets.length,
        langSwitch: q('a[href]').filter(l => /\/(es|pt-br)\//.test(l.getAttribute('href') || '') &&
                     /PT-BR|ES|Espa|Portug/i.test(l.textContent || '')).map(l => l.getAttribute('href'))[0] || null,
      };
    });
    results.a11y.push({ name, path, ...a });

    const m = await page.evaluate(() => new Promise(res => {
      let lcp = 0, cls = 0;
      try {
        new PerformanceObserver(l => { for (const e of l.getEntries()) lcp = Math.max(lcp, e.startTime); })
          .observe({ type: 'largest-contentful-paint', buffered: true });
        new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; })
          .observe({ type: 'layout-shift', buffered: true });
      } catch {}
      setTimeout(() => {
        const nav = performance.getEntriesByType('navigation')[0] || {};
        const fcp = (performance.getEntriesByName('first-contentful-paint')[0] || {}).startTime || 0;
        res({ lcp: Math.round(lcp), cls: +cls.toFixed(4), fcp: Math.round(fcp),
              domContentLoaded: Math.round(nav.domContentLoadedEventEnd || 0),
              transferKB: Math.round((nav.transferSize || 0) / 1024),
              resources: performance.getEntriesByType('resource').length });
      }, 1800);
    }));
    results.metrics.push({ name, path, ...m });

    // keyboard: first Tab should reach a visibly focused element
    const kb = await page.evaluate(async () => {
      const el = document.querySelector('a[href],button');
      if (!el) return { ok: false, why: 'no focusable element' };
      el.focus();
      const s = getComputedStyle(el, ':focus-visible');
      return { ok: document.activeElement === el, outline: s.outlineStyle || null,
               tag: el.tagName.toLowerCase(), text: (el.textContent || '').trim().slice(0, 40) };
    });
    results.interaction.push({ name, path, keyboard: kb });
  } catch (e) {
    results.errors.push({ name, path, phase: 'a11y', errors: [String(e).slice(0, 160)] });
  }
  await ctx.close();
}

// ----------------------------------------------------- mobile menu + lang swap
{
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  await page.goto(BASE + '/es/venta/central/luque/terrenos/', { waitUntil: 'load' });
  const menu = await page.evaluate(() => {
    const btn = document.querySelector('[aria-controls="main-menu"],.navtoggle,button[aria-expanded]');
    if (!btn) return { found: false };
    const m = document.getElementById('main-menu');
    const before = m ? getComputedStyle(m).display : null;
    btn.click();
    const after = m ? getComputedStyle(m).display : null;
    return { found: true, expandedAttr: btn.getAttribute('aria-expanded'), before, after,
             changed: before !== after };
  });
  const swap = await page.evaluate(() => {
    const l = Array.from(document.querySelectorAll('a[href]'))
      .find(a => /PT-BR|Portugu/i.test(a.textContent || ''));
    return l ? l.getAttribute('href') : null;
  });
  results.interaction.push({ name: 'mobile-menu', menu, langSwapHref: swap });
  await ctx.close();
}

await browser.close();
writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 1));

// ----------------------------------------------------------------- summary
console.log('=== HORIZONTAL OVERFLOW ===');
if (!results.overflow.length) console.log('  none across', PAGES.length, 'pages x', WIDTHS.length, 'widths');
for (const o of results.overflow) {
  console.log(`  ${o.name} @${o.w}px  scrollW=${o.scrollW} clientW=${o.clientW} offenders=${o.count}`);
  for (const f of o.offenders) console.log(`      ${f.tag}.${f.cls} left=${f.left} right=${f.right}`);
}
console.log('\n=== A11Y / STRUCTURE (390px) ===');
for (const a of results.a11y) {
  const flags = [];
  if (a.h1 !== 1) flags.push(`h1=${a.h1}`);
  if (!a.skipLink) flags.push('no-skip-link');
  if (a.imgNoAlt) flags.push(`imgNoAlt=${a.imgNoAlt}`);
  if (a.emptyLinks) flags.push(`emptyLinks=${a.emptyLinks}`);
  if (a.smallTargetCount) flags.push(`smallTargets=${a.smallTargetCount}`);
  console.log(`  ${a.name.padEnd(20)} lang=${String(a.lang).padEnd(6)} ${flags.length ? 'FLAGS: ' + flags.join(' ') : 'ok'}`);
  for (const t of (a.smallTargets || [])) console.log(`      small: <${t.tag}> ${t.w}x${t.h} "${t.text}"`);
}
console.log('\n=== LOCAL-LAB METRICS (390px, loopback, desktop CPU) ===');
console.log('  page                 LCP     CLS     FCP   DOMCL  res');
for (const m of results.metrics) {
  console.log(`  ${m.name.padEnd(20)} ${String(m.lcp).padStart(5)}ms ${String(m.cls).padStart(6)} ${String(m.fcp).padStart(5)}ms ${String(m.domContentLoaded).padStart(5)}ms ${String(m.resources).padStart(4)}`);
}
console.log('\n=== INTERACTION ===');
for (const i of results.interaction) console.log('  ' + JSON.stringify(i));
console.log('\n=== CONSOLE / PAGE ERRORS ===');
if (!results.errors.length) console.log('  none');
for (const e of results.errors.slice(0, 10)) console.log('  ' + JSON.stringify(e));
