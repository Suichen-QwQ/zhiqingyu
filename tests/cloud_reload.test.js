const fs=require('fs'),vm=require('vm'),assert=require('assert');const html=fs.readFileSync('frontend/index.html','utf8');
const start=html.indexOf('  function dbLoad(){'),end=html.indexOf('   function dbReset(){',start);
const raw=JSON.stringify({v:2,sessions:[{id:'saved',msgs:[{id:'m',text:'unsynced'}]}],diary:{},meta:{}});
const map=new Map([['old-pending',raw]]),db={};
const ctx={DB:db,SCHEMA:2,cloudPendingKey:'new-pending',cloudRecoveryKey:'old-pending',normalizeDB:()=>{},newSession:()=>{throw Error('unexpected reset')},
 localStorage:{getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)}};
vm.createContext(ctx);vm.runInContext(html.slice(start,end)+'\ndbLoad();',ctx);
assert.equal(db.sessions[0].msgs[0].text,'unsynced');assert.equal(map.get('new-pending'),raw);assert(!map.has('old-pending'));
console.log('refresh pending snapshot transfer regression passed');
