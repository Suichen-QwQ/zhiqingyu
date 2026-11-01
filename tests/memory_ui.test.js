const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('frontend/index.html','utf8');
function section(start,end){const a=html.indexOf(start);assert(a>=0,start);const b=html.indexOf(end,a);assert(b>a,end);return html.slice(a,b);}
function element(tag){return {tag,children:[],listeners:{},disabled:false,value:'',appendChild(child){this.children.push(child)},addEventListener(type,fn){this.listeners[type]=fn},setAttribute(){},focus(){},setSelectionRange(){}};}
function setup(){let profile='one';const calls=[],toasts=[];const ctx={profileId:()=>profile,showToast:s=>toasts.push(s),loadMem:()=>{},memPost:async b=>(calls.push(b),{ok:false,net:false}),zqyConfirm:async()=>true,document:{createElement:element},memIcon:()=>element('button'),MEM_CATS:[],MEM_OK:'',MEM_X:'',MEM_ROWS:[],MEM_V2:[],MEM_ITEMS:[]};vm.createContext(ctx);vm.runInContext(section('    function memCheckProfile(', '    function memCountText('),ctx);return {ctx,calls,toasts,switchProfile:p=>profile=p};}
async function actions(){
 const {ctx,calls,switchProfile}=setup();const r={v2:true,profile_id:'one',id:'gone',idx:0,text:'original',cat:'pref',imp:3};
 await ctx.memDelete(r);assert.equal(calls.length,1);assert.equal(calls[0].id,'gone');assert(!('index' in calls[0]));
 const row=element('div');ctx.memEdit(row,r);row.children[0].children[0].value='updated';await row.children[1].children[0].listeners.click();
 assert.equal(calls.length,2);assert.equal(calls[1].action,'update');assert(!calls.some(x=>x.action==='replace'));
 let confirm;ctx.zqyConfirm=()=>new Promise(r=>confirm=r);const deletion=ctx.memDelete(r);switchProfile('two');confirm(true);await deletion;assert.equal(calls.length,2,'confirmation must not target a newly selected profile');
 const legacy={v2:false,profile_id:'two',idx:0,text:'old',created:'',expected_items:['old','retained']};
 const legacyRow=element('div');ctx.memEdit(legacyRow,legacy);legacyRow.children[0].children[0].value='new';await legacyRow.children[1].children[0].listeners.click();
 assert.equal(calls.length,3);assert.equal(calls[2].profile_id,'two');assert.deepEqual(Array.from(calls[2].expected_items),['old','retained']);assert.deepEqual(Array.from(calls[2].items),['new','retained']);
 ctx.zqyConfirm=async()=>true;await ctx.memDelete(legacy);assert.deepEqual(Array.from(calls[3].expected_items),['old','retained']);
}
async function clearAndAdd(){
 let profile='one',confirm,finish;const calls=[];const clear=element('button'),input=element('input'),go=element('button');
 const ctx={profileId:()=>profile,memClear:clear,memAddIn:input,memAddGo:go,document:{getElementById:id=>id==='memAddIn'?input:go},zqyConfirm:()=>new Promise(r=>confirm=r),memCheckProfile:r=>r.profile_id===profile,memPost:async b=>(calls.push(b),{ok:true}),showToast:()=>{},loadMem:()=>{}};
 vm.createContext(ctx);vm.runInContext(section("    if(memClear) memClear.addEventListener(","    if(memAddGo) memAddGo.addEventListener("),ctx);
 const clearing=clear.listeners.click();profile='two';confirm(true);await clearing;assert.equal(calls.length,0);
 ctx.memPost=b=>(calls.push(b),new Promise(r=>finish=r));input.value='first fact';const adding=ctx.memAdd();input.value='next fact';finish({ok:true});await adding;
 assert.equal(input.value,'next fact');assert.equal(calls[0].profile_id,'two');
}
async function loads(){
 let profile='one';const pending=[],painted=[];const list=element('div');const ctx={memList:list,memCount:element('span'),MEM_LOAD_SEQ:0,MEM_ITEMS:[],MEM_V2:[],MEM_ROWS:[],MEM_STATS:null,profileId:()=>profile,document:{createElement:element},fetch:()=>new Promise(resolve=>pending.push(resolve)),memBuildRows:(data,p)=>({rows:[{profile_id:p,text:data.items[0]}],items:data.items,v2:[]}),memPaint:()=>painted.push(ctx.MEM_ROWS[0])};
 vm.createContext(ctx);vm.runInContext(section('    async function loadMem(){','    if(memSearch)'),ctx);
 const first=ctx.loadMem();profile='two';const second=ctx.loadMem();pending[1]({ok:true,json:async()=>({items:['new']})});await second;pending[0]({ok:true,json:async()=>({items:['old']})});await first;
 assert.deepEqual(painted,[{profile_id:'two',text:'new'}]);
 const changed=ctx.loadMem();profile='three';pending[2]({ok:true,json:async()=>({items:['wrong profile']})});await changed;assert.equal(painted.length,1);
 const failed=ctx.loadMem();pending[3]({ok:false,json:async()=>({error:'unavailable'})});await failed;assert.equal(painted.length,1);assert(list.children.at(-1).textContent.includes('读取失败'));
}
(async()=>{await actions();await clearAndAdd();await loads();console.log('Memory actions keep stable targets and reject stale profile/list results');})().catch(e=>{console.error(e);process.exitCode=1});
