const fs=require('fs'),vm=require('vm'),assert=require('assert');const html=fs.readFileSync('frontend/index.html','utf8');
function extract(a,b){const start=html.indexOf(a),end=html.indexOf(b,start);assert(start>=0&&end>start);return html.slice(start,end);}
async function check(failMemory){
 let finish,task,persisted=0,refreshed=0,syncs=0,blocked=0;const notices=[],button={addEventListener(_,fn){this.click=fn}};
 const backup={db:{sessions:[{id:'restored',msgs:[]}],activeId:'restored',diary:{},meta:{}}};const DB={sessions:[{id:'old'}],diary:{},meta:{}};
 const ctx={DB,cloudBusy:false,cloudState:'restored',cloudGeneration:1,cloudSavedGeneration:1,cloudT:null,showToast:m=>notices.push(m),clearTimeout(){},window:{prompt(){}},selectBackupData:b=>({data:b.db,primary:true}),zqyConfirm:async()=>true,normalizeDB(){},profileId:()=> 'p',uid:()=> 'id',newSession(){throw Error('unexpected empty restore')},dbSave:()=>ctx.cloudGeneration++,persistLocalSnapshot:()=>persisted++,refreshView:()=>refreshed++,cloudSync:()=>syncs++,memImport:()=>{assert.equal(persisted,1);assert.equal(refreshed,1);assert(ctx.cloudBusy);return new Promise((resolve,reject)=>finish=()=>failMemory?reject(Error('offline')):resolve(true));},
 document:{getElementById:()=>button,createElement:()=>({files:[{}],addEventListener(_,fn){this.change=fn},click(){this.change()}})},FileReader:class{readAsText(){this.result=JSON.stringify(backup);task=this.onload();}}};
 vm.createContext(ctx);vm.runInContext(extract("    const bkImport=document.getElementById('bkImport');",'    /* ---- P2 归档包'),ctx);
 button.click();await new Promise(setImmediate);assert.equal(DB.sessions[0].id,'restored');assert.equal(persisted,1);assert.equal(syncs,0);
 const first=task;button.click();await task;assert(notices.some(m=>m.includes('正在同步或导入')));assert.equal(persisted,1,'overlapping imports must not replace local state');
 finish();await first;assert(!ctx.cloudBusy);assert.equal(syncs,1);assert.equal(DB.sessions[0].id,'restored');
 if(failMemory)assert(notices.some(m=>m.includes('后续处理未完成')));
}
(async()=>{await check(false);await check(true);console.log('JSON restore saves local data before awaiting memory and serializes imports');})().catch(e=>{console.error(e);process.exitCode=1});
