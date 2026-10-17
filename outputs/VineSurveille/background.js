
importScripts('core.js','extract.js','telegram.js');
const ALARM='vine-random';
const defaults={enabled:false,initialized:false,seen:[],visible:[],recent:[],pending:null,lastCheck:null,lastAttempt:null,status:'Désactivée',error:null,deliveryError:null,tgEnabled:false,token:'',chatId:'',hoursEnabled:false,hoursStart:'08:00',hoursEnd:'22:00',intervalMinutes:10,scheduleLog:[],lastWindow:null,lastConsumedWhen:null,tgProtectionEnabled:true,protectionAlert:null,telegramTestLog:[],telegramTestStatus:'idle',telegramTestError:null};
let queue=Promise.resolve();
function serial(fn){
 const job=queue.then(fn);
 queue=job.catch(async()=>{try{await chrome.storage.local.set({error:'Erreur technique. Réessayez ou rechargez l’extension.'});}catch{}});
 return job;
}
async function state(){return {...defaults,...await chrome.storage.local.get(null)};}


const DEFAULT_SLOT_MINUTES=10;
function validInterval(value){return Number.isInteger(value) && value>=1 && value<=1440;}
function validTime(value){return typeof value==='string' && /^([01]\d|2[0-3]):[0-5]\d$/.test(value);}
function timeAllowed(s,now=Date.now()){
 if(!s.hoursEnabled) return true;
 if(!validTime(s.hoursStart)||!validTime(s.hoursEnd)||s.hoursStart===s.hoursEnd) return false;
 const minutes=t=>Number(t.slice(0,2))*60+Number(t.slice(3));
 const d=new Date(now),n=d.getHours()*60+d.getMinutes(),start=minutes(s.hoursStart),end=minutes(s.hoursEnd);
 return start<end ? n>=start&&n<end : n>=start||n<end;
}
function dynamicDurations(value){
 const n=validInterval(value)?value:DEFAULT_SLOT_MINUTES;
 return [...new Set([Math.max(1,n-1),n,n+1])];
}
function permittedSegments(s,lower,upper){
 const segments=[];
 for(let t=lower;t<upper;){
  const end=Math.min(upper,(Math.floor(t/60000)+1)*60000);
  if(timeAllowed(s,t))segments.push([t,end]);
  t=end;
 }
 return segments;
}
function nextOpening(s,from){
 if(timeAllowed(s,from))return from;
 let t=(Math.floor(from/60000)+1)*60000;
 for(let i=0;i<3*24*60;i++,t+=60000)if(timeAllowed(s,t))return t;
 throw new Error('Aucune plage horaire valide trouvée dans les trois prochains jours.');
}
function dynamicPlan(s,now,previousEnd=null,random=Math.random){
 // Au démarrage, laisse 30 s à Chrome avant le début de la première tranche.
 const earliest=now+30000;
 let start=Number.isFinite(previousEnd)?previousEnd:earliest;
 // Une première minute expirée est abandonnée, sans contrôle de rattrapage.
 if(start+60000<=earliest)start=earliest;
 let segments=permittedSegments(s,Math.max(start,earliest),start+60000);
 if(!segments.length){
  start=nextOpening(s,Math.max(start,earliest));
  segments=permittedSegments(s,start,start+60000);
 }
 const durations=dynamicDurations(s.intervalMinutes);
 const durationMinutes=durations[Math.min(durations.length-1,Math.floor(random()*durations.length))];
 const total=segments.reduce((n,[a,b])=>n+b-a,0);
 let offset=Math.min(total-1,Math.floor(random()*total));
 let when;
 for(const [a,b]of segments){if(offset<b-a){when=a+offset;break;}offset-=b-a;}
 return {start,end:start+durationMinutes*60000,durationMinutes,when};
}

async function surveillanceLog(message){
 const {scheduleLog=[]}=await chrome.storage.local.get('scheduleLog');
 await chrome.storage.local.set({scheduleLog:[...scheduleLog,{at:Date.now(),message}].slice(-40)});
}
function validPlan(s,plan){
 return !!plan && [plan.start,plan.end,plan.when].every(Number.isFinite) &&
  dynamicDurations(s.intervalMinutes).includes(plan.durationMinutes) &&
  plan.end-plan.start===plan.durationMinutes*60000 &&
  plan.when>=plan.start && plan.when<plan.start+60000;
}
async function schedule(previousEnd=null){
 const s=await state(),plan=dynamicPlan(s,Date.now(),previousEnd);
 await chrome.storage.local.set({plannedWindow:plan});
 await chrome.alarms.create(ALARM,{when:plan.when});
 await surveillanceLog('Tranche de '+plan.durationMinutes+' min, début '+new Date(plan.start).toLocaleString('fr-FR')+' ; contrôle prévu '+new Date(plan.when).toLocaleString('fr-FR')+'.');
}
async function processPlan(plan,origin){
 const s=await state();
 if(!s.enabled || !validPlan(s,plan) || s.plannedWindow?.when!==plan.when || s.lastConsumedWhen===plan.when)return;
 const now=Date.now();
 if(now<plan.when)return;
 // Marque durable : le réveil et l’événement d’alarme ne doivent jamais traiter deux fois la tranche.
 await chrome.storage.local.set({lastConsumedWhen:plan.when,lastWindow:plan});
 await schedule(plan.end);
 if(inFirstMinute(plan)){
  await surveillanceLog('Contrôle lancé ('+origin+').');
  await check(plan);
 }else{
  await chrome.storage.local.set({status:'Première minute dépassée — contrôle ignoré'});
  await surveillanceLog('Contrôle ignoré : première minute dépassée, retard de '+Math.max(0,Math.round((now-plan.when)/1000))+' s ('+origin+').');
 }
}
async function reconcile(){
 await chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
 if((await state()).scheduleVersion!==4){
  for(const name of ['vine-5min','vine-10min',ALARM])await chrome.alarms.clear(name);
  await chrome.storage.local.set({scheduleVersion:4,lastSlot:-1,plannedSlot:null,plannedWindow:null,pending:null,lastConsumedWhen:null});
 }
 const s=await state();
 if(!s.enabled){await chrome.alarms.clear(ALARM);return;}
 const plan=s.plannedWindow,alarm=await chrome.alarms.get(ALARM);
 if(!validPlan(s,plan)){
  await chrome.alarms.clear(ALARM);
  await schedule();
  return;
 }
 if(s.lastConsumedWhen===plan.when){
  // Reprise après une interruption entre le marquage et la programmation suivante.
  await chrome.alarms.clear(ALARM);
  await schedule(plan.end);
  return;
 }
 if(!alarm){
  if(plan.when<=Date.now()){
   // Une alarme ponctuelle peut déjà être retirée lorsque son événement réveille le worker.
   await processPlan(plan,'reprise du service');
  }else{
   // Conserve l’instant tiré même s’il est à moins de 30 s ; Chrome peut retarder son exécution.
   await chrome.alarms.create(ALARM,{when:plan.when});
   await surveillanceLog('Alarme future rétablie sans changer la tranche.');
  }
 }else if(Number.isFinite(alarm.scheduledTime) && Math.abs(alarm.scheduledTime-plan.when)>1){
  await chrome.alarms.create(ALARM,{when:plan.when});
  await surveillanceLog('Alarme remise en accord avec le contrôle mémorisé.');
 }
}

async function stop(error,{protection=false}={}){
 const s=await state();
 await chrome.storage.local.set({enabled:false,pending:null,error,status:'Intervention nécessaire'});
 await chrome.alarms.clear(ALARM);
 // L’état désactivé empêche les événements suivants de renvoyer la même alerte.
 if(!protection || !s.enabled)return;
 const at=Date.now();
 if(s.tgProtectionEnabled===false){
  await chrome.storage.local.set({protectionAlert:{at,status:'disabled'}});
  return;
 }
 if(!validSettings(s)){
  await chrome.storage.local.set({protectionAlert:{at,status:'failed'},deliveryError:'Alerte protection non envoyée : configurez le jeton et le chat ID Telegram.'});
  return;
 }
 await chrome.storage.local.set({protectionAlert:{at,status:'sending'}});
 try{
  await telegram(s,'⚠️ Protection Amazon détectée\n\nLa surveillance Vine a été arrêtée.\n\nOuvrez Vine et résolvez manuellement le CAPTCHA ou la vérification demandée. Lorsque la liste des articles est accessible, ouvrez l’extension puis cliquez sur « Activer ».\n\n'+Vine.url);
  await chrome.storage.local.set({protectionAlert:{at,status:'sent'},deliveryError:null});
 }catch(e){
  await chrome.storage.local.set({protectionAlert:{at,status:'failed'},deliveryError:'Échec de l’alerte protection Telegram : '+redactTelegram(e?.message || 'Erreur réseau.',s)});
 }
}

async function openVine(){
 const tabs=await chrome.tabs.query({url:'https://www.amazon.fr/vine/vine-items*'});
 const t=tabs.find(t=>Vine.matches(t.url));
 if(t){await chrome.tabs.update(t.id,{active:true});await chrome.windows.update(t.windowId,{focused:true});}
 else {const win=await chrome.windows.getLastFocused({windowTypes:['normal']});await chrome.tabs.create({url:Vine.url,windowId:win.id,index:0,active:true});}
}
async function notification(id,title,message){
 await chrome.notifications.create(id,{type:'basic',iconUrl:'icon.png',title,message});
}
function validSettings(s){return /^\d+:[A-Za-z0-9_-]{20,}$/.test(s.token) && /^-?\d+$/.test(s.chatId);}

async function sendNewProducts(s,items){
 // Appel uniquement depuis la branche des ASIN nouveaux ; aucun message de statut.
 for(let i=0;i<items.length;i++){
  if(i) await new Promise(resolve=>setTimeout(resolve,1100));
  const current=await state();
  if(!current.enabled || !timeAllowed(current)) return;
  const item=items[i];
  const caption='🆕 Nouvel article Amazon Vine\n\n'+item.title+'\n\nFiche produit : https://www.amazon.fr/dp/'+item.id+'\n\nOuvrir Amazon Vine : '+Vine.url;
  await telegram(s,caption+(item.image?'':'\n\nPhoto indisponible sur la carte.'),item.image || null);
 }
}

function inFirstMinute(plan,now=Date.now()){return !!plan && now>=plan.start && now<plan.start+60000;}
async function check(plan){
 if(!inFirstMinute(plan))return;
 const s=await state(); if(!s.enabled) return;
 if(!timeAllowed(s)){await chrome.storage.local.set({pending:null,status:'Hors plage horaire — reprise programmée'});return;}
 if(s.pending && Date.now()-s.pending.started<120000) return;
 const tabs=await chrome.tabs.query({url:'https://www.amazon.fr/vine/vine-items*'});
 const t=tabs.find(t=>Vine.matches(t.url));
 if(!inFirstMinute(plan))return;
 if(!t){
  try{
   const win=await chrome.windows.getLastFocused({windowTypes:['normal']});
   if(!inFirstMinute(plan) || !timeAllowed(await state()))return;
   const created=await chrome.tabs.create({url:Vine.url,windowId:win.id,index:0,active:false});
   await chrome.storage.local.set({pending:{tabId:created.id,started:Date.now()},lastAttempt:Date.now(),status:'Onglet Vine ouvert en première position — chargement…',error:null});
   // La création navigue déjà vers Vine : pas de second rechargement.
   if(created.status==='complete')await complete(created.id);
  }catch{await chrome.storage.local.set({pending:null,status:'Ouverture impossible',error:'Impossible d’ouvrir Vine. Ouvrez une fenêtre Chrome normale puis réessayez.'});}
  return;
 }
 await chrome.storage.local.set({pending:{tabId:t.id,started:Date.now()},lastAttempt:Date.now(),status:'Chargement…',error:null});
 if(!inFirstMinute(plan)){await chrome.storage.local.set({pending:null,status:'Première minute dépassée — contrôle ignoré'});return;}
 try{await chrome.tabs.reload(t.id);}catch{await chrome.storage.local.set({pending:null,error:'Impossible de recharger l’onglet.',status:'Erreur de chargement'});}
}
async function complete(tabId){
 const s=await state();
 if(!s.enabled || s.pending?.tabId!==tabId) return;
 if(!timeAllowed(s)){await chrome.storage.local.set({pending:null,status:'Hors plage horaire — reprise programmée'});return;}
 if(Date.now()-s.pending.started>120000){await chrome.storage.local.set({pending:null,error:'Chargement expiré.',status:'Erreur de chargement'});return;}
 try{
  const tab=await chrome.tabs.get(tabId);
  if(!Vine.matches(tab.url)){let protection=false;try{const u=new URL(tab.url);protection=u.origin==='https://www.amazon.fr' && /captcha|robotcheck|challenge/i.test(u.pathname);}catch{}await stop('Onglet redirigé ou modifié. Vérifiez la page puis réactivez.',{protection});return;}
  const results=await chrome.scripting.executeScript({target:{tabId},func:extractVine});
  const r=results[0]?.result;
  if(!r || r.error){
   if(r?.stop) await stop(r.error,{protection:r.protection===true});
   else await chrome.storage.local.set({pending:null,status:'Lecture impossible',error:r?.error || 'Lecture sans résultat.'});
   return;
  }
  if(!timeAllowed(await state())){await chrome.storage.local.set({pending:null,status:'Hors plage horaire — reprise programmée'});return;}
  const added=Vine.diff(s.seen,r.items,s.initialized);
  const seen=[...new Set([...s.seen,...r.items.map(x=>x.id)])];
  if(seen.length>20000){await stop('Limite de 20 000 identifiants atteinte. Réinitialisez la référence.');return;}
  await chrome.storage.local.set({pending:null,initialized:true,seen,visible:r.items,lastCheck:Date.now(),error:null,status:s.initialized?added.length+' nouveauté(s)':'Référence initiale enregistrée',recent:added.length?[...added.map(x=>({...x,at:Date.now()})),...s.recent].slice(0,50):s.recent});
  if(added.length && timeAllowed(await state())){
   const errors=[];
   try{await notification('vine-new','Vine : '+added.length+' nouveauté(s)',added.slice(0,3).map(x=>x.title).join('\n'));}catch{errors.push('Notification Chrome impossible.');}
   if(s.tgEnabled) try{
    await sendNewProducts(s,added);
   }catch(e){errors.push(e.message);}
   await chrome.storage.local.set({deliveryError:errors.join('\n') || null});
  }
 }catch{await chrome.storage.local.set({pending:null,error:'Lecture impossible : onglet fermé, navigation ou structure modifiée.',status:'Erreur de lecture'});}
}


chrome.alarms.onAlarm.addListener(a=>{
 if(a.name!==ALARM)return;
 void serial(async()=>{
  const s=await state(),plan=s.plannedWindow;
  if(!s.enabled || !validPlan(s,plan))return;
  if(Number.isFinite(a.scheduledTime) && Math.abs(a.scheduledTime-plan.when)>1)return;
  await processPlan(plan,'alarme Chrome');
 }).catch(()=>{});
});

chrome.tabs.onUpdated.addListener((id,info)=>{if(info.status==='complete') void serial(()=>complete(id)).catch(()=>{});});
chrome.tabs.onRemoved.addListener(id=>{void serial(async()=>{if((await state()).pending?.tabId===id) await chrome.storage.local.set({pending:null,error:'Onglet fermé. Il sera rouvert au prochain contrôle autorisé.',status:'En attente'});}).catch(()=>{});});
chrome.notifications.onClicked.addListener(id=>{if(['vine-new','vine-test'].includes(id)) void openVine().catch(()=>{});});
chrome.runtime.onStartup.addListener(()=>{void serial(async()=>{await chrome.storage.local.set({pending:null});await reconcile();}).catch(()=>{});});
chrome.runtime.onInstalled.addListener(()=>{void serial(reconcile).catch(()=>{});});
async function publicState(){const s=await state();const a=await chrome.alarms.get(ALARM);const {token,...safe}=s;return {...safe,hasToken:!!token,inHours:timeAllowed(s),nextCheck:a?.scheduledTime || null};}
chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
 if(sender.id!==chrome.runtime.id || sender.tab || !['status','toggle','open','test','testTelegram','save','forget','detect','reset','saveHours','clearTelegramLog','saveInterval'].includes(msg?.type)) return;
 if(msg.type==='status'){publicState().then(s=>reply({ok:true,state:s}),()=>reply({ok:false,error:'État indisponible.'}));return true;}
 serial(async()=>{
  if(msg.type==='toggle'){
   const enabled=!(await state()).enabled;
   await chrome.storage.local.set({enabled,pending:null,plannedWindow:null,error:null,status:enabled?'Activation…':'Désactivée'});
   await reconcile();
  }


  if(msg.type==='saveInterval'){
   const intervalMinutes=msg.intervalMinutes;
   if(!validInterval(intervalMinutes)) throw new Error('La durée doit être un nombre entier entre 1 et 1 440 minutes.');
   const prior=await state();
   if(intervalMinutes!==prior.intervalMinutes){
    await chrome.storage.local.set({intervalMinutes,plannedWindow:null,pending:null});
    await chrome.alarms.clear(ALARM);
    await reconcile();
   }
  }
  if(msg.type==='saveHours'){
   const hoursEnabled=msg.hoursEnabled===true,hoursStart=String(msg.hoursStart || ''),hoursEnd=String(msg.hoursEnd || '');
   if(!validTime(hoursStart)||!validTime(hoursEnd)||hoursStart===hoursEnd) throw new Error('Choisissez deux heures différentes au format HH:MM. Pour toute la journée, décochez la plage horaire.');
   await chrome.storage.local.set({hoursEnabled,hoursStart,hoursEnd,plannedWindow:null,pending:null});
   await chrome.alarms.clear(ALARM);await reconcile();
   const current=await state();
   if(current.enabled) await chrome.storage.local.set({status:timeAllowed(current)?'En attente de la prochaine vérification':'Hors plage horaire — reprise programmée'});
  }
  if(msg.type==='open') await openVine();
  if(msg.type==='test') await notification('vine-test','Vine Surveille','Le test de notification fonctionne.');
  if(msg.type==='save'){
   const token=String(msg.token || '').trim(),chatId=String(msg.chatId || '').trim();
   const enabled=msg.enabled===true;
   const prior=await state();const config={token:token || prior.token,chatId,tgEnabled:enabled,tgProtectionEnabled:msg.protectionEnabled!==false};
   if(enabled && !validSettings(config)) throw new Error('Jeton ou identifiant Telegram invalide.');
   await chrome.storage.local.set(config);
  }
  if(msg.type==='detect'){
 const s=await state();
 if(!/^\d+:[A-Za-z0-9_-]{20,}$/.test(s.token)) throw new Error('Enregistrez d’abord le jeton, avec Telegram décoché.');
 let data;
 try{
  const r=await fetch('https://api.telegram.org/bot'+s.token+'/getUpdates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({allowed_updates:['message'],limit:100}),credentials:'omit',redirect:'error',signal:AbortSignal.timeout(12000)});
  data=await r.json();
 }catch{throw new Error('Telegram inaccessible.');}
 if(!data.ok) throw new Error('Lecture Telegram refusée. Utilisez un bot dédié sans webhook.');
 const ids=[...new Set(data.result.filter(x=>x.message?.chat?.type==='private').map(x=>String(x.message.chat.id)))];
 if(ids.length!==1) throw new Error('Envoyez un message à votre bot dédié puis réessayez. Une seule discussion privée doit être trouvée ; sinon renseignez son identifiant manuellement.');
 await chrome.storage.local.set({chatId:ids[0]});
}
if(msg.type==='forget') await chrome.storage.local.set({token:'',chatId:'',tgEnabled:false});
  if(msg.type==='testTelegram') await runTelegramTest();
  if(msg.type==='clearTelegramLog') await chrome.storage.local.set({telegramTestLog:[],telegramTestStatus:'idle',telegramTestError:null});
  if(msg.type==='reset') await chrome.storage.local.set({initialized:false,seen:[],visible:[],recent:[],status:'Référence effacée ; prochaine lecture sans alerte',error:null,deliveryError:null});
  return await publicState();
 }).then(s=>reply({ok:true,state:s}),e=>reply({ok:false,error:e.message}));
 return true;
});
void serial(reconcile).catch(()=>{});
