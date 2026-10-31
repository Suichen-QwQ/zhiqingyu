const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('frontend/index.html','utf8');
const sync=html.slice(html.indexOf("  let cloudState='pending'"),html.indexOf('  function pushDiaryItem('));
const map=new Map();
function tab(id){let timers=[],resolveFetch;const ctx={saveT:null,cloudT:null,snapshot:()=>({sessions:[{id,msgs:[id]}]}),
 sessionStorage:{getItem:()=>id,setItem:()=>{}},localStorage:{get length(){return map.size},key:i=>[...map.keys()][i],getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)},
 setTimeout:f=>(timers.push(f),f),clearTimeout:f=>timers=timers.filter(x=>x!==f),showToast:()=>{},fetch:()=>new Promise(r=>resolveFetch=r)};
 vm.createContext(ctx);vm.runInContext(sync+'\nthis.api={save:dbSave,sync:cloudSync,records:cloudPendingRecords,ready:()=>{cloudState="restored";cloudTracking=true;}}',ctx);
 return {ctx,run:()=>timers.shift()(),finish:r=>resolveFetch(r)};}
(async()=>{
 const a=tab('a'),b=tab('b');a.ctx.api.ready();b.ctx.api.ready();
 a.ctx.api.save();a.run();let pending=a.run();b.ctx.api.save();
 a.finish({ok:true,json:async()=>({ok:true,revision:'next'})});await pending;
 assert(!map.has('zqy-pending-a'));assert(map.has('zqy-pending-b'));
 assert.equal(JSON.parse(map.get('zqy-pending-b')).sessions[0].msgs[0],'b');
 console.log('multiple tab pending snapshots regression passed');
 const start=html.indexOf('    (async function cloudRestore(){'),end=html.indexOf('\n    })();',start)+10;
 const db={sessions:[{id:'empty',msgs:[]}],diary:{},meta:{}};
 let rendered=0;
 const ctx={DB:db,cloudState:'pending',cloudRevision:null,cloudUnsynced:()=>false,cloudSync:()=>{},
 fetch:async()=>({json:async()=>({revision:'v',data:{sessions:[],diary:{'2026-10-31':{manual:'valuable diary'}}}})}),
 window:{},localStorage:{setItem:()=>{}},normalizeDB:()=>{},profileId:()=>{},newSession:()=>db.sessions.push({id:'new',msgs:[]}),renderSession:()=>rendered++};
 vm.createContext(ctx);vm.runInContext(html.slice(start,end),ctx);await new Promise(setImmediate);
 assert.equal(db.diary['2026-10-31'].manual,'valuable diary');assert.equal(ctx.cloudState,'restored');assert.equal(rendered,1);
 console.log('diary without sessions restoration regression passed');
})().catch(e=>{console.error(e);process.exitCode=1});
