const fs=require('fs'),vm=require('vm'),assert=require('assert');const h=fs.readFileSync('frontend/index.html','utf8');const source=h.slice(h.indexOf("  let cloudState='pending'"),h.indexOf('  function pushDiaryItem('));
async function check(allowPending){let timers=[],notices=[],unload;const map=new Map();
 const ctx={saveT:null,cloudT:null,snapshot:()=>({sessions:[{msgs:['new message']}]}),sessionStorage:{getItem:()=>null,setItem:()=>{}},
 localStorage:{get length(){return map.size},key:i=>[...map.keys()][i],getItem:k=>map.get(k)||null,setItem:(k,v)=>{if(allowPending&&k.startsWith('zqy-pending-'))map.set(k,v);else throw Error('QuotaExceededError')},removeItem:k=>map.delete(k)},
 window:{addEventListener:(name,f)=>unload=f},setTimeout:f=>(timers.push(f),f),clearTimeout:f=>timers=timers.filter(x=>x!==f),showToast:x=>notices.push(x),fetch:async()=>{throw Error('offline')}};
 vm.createContext(ctx);vm.runInContext(source+'\nthis.api={save:dbSave,unsynced:cloudUnsynced,ready:()=>{cloudState="restored";cloudTracking=true}}',ctx);
 ctx.api.ready();ctx.api.save();timers.shift()();await timers.shift()();assert(ctx.api.unsynced());
 let blocked=false;unload({preventDefault:()=>blocked=true});
 if(allowPending){assert(notices.some(x=>x.includes('本机内容已保留')));assert(!blocked);}
 else {assert(notices.some(x=>x.includes('立即导出备份')));assert(!notices.some(x=>x.includes('本机内容已保留')));assert(blocked);}
}
(async()=>{await check(false);await check(true);console.log('quota failures, accurate persistence messages and unload protection passed')})().catch(e=>{console.error(e);process.exitCode=1});
