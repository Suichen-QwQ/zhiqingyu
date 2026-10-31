const fs=require('fs'),vm=require('vm'),assert=require('assert');const h=fs.readFileSync('frontend/index.html','utf8');const start=h.indexOf('    (async function cloudRestore(){'),end=h.indexOf('\n    })();',start)+10;
const meta={persona:{name:'custom'},user:{name:'saved user'},flags:{tts:true}};const DB={sessions:[],diary:{},meta:{}};
const ctx={window:{},DB,SCHEMA:2,cloudState:'pending',cloudRevision:null,cloudUnsynced:()=>false,
 fetch:async()=>({json:async()=>({revision:'v',data:{sessions:[],diary:{},meta}})}),persistLocalSnapshot:()=>true,
 normalizeDB:()=>{},profileId:()=>{},newSession:()=>DB.sessions.push({id:'new',msgs:[]}),renderSession:()=>{}};
vm.createContext(ctx);vm.runInContext(h.slice(start,end),ctx);
setImmediate(()=>{try{assert.equal(ctx.cloudState,'restored');assert.equal(DB.meta.persona.name,'custom');assert(DB.meta.flags.tts);console.log('cloud settings without chat restoration passed')}catch(e){console.error(e);process.exitCode=1}});
