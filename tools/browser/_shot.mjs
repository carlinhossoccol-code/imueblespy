import { chromium } from 'playwright';
const b = await chromium.launch();
const out = process.env.OUT;
const ctx = await b.newContext({ viewport: { width: 1280, height: 1200 } });
const p = await ctx.newPage();
await p.goto('http://127.0.0.1:8899/es/', { waitUntil: 'load' });
const secs = await p.$$('section.section');
for (const s of secs) {
  const h = await s.$eval('h2', e => e.textContent).catch(() => '');
  if (h.includes('tipo de propiedad')) { await s.screenshot({ path: `${out}/category-cards.png` }); }
}
await ctx.close();
const ctx2 = await b.newContext({ viewport: { width: 390, height: 844 } });
const p2 = await ctx2.newPage();
await p2.goto('http://127.0.0.1:8899/es/venta/central/luque/terrenos/', { waitUntil: 'load' });
const el = await p2.$('.panel:has(.catlink)') || await p2.$('.gridlist');
if (el) await el.screenshot({ path: `${out}/catlinks-mobile.png` });
await ctx2.close();
await b.close();
console.log('ok');
