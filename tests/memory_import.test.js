const fs=require('fs'),vm=require('vm'),assert=require('assert');const h=fs.readFileSync('frontend/index.html','utf8');
const start=h.indexOf('    async function memImport('),end=h.indexOf('\n    /* ---- 对话展示',start);const calls=[];
const ctx={memPost:async body=>(calls.push(body),{ok:true}),fetch:()=>{throw Error('merge must not pre-read memory')}};
vm.createContext(ctx);vm.runInContext(h.slice(start,end)+'\nthis.run=memImport',ctx);
(async()=>{const item={id:'memory1',text:'backup fact',cat:'pref',imp:5,pinned:true};await ctx.run({memory_v2:[item]},false);assert.equal(calls[0].action,'merge');assert(calls[0].items[0].pinned);await ctx.run({memory:['legacy']},true);assert.equal(calls[1].action,'replace');
const count=calls.length;assert.equal(await ctx.run({memory_status:{available:false},memory:[]},true),false);assert.equal(calls.length,count);
await ctx.run({memory_status:{available:true},memory:[]},true);assert.equal(calls[2].action,'replace');assert.equal(calls[2].items.length,0);console.log('memory import uses atomic merge without a destructive pre-read passed')})().catch(e=>{console.error(e);process.exitCode=1});
