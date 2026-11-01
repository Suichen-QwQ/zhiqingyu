const fs=require('fs'),vm=require('vm'),assert=require('assert');const html=fs.readFileSync('frontend/index.html','utf8');
function source(a,b){const start=html.indexOf(a),end=html.indexOf(b,start);assert(start>=0&&end>start,a);return html.slice(start,end);}
function setup(){let profile='one',months=12;const notices=[],elements={};const ctx={profileId:()=>profile,rcMonthsValue:()=>months,showToast:s=>notices.push(s),rcEl:id=>elements[id]||(elements[id]={hidden:false,textContent:''}),window:{zqyRecallReady:true},rcBusy:false,rcData:null,rcLast:null,rcDataContext:null,rcLoadSeq:0,rcMissingSeq:0,rcMissingList:[],rcPaintAll(){},rcPaintMissing(){},rcPaintButtons(){},rcPaintDetail(){},loadRecallMissing(){}};vm.createContext(ctx);vm.runInContext(source('  function rcContext(){','  function rcEl('),ctx);return {ctx,notices,elements,setProfile:p=>profile=p,setMonths:m=>months=m};}
async function loads(){
 const {ctx,setProfile,setMonths}=setup(),pending=[],painted=[];ctx.fetch=url=>new Promise(resolve=>pending.push({url,resolve}));ctx.rcPaintAll=()=>{if(ctx.rcData)painted.push(ctx.rcData.shared)};
 vm.runInContext(source('  async function loadRecall(){','  /* ==== 缺失摘要检测'),ctx);
 const a=ctx.loadRecall();setProfile('two');const b=ctx.loadRecall();pending[1].resolve({ok:true,json:async()=>({ok:true,shared:'two',months:12})});await b;pending[0].resolve({ok:true,json:async()=>({ok:true,shared:'one',months:12})});await a;assert.deepEqual(painted,['two']);assert.equal(ctx.rcDataContext.profile,'two');
 const c=ctx.loadRecall();setMonths(3);const d=ctx.loadRecall();pending[3].resolve({ok:true,json:async()=>({ok:true,shared:'three months',months:3})});await d;pending[2].resolve({ok:true,json:async()=>({ok:true,shared:'twelve months',months:12})});await c;assert.deepEqual(painted,['two','three months']);
 const x=ctx.loadRecall(),y=ctx.loadRecall();pending[5].resolve({ok:true,json:async()=>({ok:true,shared:'latest',months:3})});await y;pending[4].resolve({ok:true,json:async()=>({ok:true,shared:'older',months:3})});await x;assert.equal(ctx.rcData.shared,'latest');
 const missing=[];ctx.rcPaintMissing=data=>missing.push(data.label);vm.runInContext(source('  async function loadRecallMissing(){','  /* 单轮 POST build'),ctx);
 const m1=ctx.loadRecallMissing();setProfile('three');const m2=ctx.loadRecallMissing();pending[7].resolve({ok:true,json:async()=>({ok:true,label:'current missing'})});await m2;pending[6].resolve({ok:true,json:async()=>({ok:true,label:'stale missing'})});await m1;assert.deepEqual(missing,['current missing']);
}
async function builds(change){
 const {ctx,setProfile,setMonths}=setup(),posts=[];let finish,reloads=0;ctx.DB={diary:{old:'diary'}};ctx.rcDaysFromDiary=()=>[{date:'2026-10-01',text:'old profile diary'}];ctx.rcBuildBody=(p,days,m)=>({profile_id:p,days,months:m});ctx.loadRecall=async()=>reloads++;ctx.fetch=async(_,opts)=>{posts.push(JSON.parse(opts.body));return new Promise(resolve=>finish=()=>resolve({status:200,ok:true,json:async()=>({ok:true,pending:1,generated:[{}]})}));};
 vm.runInContext(source('  async function rcRunBatch(opts){','  /* 复制：'),ctx);vm.runInContext(source('  async function rcPostBuild(','  async function rcClear(){'),ctx);
 const task=ctx.rcBuildNow();assert.equal(posts[0].profile_id,'one');if(change==='profile')setProfile('two');else if(change==='months')setMonths(3);else ctx.DB.diary={new:'imported diary'};finish();await task;
 assert.equal(posts.length,1,'a changed context must stop subsequent build rounds');assert.equal(reloads,1);assert.equal(ctx.rcLast,null);assert(!ctx.rcBusy);
}
async function clearAndCopy(){
 const {ctx,setProfile,notices}=setup();let confirm,posts=0,copied=0;ctx.zqyConfirm=()=>new Promise(resolve=>confirm=resolve);ctx.fetch=async()=>{posts++;return {ok:true,json:async()=>({ok:true})}};ctx.loadRecall=async()=>{};ctx.rcCopyText=async()=>{copied++;return true};
 vm.runInContext(source('  async function rcClearFlow(opts){','  /* enabled=false'),ctx);vm.runInContext(source('  async function rcClear(){','  (function rcBind(){'),ctx);
 const task=ctx.rcClear();setProfile('two');confirm(true);await task;assert.equal(posts,0);assert(!ctx.rcBusy);
 ctx.rcData={shared:'old profile private recall'};ctx.rcDataContext={profile:'one',months:12};await ctx.rcCopyShared();assert.equal(copied,0);assert(notices.some(s=>s.includes('刷新回忆')));
}
async function completion(change){
 const {ctx,setProfile}=setup();let read;ctx.DB={diary:{day:'text'}};ctx.rcDaysFromDiary=()=>[{date:'2026-10-01',text:'diary'}];ctx.rcBuildBody=(p,days,m)=>({profile_id:p,days,months:m});
 ctx.fetch=async(url)=>url==='api/recall'?{ok:true,status:200,json:async()=>({ok:true,pending:0,generated:[{}]})}:new Promise(resolve=>read=()=>resolve({ok:true,json:async()=>({ok:true,shared:'built recall',months:12})}));
 vm.runInContext(source('  async function rcRunBatch(opts){','  /* 复制：'),ctx);vm.runInContext(source('  async function loadRecall(){','  /* ==== 缺失摘要检测'),ctx);vm.runInContext(source('  async function rcPostBuild(','  async function rcClear(){'),ctx);
 const task=ctx.rcBuildNow();await new Promise(setImmediate);if(change)setProfile('two');read();await task;
 if(change)assert.equal(ctx.rcLast,null);else assert.equal(ctx.rcLast.generated,1,'initial recall load must retain completed build statistics');
}
async function unavailable(){const {ctx}=setup();ctx.rcData={enabled:true};ctx.rcBuildBody=()=>({});ctx.fetch=async()=>({status:503,ok:false,json:async()=>({ok:false,error_code:'recall_unreadable',error:'Unreadable recall'})});vm.runInContext(source('  async function rcPostBuild(','  async function rcBuildNow(){'),ctx);assert(!(await ctx.rcPostBuild([],12,'one')).ok);assert(ctx.rcData.enabled,'a data error must not disable the feature');}
(async()=>{await loads();for(const change of ['profile','months','diary'])await builds(change);await clearAndCopy();await completion(false);await completion(true);await unavailable();console.log('Recall operations preserve identity, range and request order; stale builds stop');})().catch(e=>{console.error(e);process.exitCode=1});
