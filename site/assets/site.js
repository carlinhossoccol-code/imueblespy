(()=>{'use strict';
const toggle=document.querySelector('[data-menu-toggle]');const nav=document.querySelector('#main-menu');
const closeMenu=()=>{if(!nav||!toggle)return;nav.classList.remove('is-open');toggle.setAttribute('aria-expanded','false');};
if(toggle&&nav){toggle.addEventListener('click',()=>{const open=nav.classList.toggle('is-open');toggle.setAttribute('aria-expanded',String(open));});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeMenu();toggle.focus();}});
 document.addEventListener('click',e=>{if(!toggle.contains(e.target)&&!nav.contains(e.target))closeMenu();});}
const form=document.querySelector('[data-city-search]');if(!form)return;
const locale=document.documentElement.lang.toLowerCase().startsWith('pt')?'pt-br':'es';
const input=form.querySelector('input');const list=form.querySelector('[data-suggestions]');const status=document.querySelector('[data-status]');let places=[];
const norm=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const close=()=>{list.hidden=true;input.setAttribute('aria-expanded','false');};
const show=()=>{const q=norm(input.value.trim());list.replaceChildren();if(!q){close();return [];}
 const hits=places.filter(p=>norm(p.name+' '+p.department).includes(q)).slice(0,9);
 for(const place of hits){if(typeof place.url!=='string'||!place.url.startsWith('/'+locale+'/'))continue;
 const a=document.createElement('a');a.href=place.url;a.textContent=place.name+' · '+place.department;list.append(a);}
 list.hidden=!list.children.length;input.setAttribute('aria-expanded',String(!list.hidden));return hits;};
input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-haspopup','true');input.setAttribute('aria-controls','city-options');input.setAttribute('aria-expanded','false');list.id='city-options';
list.setAttribute('role','group');list.setAttribute('aria-label',locale==='es'?'Ciudades sugeridas':'Cidades sugeridas');
fetch('/assets/search-'+locale+'.json').then(r=>r.ok?r.json():Promise.reject(Error('data'))).then(d=>{places=d;if(input.value.trim())show();}).catch(()=>{if(status)status.textContent=locale==='es'?'Explorá desde los enlaces de ciudades.':'Explore pelos links das cidades.';});
input.addEventListener('input',()=>{if(status)status.textContent='';show();});
input.addEventListener('keydown',event=>{if(event.key==='ArrowDown'&&!list.hidden){event.preventDefault();list.querySelector('a')?.focus();}if(event.key==='Escape')close();});
list.addEventListener('keydown',event=>{if(event.key==='Escape'){close();input.focus();}
 if(event.key==='ArrowDown'||event.key==='ArrowUp'){const links=[...list.querySelectorAll('a')];const i=links.indexOf(document.activeElement);if(i!==-1){event.preventDefault();links[(i+(event.key==='ArrowDown'?1:-1)+links.length)%links.length].focus();}}});
form.addEventListener('submit',event=>{event.preventDefault();const hits=show();if(hits.length&&typeof hits[0].url==='string'&&hits[0].url.startsWith('/'+locale+'/'))location.assign(hits[0].url);
else if(status)status.textContent=locale==='es'?'No encontramos esa localidad. Probá con otra ciudad.':'Não encontramos essa cidade. Tente outra busca.';});
document.addEventListener('click',event=>{if(!form.contains(event.target))close();});
})();