const {readFileSync}=require('fs'),vm=require('vm'),assert=require('assert');
const html=readFileSync('frontend/index.html','utf8');
const start=html.indexOf('    (async function cloudRestore(){');
const end=html.indexOf('\n    })();',start)+10;
let finishFetch, saved=0, prompted=0;
const local={sessions:[{id:'local',msgs:[]}],diary:{},meta:{},activeId:'local'};
const ctx={DB:local,cloudState:'pending',cloudRevision:null,cloudUnsynced:()=>true,
 setCloudUnsynced:()=>{},showToast:()=>{},window:{confirm:()=>{prompted++;return false}},
 fetch:()=>new Promise(r=>finishFetch=r),localStorage:{setItem:()=>saved++},
 setTimeout,normalizeDB:()=>{},profileId:()=>{},newSession:()=>{},renderSession:()=>{}};
vm.createContext(ctx);vm.runInContext(html.slice(start,end),ctx);
local.sessions[0].msgs.push('new local message');
finishFetch({json:async()=>({revision:'server-v1',data:{sessions:[{id:'cloud',msgs:['old']}]}})});
setImmediate(()=>{try{assert.equal(prompted,1);assert.equal(ctx.cloudState,'error');assert.equal(local.sessions[0].msgs[0],'new local message');assert.equal(saved,0);console.log('delayed cloud restore regression passed');}catch(e){console.error(e);process.exitCode=1}});
