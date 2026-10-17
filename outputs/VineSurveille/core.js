
globalThis.Vine = {
 url:'https://www.amazon.fr/vine/vine-items?queue=potluck',
 matches(url) {
  try { const u=new URL(url); return u.origin==='https://www.amazon.fr' && u.pathname==='/vine/vine-items' && u.searchParams.get('queue')==='potluck' && (!u.searchParams.has('page') || u.searchParams.get('page')==='1') && !u.searchParams.has('search'); } catch {return false;}
 },
 diff(seen,items,initialized) {const known=new Set(seen);return initialized?items.filter(x=>!known.has(x.id)):[];}
};
