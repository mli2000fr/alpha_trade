
import fs from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const files={};
for(const n of ['core.js','extract.js','telegram.js','background.js','popup.js'])files[n]=await fs.readFile(new URL(n,import.meta.url),'utf8');
const results=[];
function pass(name,fn){fn();results.push(name);}
for(const [name,src] of Object.entries(files))pass('Syntaxe '+name,()=>new vm.Script(src,{filename:name}));
const token='123456:ABCDEFGHIJKLMNOPQRSTUVWX',chatId='987654321';
async function harness(response){
 const env={store:{scheduleVersion:2,token,chatId},events:{},calls:[]};
 const evt=name=>({addListener:f=>{env.events[name]=f;}});
 const chrome={
 storage:{local:{get:async()=>structuredClone(env.store),set:async x=>{Object.assign(env.store,structuredClone(x));},setAccessLevel:async()=>{}}},
 alarms:{get:async()=>null,clear:async()=>{},create:async()=>{},onAlarm:evt('alarm')},
 tabs:{onUpdated:evt('updated'),onRemoved:evt('removed')},
 notifications:{onClicked:evt('click')},
 runtime:{id:'test',onStartup:evt('startup'),onInstalled:evt('installed'),onMessage:evt('message')}
 };
 const c=vm.createContext({chrome,URL,Date,Math,Set,AbortSignal,console,setTimeout,clearTimeout,fetch:async(url,options)=>{
  const method=url.split('/').pop();env.calls.push({method,body:JSON.parse(options.body)});
  return await response(method,env);
 }});
 c.importScripts=(...names)=>names.forEach(n=>vm.runInContext(files[n],c));
 vm.runInContext(files['background.js'],c);await vm.runInContext('queue',c);
 env.ctx=c;
 env.msg=(type,extra={})=>new Promise(resolve=>env.events.message({type,...extra},{id:'test'},resolve));
 return env;
}
const reply=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
const accepted=method=>reply({ok:true,result:method==='getMe'?{id:123,is_bot:true}:{message_id:77}});
function safe(env){
 const text=JSON.stringify(env.store.telegramTestLog);
 assert(!text.includes(token));assert(!text.includes(chatId));assert(!text.includes('api.telegram.org/bot'));
}
let env=await harness(async m=>accepted(m));
let r=await env.msg('testTelegram');
pass('Test réussi : getMe puis sendMessage et confirmation persistée',()=>{
 assert(r.ok);assert.equal(env.calls.map(x=>x.method).join(','),'getMe,sendMessage');
 assert.equal(env.store.telegramTestStatus,'success');
 assert(env.store.telegramTestLog.some(x=>x.message.includes('HTTP 200')));
 assert(env.store.telegramTestLog.some(x=>x.message.includes('message n° 77')));
 safe(env);assert(!('token' in r.state));
});
for(const [code,description,expected] of [
 [401,'Unauthorized','BotFather'],
 [403,'Forbidden: bot was blocked by the user','débloquez'],
 [400,'Bad Request: chat not found','chat ID'],
 [429,'Too Many Requests','Réessayer dans 30 s']
]){
 env=await harness(async method=>method==='getMe' && code!==401?accepted(method):reply({ok:false,error_code:code,description,parameters:{retry_after:30}},code));
 r=await env.msg('testTelegram');
 pass('Diagnostic Telegram '+code,()=>{assert(!r.ok);assert(r.error.includes(expected));assert.equal(env.store.telegramTestStatus,'error');assert(env.store.telegramTestLog.some(x=>x.level==='ERREUR'));safe(env);});
}
env=await harness(async()=>{throw Object.assign(new Error('secret '+token),{name:'TimeoutError'});});
r=await env.msg('testTelegram');
pass('Délai dépassé : erreur lisible sans secret',()=>{assert(!r.ok);assert(r.error.includes('Délai'));safe(env);assert(!r.error.includes(token));});
env=await harness(async()=>{throw new TypeError('Failed to fetch '+token);});
r=await env.msg('testTelegram');
pass('Erreur réseau : diagnostic de connexion',()=>{assert(!r.ok);assert(r.error.includes('Connexion'));safe(env);});
env=await harness(async()=>({ok:false,status:502,json:async()=>{throw Error('html');}}));
r=await env.msg('testTelegram');
pass('Réponse non JSON : HTTP conservé dans le journal',()=>{assert(!r.ok);assert(r.error.includes('502'));assert(env.store.telegramTestLog.some(x=>x.message.includes('HTTP 502')));});
env=await harness(async()=>reply({ok:false,error_code:400,description:'Secret '+token+' chat '+chatId+' https://api.telegram.org/bot'+token+'/sendMessage'},400));
r=await env.msg('testTelegram');
pass('Description distante : jeton, chat ID et URL masqués',()=>{assert(!r.ok);safe(env);assert(!r.error.includes(token));assert(!r.error.includes(chatId));});
env=await harness(async m=>accepted(m));env.store.token='';
r=await env.msg('testTelegram');
pass('Jeton absent : journal et aucune requête réseau',()=>{assert(!r.ok);assert.equal(env.calls.length,0);assert(r.error.includes('Enregistrer'));assert.equal(env.store.telegramTestStatus,'error');});
env=await harness(async m=>accepted(m));env.store.chatId='';
r=await env.msg('testTelegram');
pass('Chat ID absent : erreur locale explicite',()=>{assert(!r.ok);assert.equal(env.calls.length,0);assert(r.error.includes('Chat ID'));});
env=await harness(async m=>accepted(m));
await env.msg('testTelegram');
await env.msg('clearTelegramLog');
pass('Effacement du journal sans effacer Telegram',()=>{assert.equal(env.store.telegramTestLog.length,0);assert.equal(env.store.token,token);assert.equal(env.store.chatId,chatId);});
let release,entered;
const started=new Promise(resolve=>entered=resolve);
env=await harness(async method=>{
 if(method==='getMe'){entered();await new Promise(resolve=>release=resolve);}
 return accepted(method);
});
const running=env.msg('testTelegram');
await started;
const snapshot=await env.msg('status');
pass('État et logs accessibles pendant la requête réseau',()=>{assert(snapshot.ok);assert.equal(snapshot.state.telegramTestStatus,'running');assert(snapshot.state.telegramTestLog.length>=3);});
release();await running;
const html=await fs.readFile(new URL('popup.html',import.meta.url),'utf8');
const ids=[...html.matchAll(/id="([^"]+)"/g)].map(x=>x[1]);
pass('Journal affiché et boutons présents',()=>{assert.equal(new Set(ids).size,ids.length);for(const id of ['feedback','telegramTestStatus','telegramLog','copyTelegramLog','clearTelegramLog'])assert(ids.includes(id));});
pass('Cadence et horaires conservés',()=>{assert(files['background.js'].includes('const DEFAULT_SLOT_MINUTES=10;'));assert(files['background.js'].includes('timeAllowed(current)'));});
const manifest=JSON.parse(await fs.readFile(new URL('manifest.json',import.meta.url),'utf8'));
pass('Aucune nouvelle permission',()=>{assert.deepEqual(manifest.permissions,['alarms','storage','scripting','notifications']);assert.equal(manifest.host_permissions.length,2);});

{
 const elements=Object.fromEntries(ids.map(id=>[id,{textContent:'',value:'',checked:false,disabled:false,handlers:{},addEventListener(name,f){this.handlers[name]=f;},replaceChildren(){},append(){}}]));
 const buttons=['toggle','open','test','reset','save','forget','detect','testTelegram','saveHours','clearTelegramLog','copyTelegramLog'].map(id=>elements[id]);
 const state={enabled:false,hoursEnabled:false,hoursStart:'08:00',hoursEnd:'22:00',status:'Désactivée',seen:[],visible:[],recent:[],chatId:'',telegramTestStatus:'idle',telegramTestLog:[]};
 let changes,testReply;
 const testStarted=new Promise(resolve=>{testReply={started:resolve};});
 const document={getElementById:id=>elements[id],querySelectorAll:()=>buttons,createElement:()=>({textContent:'',append(){}})};
 const chrome={runtime:{sendMessage:async msg=>{
  if(msg.type==='status')return {ok:true,state:structuredClone(state)};
  if(msg.type==='testTelegram'){testReply.started();return await new Promise(resolve=>testReply.finish=resolve);}
 }},storage:{onChanged:{addListener:f=>changes=f}}};
 const c=vm.createContext({chrome,document,navigator:{clipboard:{writeText:async()=>{}}},Date,setTimeout,clearTimeout,console});
 vm.runInContext(files['popup.js'],c);
 for(let i=0;i<10;i++)await Promise.resolve();
 const action=vm.runInContext("act('testTelegram')",c);
 await testStarted;
 state.telegramTestStatus='running';state.telegramTestLog=[{at:Date.now(),level:'INFO',message:'getMe : requête envoyée'}];
 changes({},'local');for(let i=0;i<10;i++)await Promise.resolve();
 pass('Fenêtre : progression visible sans réactiver les boutons pendant le test',()=>{assert(elements.telegramLog.textContent.includes('getMe'));assert(buttons.every(b=>b.disabled));});
 state.telegramTestStatus='error';state.telegramTestLog.push({at:Date.now(),level:'ERREUR',message:'Chat introuvable'});
 testReply.finish({ok:false,error:'Chat introuvable'});
 await action;
 changes({},'local');for(let i=0;i<10;i++)await Promise.resolve();
 pass('Fenêtre : erreur conservée après actualisation et boutons libérés',()=>{assert.equal(elements.feedback.textContent,'Chat introuvable');assert(elements.telegramLog.textContent.includes('Chat introuvable'));assert(buttons.every(b=>!b.disabled));});
}

export default results;
