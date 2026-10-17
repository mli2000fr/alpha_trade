
import fs from 'node:fs/promises';import vm from 'node:vm';import assert from 'node:assert/strict';
const files={};for(const n of ['core.js','extract.js','telegram.js','background.js','popup.js'])files[n]=await fs.readFile(new URL(n,import.meta.url),'utf8');
const results=[];const pass=(n,f)=>{f();results.push(n);};
for(const[n,s]of Object.entries(files))pass('Syntaxe '+n,()=>new vm.Script(s));
async function harness(extra={}){
 const env={s:{enabled:true,scheduleVersion:4,tgEnabled:false,tgProtectionEnabled:true,token:'123456:ABCDEFGHIJKLMNOPQRSTUVWX',chatId:'987654321',...extra},calls:[],events:{},fail:false,alarm:true};
 const ev=n=>({addListener:f=>env.events[n]=f});
 const chrome={storage:{local:{get:async()=>structuredClone(env.s),set:async x=>Object.assign(env.s,structuredClone(x)),setAccessLevel:async()=>{}}},
 alarms:{get:async()=>env.alarm?{}:null,create:async()=>{env.alarm=true;},clear:async()=>{env.alarm=false;},onAlarm:ev('alarm')},
 tabs:{onUpdated:ev('updated'),onRemoved:ev('removed')},notifications:{onClicked:ev('clicked')},
 runtime:{id:'test',onStartup:ev('startup'),onInstalled:ev('install'),onMessage:ev('message')}};
 const c=vm.createContext({chrome,URL,Date,Math,Set,AbortSignal,console,setTimeout,clearTimeout,fetch:async(url,options)=>{
  assert.equal(env.s.enabled,false);assert.equal(env.alarm,false);
  env.calls.push({url,payload:JSON.parse(options.body)});
  if(env.fail)throw Error('Simulated network failure '+env.s.token);
  return{ok:true,status:200,json:async()=>({ok:true,result:{message_id:1}})};
 }});
 c.importScripts=(...ns)=>ns.forEach(n=>vm.runInContext(files[n],c));
 vm.runInContext(files['background.js'],c);await vm.runInContext('queue',c);
 env.c=c;return env;
}
let e=await harness();
await vm.runInContext("stop('Protection détectée',{protection:true})",e.c);
pass('Protection : surveillance arrêtée avant l’envoi, une alerte avec lien et instructions',()=>{
 assert.equal(e.calls.length,1);const body=e.calls[0].payload;assert(body.text.includes('Protection Amazon'));assert(body.text.includes('Activer'));assert(body.text.includes('https://www.amazon.fr/vine/vine-items?queue=potluck'));assert.equal(e.s.protectionAlert.status,'sent');assert.equal(e.s.enabled,false);
});
await vm.runInContext("stop('Protection détectée',{protection:true})",e.c);
pass('Pas de doublon après arrêt',()=>assert.equal(e.calls.length,1));
e.s.enabled=true;e.alarm=true;
await vm.runInContext("stop('Nouvelle protection',{protection:true})",e.c);
pass('Nouvel arrêt après réactivation : nouvelle alerte autorisée',()=>assert.equal(e.calls.length,2));
e=await harness({tgProtectionEnabled:false});await vm.runInContext("stop('Protection',{protection:true})",e.c);
pass('Option décochée : arrêt sans alerte',()=>{assert.equal(e.calls.length,0);assert.equal(e.s.enabled,false);assert.equal(e.s.protectionAlert.status,'disabled');});
e=await harness({token:''});await vm.runInContext("stop('Protection',{protection:true})",e.c);
pass('Configuration absente : arrêt et erreur locale sans requête',()=>{assert.equal(e.calls.length,0);assert.equal(e.s.enabled,false);assert.equal(e.s.protectionAlert.status,'failed');assert(e.s.deliveryError.includes('configurez'));});
e=await harness();e.fail=true;await vm.runInContext("stop('Protection',{protection:true})",e.c);
await vm.runInContext("stop('Protection',{protection:true})",e.c);
pass('Échec Telegram : arrêt conservé, erreur masquée, sans répétition automatique',()=>{
 assert.equal(e.calls.length,1);assert.equal(e.s.enabled,false);assert.equal(e.s.protectionAlert.status,'failed');assert(e.s.deliveryError.includes('Échec'));assert(!e.s.deliveryError.includes(e.s.token));
});
e=await harness();await vm.runInContext("stop('Grille inconnue')",e.c);
pass('Autre erreur : aucun faux message de protection',()=>assert.equal(e.calls.length,0));
async function extract(text){
 const document={body:{innerText:text},querySelector:s=>s==='#vvp-items-grid .vvp-item-tile'?{}:null};
 const c=vm.createContext({document,URL,location:{href:'https://www.amazon.fr/vine/vine-items?queue=potluck'}});
 vm.runInContext(files['extract.js'],c);return await vm.runInContext('extractVine()',c);
}
let r=await extract('Robot Check CAPTCHA');
pass('CAPTCHA reconnu et signalé explicitement',()=>{assert(r.stop);assert.equal(r.protection,true);});
r=await extract('Service Unavailable');
pass('Panne de service distinguée d’une protection',()=>{assert(r.stop);assert(!r.protection);});
const html=await fs.readFile(new URL('popup.html',import.meta.url),'utf8');
pass('Option de protection présente',()=>assert(html.includes('id="tgProtectionEnabled"')));
export default results;
