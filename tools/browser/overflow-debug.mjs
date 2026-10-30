// Diagnostic: find the elements that actually widen the document at a given
// width, ignoring anything an ancestor clips (a wide table inside a scroll
// container is not a page overflow). Pass a URL as the first argument.
import { chromium } from 'playwright';
const b = await chromium.launch();
for (const w of [390, 1024]) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 } });
  const p = await ctx.newPage();
  await p.goto((process.env.BASE || 'http://127.0.0.1:8899') + (process.argv[2] || '/es/venta/central/luque/terrenos/'), { waitUntil: 'load' });
  const info = await p.evaluate(() => {
    const de = document.documentElement;
    const res = [];
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.right > de.clientWidth + 1.5) {
        // does an ancestor clip it?
        let clipped = false, a = el.parentElement;
        while (a && a !== document.body) {
          const s = getComputedStyle(a);
          if (/auto|scroll|hidden/.test(s.overflowX)) { clipped = true; break; }
          a = a.parentElement;
        }
        if (!clipped) res.push({ tag: el.tagName.toLowerCase(), cls: (el.className||'').toString().slice(0,40),
                                  right: Math.round(r.right), w: Math.round(r.width) });
      }
    }
    return { scrollW: de.scrollWidth, clientW: de.clientWidth, unclipped: res.slice(0, 8) };
  });
  console.log(`@${w}px scrollW=${info.scrollW} clientW=${info.clientW} unclipped=${info.unclipped.length}`);
  for (const o of info.unclipped) console.log('   ', o);
  await ctx.close();
}
await b.close();
