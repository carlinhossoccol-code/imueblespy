// Accessibility checks that need a real browser: WCAG 1.4.10 reflow at zoom,
// 1.4.3 contrast on rendered text, 2.3.3 reduced motion, and 2.4.7 focus
// visibility on every interactive control.
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'node:fs';

const BASE = process.env.BASE || 'http://127.0.0.1:8899';
const OUT = process.env.OUT || '/tmp/a11y';
mkdirSync(OUT, { recursive: true });

const PAGES = [
  ['home-es', '/es/'],
  ['category', '/es/venta/central/luque/terrenos/'],
  ['thin-city', '/es/venta/alto-parana/mbaracayu/terrenos/'],
  ['profile', '/es/inmobiliaria/366-nisa-inmobiliaria-luque/'],
  ['all-prof', '/es/todos-los-profesionales/'],
  ['city', '/es/zonas/central/luque/'],
  ['home-pt', '/pt-br/'],
  ['category-pt', '/pt-br/comprar/central/luque/terrenos/'],
];

const browser = await chromium.launch();
const findings = [];
const notes = [];
const push = (page, kind, detail) => findings.push({ page, kind, detail });

// -- 1.4.10 Reflow: 320 CSS px is 400% zoom of 1280; 640 is 200% ------------
for (const [name, path] of PAGES) {
  for (const [w, label] of [[640, '200% zoom'], [320, '400% zoom']]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 800 } });
    const p = await ctx.newPage();
    await p.goto(BASE + path, { waitUntil: 'load' });
    const r = await p.evaluate(() => {
      const de = document.documentElement;
      const bad = [];
      for (const el of document.querySelectorAll('body *')) {
        const b = el.getBoundingClientRect();
        if (b.right > de.clientWidth + 1.5) {
          let a = el.parentElement, clipped = false;
          while (a && a !== document.body) {
            if (/auto|scroll|hidden/.test(getComputedStyle(a).overflowX)) { clipped = true; break; }
            a = a.parentElement;
          }
          if (!clipped) bad.push(el.tagName.toLowerCase() + '.' + (el.className || '').toString().slice(0, 30));
        }
      }
      return { over: de.scrollWidth > de.clientWidth + 1, offenders: bad.slice(0, 3) };
    });
    if (r.over) push(name, `reflow ${label} (${w}px)`, r.offenders.join(', ') || 'document wider than viewport');
    await ctx.close();
  }
}

// -- 1.4.3 Contrast --------------------------------------------------------
for (const [name, path] of PAGES) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(BASE + path, { waitUntil: 'load' });
  const low = await p.evaluate(() => {
    const lum = c => {
      const [r, g, b] = c.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const parse = s => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    // Returns null when any ancestor paints a gradient or image: the text then
    // sits on pixels this cannot sample, and guessing produced false failures
    // on the advertising panel, where white text on dark green scored 1.05:1.
    const bgOf = el => {
      let a = el;
      while (a) {
        const s = getComputedStyle(a);
        if (s.backgroundImage && s.backgroundImage !== 'none') return null;
        const c = s.backgroundColor;
        if (c && !/rgba\(0, 0, 0, 0\)|transparent/.test(c)) return parse(c);
        a = a.parentElement;
      }
      return [255, 255, 255];
    };
    const out = [], unchecked = [];
    for (const el of document.querySelectorAll('body *')) {
      if (!el.childNodes.length) continue;
      const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
      if (!hasText) continue;
      const s = getComputedStyle(el);
      if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity === 0) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      const fs = parseFloat(s.fontSize), bold = +s.fontWeight >= 700;
      const large = fs >= 24 || (fs >= 18.66 && bold);
      const need = large ? 3 : 4.5;
      const bg = bgOf(el);
      if (!bg) { unchecked.push(el.tagName.toLowerCase()); continue; }
      const L1 = lum(parse(s.color)), L2 = lum(bg);
      const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      if (ratio < need - 0.01) {
        out.push({ tag: el.tagName.toLowerCase(), cls: (el.className || '').toString().slice(0, 28),
                   ratio: +ratio.toFixed(2), need, fs: Math.round(fs),
                   text: el.textContent.trim().slice(0, 32) });
      }
    }
    const seen = new Set();
    const uniq = out.filter(o => { const k = o.tag + o.cls + o.ratio; if (seen.has(k)) return false; seen.add(k); return true; });
    return { uniq, unchecked: unchecked.length };
  });
  for (const o of low.uniq) push(name, 'contrast', `${o.tag}.${o.cls} ${o.ratio}:1 (needs ${o.need}) "${o.text}"`);
  if (low.unchecked) notes.push(`${name}: ${low.unchecked} text node(s) sit on a gradient or image and need a manual contrast check`);
  await ctx.close();
}

// -- 2.3.3 Reduced motion --------------------------------------------------
{
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  const p = await ctx.newPage();
  await p.goto(BASE + '/pt-br/comprar/central/luque/terrenos/', { waitUntil: 'load' });
  const moving = await p.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll('body *')) {
      const s = getComputedStyle(el);
      if (s.animationName !== 'none' && parseFloat(s.animationDuration) > 0) {
        out.push((el.className || el.tagName).toString().slice(0, 36) + ' -> ' + s.animationName);
      }
    }
    return out.slice(0, 6);
  });
  for (const m of moving) push('category-pt', 'animation runs under prefers-reduced-motion', m);
  await ctx.close();
}

// -- 2.4.7 Focus visible ---------------------------------------------------
for (const [name, path] of PAGES.slice(0, 4)) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(BASE + path, { waitUntil: 'load' });
  const invisible = await p.evaluate(() => {
    const bad = [];
    const els = [...document.querySelectorAll('a[href],button,input,select,textarea')].slice(0, 120);
    for (const el of els) {
      const before = getComputedStyle(el);
      const b = { o: before.outlineStyle, w: before.outlineWidth, s: before.boxShadow, bg: before.backgroundColor };
      el.focus();
      const a = getComputedStyle(el);
      const changed = a.outlineStyle !== b.o || a.outlineWidth !== b.w ||
                      a.boxShadow !== b.s || a.backgroundColor !== b.bg;
      if (!changed && document.activeElement === el) {
        bad.push((el.tagName + '.' + (el.className || '')).slice(0, 40) + ' "' + el.textContent.trim().slice(0, 20) + '"');
      }
    }
    return bad.slice(0, 5);
  });
  for (const b of invisible) push(name, 'no visible focus indicator', b);
  await ctx.close();
}

await browser.close();
writeFileSync(`${OUT}/a11y.json`, JSON.stringify(findings, null, 1));

const byKind = {};
for (const f of findings) (byKind[f.kind] ||= []).push(f);
console.log('=== ACCESSIBILITY (real browser) ===');
for (const n of notes) console.log('  note:', n);
if (!findings.length) console.log('  no findings across', PAGES.length, 'pages');
for (const [k, v] of Object.entries(byKind)) {
  console.log(`\n  ${k}: ${v.length}`);
  for (const f of v.slice(0, 6)) console.log(`     ${f.page.padEnd(12)} ${f.detail}`);
  if (v.length > 6) console.log(`     ... ${v.length - 6} more`);
}
process.exit(findings.length ? 1 : 0);
