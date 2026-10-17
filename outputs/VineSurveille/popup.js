
const el=id=>document.getElementById(id);
const date=t=>t?new Date(t).toLocaleString('fr-FR'):'—';
let loaded=false,busy=false,refreshQueued=false;
function renderLog(s){
 const labels={idle:'Aucun test en cours',running:'Test en cours…',success:'Message accepté par Telegram',error:'Échec du test'};
 el('telegramTestStatus').textContent=labels[s.telegramTestStatus] || labels.idle;
 const entries=s.telegramTestLog || [];
 el('telegramLog').textContent=entries.length?entries.map(x=>'['+date(x.at)+'] '+x.level+' — '+x.message).join('\n'):'Aucun journal. Cliquez sur « Tester Telegram ».';
}
function render(s){
 el('toggle').textContent=s.enabled?'Désactiver':'Activer';
 el('state').replaceChildren();
 for(const [label,value] of [['Surveillance',s.enabled?'Activée':'Désactivée'],['État',s.enabled && s.hoursEnabled && !s.inHours?'Hors plage horaire — reprise programmée':s.status],['Durée de base',(s.intervalMinutes || 10)+' min (± 1 min)'],['Prochaine tranche',s.plannedWindow?s.plannedWindow.durationMinutes+' min, début '+date(s.plannedWindow.start):'—'],['Horaires',s.hoursEnabled?s.hoursStart+' – '+s.hoursEnd+' (heure locale)':'Toute la journée'],['Dernière tentative',date(s.lastAttempt)],['Dernière lecture réussie',date(s.lastCheck)],['Prochaine vérification prévue',date(s.nextCheck)],['Articles visibles',s.visible.length],['Identifiants mémorisés',s.seen.length]]){
  const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=String(value);el('state').append(dt,dd);
 }
 el('error').textContent=[s.error,s.deliveryError].filter(Boolean).join('\n');
 if(!loaded){el('intervalMinutes').value=s.intervalMinutes || 10;el('hoursEnabled').checked=s.hoursEnabled;el('hoursStart').value=s.hoursStart;el('hoursEnd').value=s.hoursEnd;el('tgEnabled').checked=s.tgEnabled;el('tgProtectionEnabled').checked=s.tgProtectionEnabled!==false;el('chatId').value=s.chatId;loaded=true;}
 el('saved').textContent=s.hasToken?'Un jeton est enregistré.':'Aucun jeton enregistré.';
 renderLog(s);
 el('scheduleLog').textContent=(s.scheduleLog || []).map(x=>'['+date(x.at)+'] '+x.message).join('\n') || 'Aucun événement.';
 el('recent').replaceChildren();
 for(const item of s.recent.slice(0,3)){
  const li=document.createElement('li'),a=document.createElement('a');
  a.textContent=item.title;a.href='https://www.amazon.fr/dp/'+item.id;a.target='_blank';a.rel='noopener noreferrer';
  li.append(a,document.createTextNode(' — '+date(item.at)));el('recent').append(li);
 }
}
async function refresh(){
 if(refreshQueued) return;
 refreshQueued=true;
 try{
  const r=await chrome.runtime.sendMessage({type:'status'});
  if(!r?.ok) throw new Error(r?.error || 'Le service ne répond pas.');
  render(r.state);
 }catch{if(!busy) el('feedback').textContent='Le service ne répond pas. Rechargez l’extension dans chrome://extensions et réessayez.';}
 finally{refreshQueued=false;}
}
async function act(type){
 if(busy) return;
 busy=true;
 document.querySelectorAll('button').forEach(b=>b.disabled=true);
 el('feedback').textContent=type==='testTelegram'?'Demande de test envoyée au service de l’extension. Attente du démarrage…':'Traitement…';
 let waiting;
 if(type==='testTelegram') waiting=setTimeout(()=>{
  if(busy) el('feedback').textContent='Le test prend du temps. Consultez les étapes du journal ci-dessous ; si aucune étape n’apparaît, rechargez l’extension.';
 },28000);
 try{
  const msg={type};
  if(type==='saveInterval'){if(!el('intervalMinutes').checkValidity()) throw new Error('Choisissez un entier entre 1 et 1 440 minutes.');msg.intervalMinutes=Number(el('intervalMinutes').value);}
  if(type==='save') Object.assign(msg,{token:el('token').value,chatId:el('chatId').value,enabled:el('tgEnabled').checked,protectionEnabled:el('tgProtectionEnabled').checked});
  if(type==='saveHours') Object.assign(msg,{hoursEnabled:el('hoursEnabled').checked,hoursStart:el('hoursStart').value,hoursEnd:el('hoursEnd').value});
  const r=await chrome.runtime.sendMessage(msg);
  if(!r?.ok) throw new Error(r?.error || 'Le service ne répond pas.');
  if(['save','forget','detect','saveHours','saveInterval'].includes(type)){loaded=false;el('token').value='';}
  render(r.state);
  el('feedback').textContent=type==='testTelegram'?'Telegram a accepté le message. Consultez le journal.':type==='test'?'Test Chrome envoyé. Vérifiez vos notifications.':'Terminé.';
 }catch(e){
  el('feedback').textContent=e.message || 'Erreur de communication avec le service.';
  if(type==='testTelegram') await refresh();
 }finally{
  clearTimeout(waiting);busy=false;
  document.querySelectorAll('button').forEach(b=>b.disabled=false);
 }
}
for(const id of ['toggle','open','test','reset','save','forget','detect','testTelegram','saveHours','clearTelegramLog','saveInterval']) el(id).addEventListener('click',()=>{
 if(id==='reset' && !confirm('Effacer la référence et l’historique ? La prochaine lecture sera sans alerte.')) return;
 void act(id);
});
el('copyTelegramLog').addEventListener('click',async()=>{
 try{await navigator.clipboard.writeText(el('telegramTestStatus').textContent+'\n'+el('telegramLog').textContent);el('feedback').textContent='Journal copié.';}
 catch{el('feedback').textContent='Copie indisponible : sélectionnez le texte du journal pour le copier.';}
});
chrome.storage.onChanged.addListener((changes,area)=>{
 if(area==='local'){
  // Le statut est lu sans attendre la fin du test ; il ne remplace pas le retour d’action.
  void refresh();
 }
});
void refresh();
