
import fs from 'node:fs/promises';import vm from 'node:vm';import assert from 'node:assert/strict';
const files={};for(const n of ['core.js','extract.js','telegram.js','background.js'])files[n]=await fs.readFile(new URL(n,import.meta.url),'utf8');
const results=[];const pass=(n,f)=>{f();results.push(n);};
async function harness(){
 const e={now:new Date(2026,9,17,10).getTime(),s:{scheduleVersion:4,enabled:true},events:{},created:[],reloads:[],tabs:[],fail:false,read:0};
 class Clock extends Date{constructor(...args){super(...(args.length?args:[e.now]));}static now(){return e.now;}}
 const ev=n=>({addListener:f=>e.events[n]=f});
 const chrome={storage:{local:{get:async()=>structuredClone(e.s),set:async x=>Object.assign(e.s,structuredClone(x)),setAccessLevel:async()=>{}}},
 alarms:{get:async()=>({}),create:async()=>{},clear:async()=>{},onAlarm:ev('alarm')},
 windows:{getLastFocused:async options=>{assert.equal(options.windowTypes[0],'normal');if(e.fail)throw Error('Aucune fenêtre');return{id:42};}},
 tabs:{query:async()=>e.tabs,create:async options=>{e.created.push(options);const tab={...options,id:99,status:'loading'};e.tabs.push(tab);return tab;},reload:async id=>e.reloads.push(id),get:async id=>e.tabs.find(t=>t.id===id),onUpdated:ev('updated'),onRemoved:ev('removed')},
 scripting:{executeScript:async()=>{e.read++;return[{result:{items:[{id:'B000000001',title:'Un'}]}}];}},
 notifications:{create:async()=>{},onClicked:ev('clicked')},runtime:{id:'test',onStartup:ev('startup'),onInstalled:ev('install'),onMessage:ev('message')}};
 const c=vm.createContext({chrome,URL,Date:Clock,Math,Set,AbortSignal,console,setTimeout,clearTimeout});
 c.importScripts=(...ns)=>ns.forEach(n=>vm.runInContext(files[n],c));vm.runInContext(files['background.js'],c);await vm.runInContext('queue',c);
 e.c=c;e.plan=()=>({start:e.now,end:e.now+300000,when:e.now,durationMinutes:5});return e;
}
let e=await harness();e.c.plan=e.plan();await vm.runInContext('check(plan)',e.c);
pass('Sans onglet Vine : création index 0, fenêtre normale, arrière-plan',()=>{assert.equal(e.created.length,1);assert.equal(e.created[0].index,0);assert.equal(e.created[0].windowId,42);assert.equal(e.created[0].active,false);assert.equal(e.created[0].url,'https://www.amazon.fr/vine/vine-items?queue=potluck');assert.equal(e.s.pending.tabId,99);assert.equal(e.reloads.length,0);});
e.events.updated(99,{status:'complete'});await vm.runInContext('queue',e.c);
pass('Fin de chargement du nouvel onglet : lecture et référence silencieuse',()=>{assert.equal(e.read,1);assert(e.s.initialized);assert.equal(e.s.pending,null);});
e=await harness();e.tabs=[{id:5,index:2,url:'https://www.amazon.fr/vine/vine-items?queue=potluck'}];e.c.plan=e.plan();await vm.runInContext('check(plan)',e.c);
pass('Vine déjà au troisième onglet : réutilisation sans création',()=>{assert.equal(e.created.length,0);assert.equal(e.reloads[0],5);});
e=await harness();e.tabs=[{id:5,url:'https://www.amazon.fr/gp/cart/view.html'}];e.c.plan=e.plan();await vm.runInContext('check(plan)',e.c);
pass('Autre page Amazon : création de Vine sans modifier l’autre page',()=>{assert.equal(e.created.length,1);assert.equal(e.tabs[0].url,'https://www.amazon.fr/gp/cart/view.html');});
e=await harness();e.s.hoursEnabled=true;e.s.hoursStart='22:00';e.s.hoursEnd='06:00';e.c.plan=e.plan();await vm.runInContext('check(plan)',e.c);
pass('Hors horaires : aucune ouverture',()=>assert.equal(e.created.length,0));
e=await harness();e.s.enabled=false;e.c.plan=e.plan();await vm.runInContext('check(plan)',e.c);
pass('Surveillance désactivée : aucune ouverture',()=>assert.equal(e.created.length,0));
e=await harness();e.c.plan={start:e.now-60000};await vm.runInContext('check(plan)',e.c);
pass('Première minute dépassée : aucune ouverture',()=>assert.equal(e.created.length,0));
e=await harness();e.fail=true;e.c.plan=e.plan();await vm.runInContext('check(plan)',e.c);
pass('Échec ouverture : erreur lisible et aucune attente bloquée',()=>{assert.equal(e.s.pending,null);assert(e.s.error.includes('fenêtre Chrome normale'));});
export default results;
