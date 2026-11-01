const fs=require('fs'),vm=require('vm'),assert=require('assert');const h=fs.readFileSync('frontend/index.html','utf8');const start=h.indexOf('    function mergeBackupData('),end=h.indexOf('    function selectBackupData(',start);const ctx={};vm.createContext(ctx);vm.runInContext(h.slice(start,end)+'\nthis.merge=mergeBackupData',ctx);
const incoming=JSON.parse('{"sessions":[],"diary":{"__proto__":{"manual":"pollution"},"constructor":{"items":[]},"2026-11-01":{"manual":"valid"}},"meta":{"__proto__":{"polluted":true},"persona":{"name":"valid"}}}');
const merged=ctx.merge({sessions:[],diary:{},meta:{}},incoming,()=> 'copy');
assert.equal(vm.runInContext('Object.prototype.manual',ctx),undefined);assert.equal(merged.meta.polluted,undefined);assert.equal(merged.diary['2026-11-01'].manual,'valid');assert.equal(Object.keys(merged.diary).length,1);
const nStart=h.indexOf('  function normalizeDB(){'),nEnd=h.indexOf('  function dbLoad(){',nStart);
ctx.DB={sessions:[[],{id:'__proto__',msgs:[]},{id:'constructor',msgs:[]},{id:'constructor',msgs:[]}],diary:{},meta:{}};
vm.runInContext(h.slice(nStart,nEnd)+'\nnormalizeDB();',ctx);
assert.equal(ctx.DB.sessions.length,2);assert.equal(ctx.DB.sessions[0].id,'__proto__');assert.equal(ctx.DB.sessions[1].id,'constructor');
console.log('hostile backup keys cannot mutate prototypes and session identity filtering is safe passed');
