
import fs from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const files={};for(const n of ['core.js','extract.js','telegram.js','background.js','popup.js'])files[n]=await fs.readFile(new URL(n,import.meta.url),'utf8');
const results=[];const pass=(n,f)=>{f();results.push(n);};
for(const[n,s]of Object.entries(files))pass('Syntaxe '+n,()=>new vm.Script(s,{filename:n}));
const env={now:new Date(2026,9,17,7,0).getTime(),store:{scheduleVersion:3,enabled:true,intervalMinutes:5,seen:['B000000001'],token:'conserve',chatId:'1234'},alarms:new Map([['vine-random',{when:0}]]),events:{},reloads:0};
class Clock extends Date{constructor(...args){super(...(args.length?args:[env.now]));}static now(){return env.now;}}
const evt=n=>({addListener:f=>env.events[n]=f});
const chrome={storage:{local:{get:async()=>structuredClone(env.store),set:async x=>Object.assign(env.store,structuredClone(x)),setAccessLevel:async()=>{}}},
 alarms:{get:async n=>env.alarms.get(n),clear:async n=>env.alarms.delete(n),create:async(n,x)=>env.alarms.set(n,{...x,scheduledTime:x.when}),onAlarm:evt('alarm')},
 tabs:{query:async()=>[{id:7,url:'https://www.amazon.fr/vine/vine-items?queue=potluck'}],reload:async()=>{env.reloads++;},onUpdated:evt('updated'),onRemoved:evt('removed')},
 notifications:{onClicked:evt('click')},runtime:{id:'test',onStartup:evt('startup'),onInstalled:evt('install'),onMessage:evt('message')}};
const c=vm.createContext({chrome,URL,Date:Clock,Math,Set,AbortSignal,console,setTimeout,clearTimeout});
c.importScripts=(...names)=>names.forEach(n=>vm.runInContext(files[n],c));
vm.runInContext(files['background.js'],c);await vm.runInContext('queue',c);
const msg=(type,extra={})=>new Promise(r=>env.events.message({type,...extra},{id:'test'},r));
pass('Migration vers les tranches dynamiques sans effacer Telegram / ASIN',()=>{
 assert.equal(env.store.scheduleVersion,4);assert(env.alarms.has('vine-random'));assert.equal(env.store.intervalMinutes,5);assert.equal(env.store.token,'conserve');assert.equal(env.store.seen[0],'B000000001');
});
pass('Base 5 : durées 4, 5 et 6 ; base 1 : durées 1 et 2',()=>{
 assert.equal(JSON.stringify(c.dynamicDurations(5)),'[4,5,6]');assert.equal(JSON.stringify(c.dynamicDurations(1)),'[1,2]');assert.equal(JSON.stringify(c.dynamicDurations(1440)),'[1439,1440,1441]');
});
let plans=0;
for(const base of [1,2,5,10,60,1440])for(const hours of [
 {hoursEnabled:false},
 {hoursEnabled:true,hoursStart:'08:03',hoursEnd:'08:04'},
 {hoursEnabled:true,hoursStart:'22:00',hoursEnd:'06:00'}
])for(const h of [0,7,21,23])for(const r of [0,.5,.999999]){
 const s={...hours,intervalMinutes:base},now=new Date(2026,9,17,h,59,45).getTime();
 const p=c.dynamicPlan(s,now,null,()=>r);
 assert(c.dynamicDurations(base).includes(p.durationMinutes));
 assert.equal(p.end-p.start,p.durationMinutes*60000);
 assert(p.when>=now+30000);assert(p.when>=p.start);assert(p.when<p.start+60000);assert(c.timeAllowed(s,p.when));plans++;
}
results.push(plans+' plans : durée autorisée, première minute, minimum 30 s et horaires respectés');
pass('Les trois durées possibles sont effectivement tirées',()=>{
 const seen=new Set();for(const r of [0,.5,.999999])seen.add(c.dynamicPlan({intervalMinutes:5},env.now,null,()=>r).durationMinutes);
 assert.equal([...seen].sort().join(','),'4,5,6');
});
pass('Chaînage : prochaine tranche commence à la fin de la précédente',()=>{
 const first=c.dynamicPlan({intervalMinutes:5},env.now,null,()=>0);
 const next=c.dynamicPlan({intervalMinutes:5},first.when,first.end,()=>.5);
 assert.equal(next.start,first.end);assert(next.when>=next.start&&next.when<next.start+60000);
});
pass('Première minute expirée : nouveau départ sans rattrapage',()=>{
 const end=env.now-120000;const next=c.dynamicPlan({intervalMinutes:5},env.now,end,()=>0);
 assert.equal(next.start,env.now+30000);assert(next.when>=next.start);
});
let plan=structuredClone(env.store.plannedWindow);
env.now=plan.when;
env.events.alarm({name:'vine-random',scheduledTime:plan.when});await vm.runInContext('queue',c);
pass('Alarme dans la première minute : une seule lecture et prochaine tranche programmée',()=>{
 assert.equal(env.reloads,1);assert.equal(env.store.plannedWindow.start,plan.end);assert.equal(env.alarms.get('vine-random').periodInMinutes,undefined);
});
env.events.alarm({name:'vine-random',scheduledTime:plan.when});await vm.runInContext('queue',c);
pass('Ancienne alarme dupliquée ignorée',()=>assert.equal(env.reloads,1));
plan=structuredClone(env.store.plannedWindow);env.now=plan.start+60000;
env.events.alarm({name:'vine-random',scheduledTime:plan.when});await vm.runInContext('queue',c);
pass('Alarme retardée après la première minute : aucune lecture',()=>{
 assert.equal(env.reloads,1);assert(env.store.status.includes('ignoré'));assert.equal(env.store.plannedWindow.start,plan.end);
});
const existing=structuredClone(env.store.plannedWindow);env.alarms.clear();
await vm.runInContext('reconcile()',c);
pass('Réveil du worker : plan futur conservé sans nouveau tirage',()=>assert.equal(env.store.plannedWindow.when,existing.when));
let r=await msg('saveInterval',{intervalMinutes:7});
pass('Nouvelle base sauvegardée, durée dans 6/7/8 et historique conservé',()=>{
 assert(r.ok);assert.equal(env.store.intervalMinutes,7);assert([6,7,8].includes(env.store.plannedWindow.durationMinutes));assert.equal(env.store.seen.length,1);
});
for(const value of [0,1.5,1441,'5']){r=await msg('saveInterval',{intervalMinutes:value});assert(!r.ok);assert.equal(env.store.intervalMinutes,7);}
results.push('Valeurs de base invalides refusées');
env.now=new Date(2026,9,17,12,0).getTime();
await msg('saveHours',{hoursEnabled:true,hoursStart:'22:00',hoursEnd:'06:00'});
pass('Hors plage : prochaine première minute dans les heures autorisées',()=>{const p=env.store.plannedWindow;assert(c.timeAllowed(env.store,p.when));assert(p.when<p.start+60000);});
await msg('toggle');await msg('saveInterval',{intervalMinutes:5});
pass('Désactivation : réglage sauvegardé sans alarme',()=>{assert.equal(env.alarms.size,0);assert.equal(env.store.intervalMinutes,5);});
pass('Lien Vine toujours présent dans les alertes',()=>assert(files['background.js'].includes("'\\n\\nOuvrir Amazon Vine : '+Vine.url")));
export default results;
