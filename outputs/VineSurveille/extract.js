
async function extractVine() {
 const u=new URL(location.href);
 if(u.origin!=='https://www.amazon.fr' || u.pathname!=='/vine/vine-items' || u.searchParams.get('queue')!=='potluck') return {error:'Page incorrecte ou connexion requise.',stop:true};
 const protectedPage=()=>document.querySelector('#captchacharacters, form[action*="validateCaptcha"], input[name="cvf_captcha_input"]') || /captcha|robot check|vérification de sécurité|saisissez les caractères|automated access/i.test(document.body?.innerText || '');
 const blocked=()=>document.querySelector('#captchacharacters, form[action*="validateCaptcha"], input[name="cvf_captcha_input"]') || /captcha|robot check|vérification de sécurité|saisissez les caractères|automated access|service unavailable|service indisponible/i.test(document.body?.innerText || '');
 if(!document.querySelector('#vvp-items-grid .vvp-item-tile') && !blocked()) await new Promise(resolve=>{
  const observer=new MutationObserver(()=>{if(document.querySelector('#vvp-items-grid .vvp-item-tile') || blocked()) done();});
  const timer=setTimeout(done,8000);
  function done(){clearTimeout(timer);observer.disconnect();resolve();}
  observer.observe(document.documentElement,{childList:true,subtree:true});
 });
 if(protectedPage()) return {error:'Protection Amazon détectée : vérifiez manuellement puis réactivez.',stop:true,protection:true};
 if(blocked()) return {error:'Service Amazon indisponible : vérifiez manuellement puis réactivez.',stop:true};
 if(document.querySelector('input[type="password"], #ap_email')) return {error:'Connexion Amazon requise.',stop:true};
 const grid=document.querySelector('#vvp-items-grid');
 if(!grid) return {error:'Grille Vine introuvable : vérifiez la page et votre connexion.',stop:true};
 const items=[],ids=new Set();
 for(const tile of grid.querySelectorAll('.vvp-item-tile')){
  if(!tile.getClientRects().length || getComputedStyle(tile).visibility==='hidden') continue;
  const link=tile.querySelector('a[href*="/dp/"], a[href*="/gp/product/"]');
  const raw=tile.getAttribute('data-asin') || tile.querySelector('[data-asin]')?.getAttribute('data-asin') || link?.getAttribute('href')?.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})(?:[/?#]|$)/i)?.[1];
  const id=(raw || '').trim().toUpperCase();
  if(!/^[A-Z0-9]{10}$/.test(id)) return {error:'Identifiant non reconnu. Référence conservée.',stop:true};
  if(!ids.has(id)){
   ids.add(id);
   const title=(tile.querySelector('.a-truncate-full, .vvp-item-product-title-container')?.textContent || link?.textContent || id).trim().replace(/\s+/g,' ').slice(0,160);
   
    const imageNode=tile.querySelector('.vvp-item-product-image-container img, img');
    let image=null;
    for(const candidate of [imageNode?.getAttribute('data-src'),imageNode?.currentSrc,imageNode?.src]){
     try{
      const u=new URL(candidate || '');
      const host=u.hostname;
      if(u.protocol==='https:' && !u.username && !u.password && !u.port &&
        ['media-amazon.com','images-amazon.com','ssl-images-amazon.com'].some(h=>host===h || host.endsWith('.'+h))){
       image=u.href;break;
      }
     }catch{}
    }
    items.push({id,title,image});
  }
 }
 if(!items.length) return {error:'Aucun article lisible : liste vide ou chargement incomplet. Référence conservée.'};
 return {items};
}
