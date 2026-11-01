const fs=require('fs'),vm=require('vm'),assert=require('assert');const h=fs.readFileSync('frontend/index.html','utf8');
const start=h.indexOf('  function diarySourceTexts('),end=h.indexOf('  window.zqyGenDiary=',start);
async function run(change){let finish,ensureCalls=0,saves=0;const DB={sessions:[{msgs:[{role:'ai',text:'reply',ts:2},{role:'me',text:'question',ts:1}]}],diary:{}};
const ctx={DB,diaryGenerating:new Set(),tsKey:()=> 'day',zqyConfirm:async()=>true,document:{querySelectorAll:()=>[],querySelector:()=>null},
fetch:()=>new Promise(r=>finish=r),ensureDay:k=>(ensureCalls++,DB.diary[k]||(DB.diary[k]={})),dbSave:()=>saves++,showDiaryDay:()=>{},renderCal:()=>{},labelOf:k=>k,showToast:()=>{},partnerName:()=> 'test'};
vm.createContext(ctx);vm.runInContext(h.slice(start,end)+'\nthis.run=genDiary;this.source=diarySourceTexts',ctx);
assert.equal(ctx.source('day')[0].text,'question');const task=ctx.run('day');change(DB);finish({json:async()=>({narrative:'generated from old chat'})});await task;return {DB,ensureCalls,saves};}
(async()=>{const cleared=await run(DB=>{DB.sessions=[];DB.diary={}});assert.equal(cleared.ensureCalls,0);assert.equal(cleared.saves,0);assert.deepEqual(Object.keys(cleared.DB.diary),[]);
const deleted=await run(DB=>DB.sessions[0].msgs.pop());assert.equal(deleted.saves,0);
const normal=await run(()=>{});assert.equal(normal.saves,1);assert.equal(normal.DB.diary.day.narrative,'generated from old chat');console.log('stale diary response after reset or conversation change is rejected passed');})().catch(e=>{console.error(e);process.exitCode=1});
