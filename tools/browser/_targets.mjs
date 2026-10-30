import { chromium } from 'playwright';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport:{width:390,height:844} });
const p = await ctx.newPage();
const tally = {};
for (const path of ['/es/','/es/venta/central/luque/terrenos/','/es/zonas/central/luque/','/es/inmobiliaria/366-nisa-inmobiliaria-luque/','/es/inmobiliarias/','/es/todos-los-profesionales/','/pt-br/guias/']) {
  await p.goto('http://127.0.0.1:8899'+path,{waitUntil:'load'});
  const out = await p.evaluate(() => {
    const path = el => {
      const parts=[];
      while (el && el.tagName && parts.length<4) {
        let s = el.tagName.toLowerCase();
        const c = (el.className||'').toString().trim().split(/\s+/).filter(Boolean)[0];
        if (c) s += '.'+c;
        parts.unshift(s); el = el.parentElement;
      }
      return parts.join(' > ');
    };
    const res={};
    for (const el of document.querySelectorAll('a[href],button')) {
      const r=el.getBoundingClientRect();
      if (r.width===0&&r.height===0) continue;
      if (r.height<24||r.width<24) {
        if (r.width<=2 && r.height<=2) continue; // visually-hidden skip link
        const k=path(el);
        res[k]=res[k]||{n:0,h:Math.round(r.height),w:Math.round(r.width)};
        res[k].n++;
      }
    }
    return res;
  });
  for (const [k,v] of Object.entries(out)) {
    tally[k]=tally[k]||{n:0,h:v.h};
    tally[k].n+=v.n;
  }
}
await b.close();
for (const [k,v] of Object.entries(tally).sort((a,b)=>b[1].n-a[1].n)) console.log(String(v.n).padStart(4), (v.h+'px').padStart(6), k);
