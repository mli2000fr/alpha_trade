
// Journal de diagnostic local : aucun jeton, URL d’API ou identifiant de discussion.
function redactTelegram(value,s){
 let text=String(value ?? '');
 for(const secret of [s.token,s.chatId]) if(secret) text=text.split(secret).join('[masqué]');
 return text.replace(/\b\d+:[A-Za-z0-9_-]+/g,'[jeton masqué]')
  .replace(/https?:\/\/api\.telegram\.org\/[^\s]+/gi,'[URL Telegram masquée]')
  .replace(/[\u0000-\u001f\u007f]/g,' ').slice(0,500);
}
async function testLog(s,level,message){
 const {telegramTestLog=[]}=await chrome.storage.local.get('telegramTestLog');
 const entries=[...telegramTestLog,{at:Date.now(),level,message:redactTelegram(message,s)}].slice(-80);
 await chrome.storage.local.set({telegramTestLog:entries});
}
function telegramAdvice(code,description){
 if(code===401 || code===404) return 'Vérifiez le jeton du bot dans BotFather puis enregistrez-le.';
 if(code===403) return 'Ouvrez votre bot dans Telegram, débloquez-le et appuyez sur Démarrer.';
 if(code===429) return 'Limite Telegram atteinte : attendez avant de retester.';
 if(/chat not found/i.test(description)) return 'Envoyez un message à votre bot, puis vérifiez ou détectez à nouveau le chat ID.';
 if(code===400) return 'Vérifiez le chat ID et les paramètres envoyés ; pour une photo, vérifiez son accessibilité.';
 return 'Vérifiez votre connexion et la configuration du bot.';
}
async function telegramRequest(s,method,payload,log=null){
 if(log) await log('INFO',method+' : requête envoyée (délai maximal 12 s).');
 let response,data;
 const started=Date.now();
 try{
  response=await fetch('https://api.telegram.org/bot'+s.token+'/'+method,{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),
   credentials:'omit',redirect:'error',signal:AbortSignal.timeout(12000)
  });
 }catch(e){
  const timedOut=e?.name==='TimeoutError'||e?.name==='AbortError';
  throw new Error(timedOut?'Délai Telegram dépassé (12 s). Vérifiez le réseau, le VPN ou le pare-feu. Aucun renvoi automatique.':
   'Connexion à Telegram impossible. Vérifiez le réseau, le VPN, le pare-feu ou l’autorisation api.telegram.org de l’extension.');
 }
 if(log) await log('INFO',method+' : réponse HTTP '+response.status+' après '+(Date.now()-started)+' ms.');
 try{data=await response.json();}catch{throw new Error('Réponse Telegram illisible (HTTP '+response.status+', JSON attendu).');}
 if(!response.ok || data?.ok!==true){
  const code=Number(data?.error_code)||response.status;
  const description=redactTelegram(data?.description || 'Aucune description fournie.',s);
  const retry=Number(data?.parameters?.retry_after);
  throw new Error('Telegram '+code+' : '+description+' '+telegramAdvice(code,description)+(Number.isFinite(retry)&&retry>0?' Réessayer dans '+retry+' s.':''));
 }
 return data.result;
}
async function telegram(s,text,photo=null){
 if(!validSettings(s)) throw new Error('Jeton ou identifiant Telegram invalide. Enregistrez la configuration avant de tester.');
 const method=photo?'sendPhoto':'sendMessage';
 const payload=photo?{chat_id:s.chatId,photo,caption:text.slice(0,1000)}:
  {chat_id:s.chatId,text:text.slice(0,3900),link_preview_options:{is_disabled:true}};
 return await telegramRequest(s,method,payload);
}
async function runTelegramTest(){
 const s=await state();
 await chrome.storage.local.set({telegramTestLog:[],telegramTestStatus:'running',telegramTestError:null});
 const log=(level,message)=>testLog(s,level,message);
 try{
  await log('INFO','Test manuel démarré. Il fonctionne même hors plage horaire ou avec la surveillance désactivée.');
  await log('INFO','Configuration enregistrée : jeton '+(s.token?'présent':'absent')+', chat ID '+(s.chatId?'présent':'absent')+'.');
  if(!/^\d+:[A-Za-z0-9_-]{20,}$/.test(s.token)) throw new Error('Jeton absent ou format invalide. Collez-le dans le champ puis cliquez sur Enregistrer.');
  if(!/^-?\d+$/.test(s.chatId)) throw new Error('Chat ID absent ou invalide. Détectez votre discussion puis cliquez sur Enregistrer.');
  await log('INFO','Formats du jeton et du chat ID valides. Vérification du bot…');
  await telegramRequest(s,'getMe',{},log);
  await log('OK','Jeton accepté par Telegram. Envoi du message de test…');
  const result=await telegramRequest(s,'sendMessage',{chat_id:s.chatId,text:'Test Vine Surveille : votre bot Telegram fonctionne.'},log);
  const messageId=Number.isSafeInteger(result?.message_id)?' (message n° '+result.message_id+')':'';
  await log('OK','Telegram confirme la création du message'+messageId+'. Vérifiez la discussion de ce bot et les discussions archivées.');
  await chrome.storage.local.set({telegramTestStatus:'success',telegramTestError:null});
 }catch(e){
  const error=redactTelegram(e?.message || 'Erreur inconnue du test.',s);
  await log('ERREUR',error);
  await chrome.storage.local.set({telegramTestStatus:'error',telegramTestError:error});
  throw new Error(error);
 }
}
