const {readFileSync} = require('fs');
const vm = require('vm');
const assert = require('assert');
const html = readFileSync('frontend/index.html', 'utf8');
const code = html.slice(html.indexOf("  let cloudState='pending'"), html.indexOf('  function pushDiaryItem('));
let timers = [], map = new Map(), notifications = [], writes = [], resolveFetch;
const ctx = {saveT:null, cloudT:null, snapshot:()=>({sessions:[{msgs:['local']}]}),
  localStorage:{getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)},
  setTimeout:(f)=>{timers.push(f);return f},clearTimeout:(f)=>{timers=timers.filter(x=>x!==f)},
  showToast:x=>notifications.push(x),
  fetch:(url,opts)=>{writes.push(JSON.parse(opts.body));return new Promise(r=>resolveFetch=r)}};
vm.createContext(ctx);
vm.runInContext(code + `\nthis.api={dbSave,cloudSync, state:()=>cloudState, setState:(s,r)=>{cloudState=s;cloudRevision=r;cloudTracking=true}, busy:()=>cloudBusy};`,ctx);
(async()=>{
 ctx.api.setState('pending',null);ctx.api.dbSave();assert.equal(map.get('zqy-cloud-unsynced'),'1');
 timers.shift()();assert.equal(writes.length,0);
 ctx.api.setState('restored','v1');ctx.api.cloudSync();let pending=timers.shift()();
 assert.equal(writes[0].expected_revision,'v1');
 ctx.api.dbSave();timers.shift()();assert.equal(writes.length,1);
 resolveFetch({ok:true,json:async()=>({ok:true,revision:'v2'})});await pending;
 assert.equal(map.get('zqy-cloud-unsynced'),'1');
 pending=timers.shift()();assert.equal(writes[1].expected_revision,'v2');
 resolveFetch({ok:false,status:409,json:async()=>({ok:false})});await pending;
 assert.equal(ctx.api.state(),'error');assert.equal(map.get('zqy-cloud-unsynced'),'1');
 assert(notifications.some(x=>x.includes('已保留')));console.log('cloud synchronization regression passed');
})().catch(e=>{console.error(e);process.exitCode=1});
