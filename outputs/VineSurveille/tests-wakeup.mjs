
import fs from 'node:fs/promises';import vm from 'node:vm';import assert from 'node:assert/strict';
const files={};for(const n of ['core.js','extract.js','telegram.js','background.js'])files[n]=await fs.readFile(new URL(n,import.meta.url),'utf8');
const results=[];
const at=(h,m,s=0)=>new Date(2026,9,17,h,m,s).getTime();
const plan={start:at(10,37,26),end:at(10,42,26),durationMinutes:5,when:at(10,37,50)};
async function boot({now=plan.when,window=plan,existing=null,consumed=null}={}){
 const e={now,store:{enabled:true,scheduleVersion:4,intervalMinutes:5,hoursEnabled:true,hoursStart:'06:00',hoursEnd:'22:00',plannedWindow:structuredClone(window),lastConsumedWhen:consumed},alarm:existing,events:{},reloads:[],created:[]};
 class Clock extends Date{constructor(...args){super(...(args.length?args:[e.now]));}static now(){return e.now;}}
 const ev=n=>({addListener:f=>e.events[n]=f});
 const chrome={storage:{local:{get:async()=>structuredClone(e.store),set:async x=>Object.assign(e.store,structuredClone(x)),setAccessLevel:async()=>{}}},
 alarms:{get:async()=>e.alarm,create:async(n,x)=>{e.alarm={name:n,scheduledTime:x.when};e.created.push(x);},clear:async()=>{e.alarm=null;},onAlarm:ev('alarm')},
 tabs:{query:async()=>[{id:7,url:'https://www.amazon.fr/vine/vine-items?queue=potluck'}],reload:async id=>e.reloads.push({id,at:e.now}),onUpdated:ev('updated'),onRemoved:ev('removed')},
 notifications:{onClicked:ev('click')},runtime:{id:'test',onStartup:ev('startup'),onInstalled:ev('install'),onMessage:ev('message')}};
 const c=vm.createContext({chrome,URL,Date:Clock,Math,Set,AbortSignal,console,setTimeout,clearTimeout});
 c.importScripts=(...names)=>names.forEach(n=>vm.runInContext(files[n],c));vm.runInContext(files['background.js'],c);
 e.c=c;return e;
}
let e=await boot();
// Chrome a retiré l’alarme ponctuelle, puis réveille le worker et livre l’événement.
e.events.alarm({name:'vine-random',scheduledTime:plan.when});
await vm.runInContext('queue',e.c);
assert.equal(e.reloads.length,1,'Le réveil ne doit pas remplacer une alarme due avant son traitement');
assert.equal(e.store.plannedWindow.start,plan.end);
results.push('Réveil du worker avec alarme due : un contrôle et une seule avance de tranche');

e=await boot({existing:{name:'vine-random',scheduledTime:plan.when}});
e.events.alarm({name:'vine-random',scheduledTime:plan.when});await vm.runInContext('queue',e.c);
assert.equal(e.reloads.length,1);assert.equal(e.store.plannedWindow.start,plan.end);
results.push('Alarme encore présente au réveil : un seul traitement');
e=await boot({now:plan.when-10000});await vm.runInContext('queue',e.c);
assert.equal(e.reloads.length,0);assert.equal(e.store.plannedWindow.when,plan.when);assert.equal(e.alarm.scheduledTime,plan.when);
results.push('Alarme absente à dix secondes de l’échéance : même tranche, aucun saut');
e=await boot({now:plan.start+80000});e.events.alarm({name:'vine-random',scheduledTime:plan.when});await vm.runInContext('queue',e.c);
assert.equal(e.reloads.length,0);assert.equal(e.store.plannedWindow.start,plan.end);assert(e.store.scheduleLog.some(x=>x.message.includes('ignoré')));
results.push('Première minute expirée : un seul saut explicitement journalisé');
e=await boot({consumed:plan.when});e.events.alarm({name:'vine-random',scheduledTime:plan.when});await vm.runInContext('queue',e.c);
assert.equal(e.reloads.length,0);assert.equal(e.store.plannedWindow.start,plan.end);
results.push('Tranche déjà marquée avant interruption : aucun doublon');
let current=plan;
for(let i=0;i<60;i++){
 e=await boot({now:current.when,window:current});
 e.events.alarm({name:'vine-random',scheduledTime:current.when});await vm.runInContext('queue',e.c);
 assert.equal(e.reloads.length,1);assert.equal(e.store.plannedWindow.start,current.end);
 assert([4,5,6].includes(e.store.plannedWindow.durationMinutes));
 assert(e.store.plannedWindow.when>=e.store.plannedWindow.start&&e.store.plannedWindow.when<e.store.plannedWindow.start+60000);
 const previous=current;current=structuredClone(e.store.plannedWindow);
 assert(current.when-previous.when<7*60000);
}
results.push('60 réveils avec base 5 et horaires 06:00–22:00 : aucun contrôle sauté ni écart de dix minutes');
export default results;

