const fs=require('fs'),vm=require('vm'),assert=require('assert');const html=fs.readFileSync('frontend/index.html','utf8');
function section(a,b){const start=html.indexOf(a),end=html.indexOf(b,start);assert(start>=0&&end>start);return html.slice(start,end)}
async function voice(){
 let resolveMic,stopped=0,sent=0;const session={id:'one'},diary={};const notices=[];const ctx={voiceEpoch:1,voiceTarget:{epoch:1,session,diary,input:'draft'},DB:{sessions:[session],diary},curSess:()=>session,ta:{value:'draft',dispatchEvent(){}},sendMsg:()=>sent++,showToast:s=>notices.push(s),Event:class{},pressing:true,window:{isSecureContext:true,AudioContext:class{constructor(){throw Error('must not allocate a late stream')}}},navigator:{mediaDevices:{getUserMedia:()=>new Promise(r=>resolveMic=r)}},finalText:'',interimText:'',azRetry:false,voiceIssue(){},az:null,setTimeout(){}};
 vm.createContext(ctx);vm.runInContext(section('    function commitSend(', '    function pressStart('),ctx);ctx.commitSend('spoken');assert.equal(sent,1);
 ctx.ta.value='new draft';ctx.commitSend('old transcript');assert.equal(sent,1);assert.equal(ctx.ta.value,'new draft');
 ctx.ta.value='draft';ctx.voiceEpoch++;ctx.commitSend('stale transcript');assert.equal(sent,1);
 vm.runInContext(section('    function startAzure(){','    function stopAzure(){'),ctx);ctx.startAzure();ctx.pressing=false;resolveMic({getTracks:()=>[{stop:()=>stopped++}]});await new Promise(setImmediate);assert.equal(stopped,1);assert.equal(ctx.az,null);
}
async function model(){
 let finish;const field=value=>({value});const ctx={mdUrl:field('old'),mdModel:field('old-model'),mdReason:field('reason'),mdTimeout:field('60'),mdKey:field(''),mdEditing:false,mdClear:false,fbCollect:()=>[],fbRender(){throw Error('stale load must not render')},fetch:()=>new Promise(resolve=>finish=resolve),mdStatus(){},setModelChoices(){},mdKeyEye:{},mdPaintKey(){},mdMarkPreset(){},MD:{},MD_PH:'',MD_EYE:''};
 vm.createContext(ctx);vm.runInContext(section('    let modelLoadSeq=0,modelSaving=false;', '    async function mdProbe('),ctx);const pending=ctx.loadModel();ctx.mdKey.value='new unsaved fake key';ctx.mdModel.value='new unsaved model';finish({ok:true,json:async()=>({base_url:'server',model:'server-model'})});await pending;assert.equal(ctx.mdModel.value,'new unsaved model');assert.equal(ctx.mdKey.value,'new unsaved fake key');
 const button={disabled:false,addEventListener(_,fn){this.save=fn}};ctx.document={getElementById:()=>button};ctx.showToast=()=>{};ctx.mdUrl.value='https://example.test/v1';ctx.mdModel.value='test';ctx.mdTimeout.value='60';ctx.mdPaintKey=()=>{throw Error('a stale save must preserve newly typed credentials')};
 vm.runInContext(section("    const mdSave=document.getElementById('mdSave');",'    /* ---- 备用模型'),ctx);const saving=button.save();ctx.mdKey.value='newer unsaved fake key';finish({ok:true,json:async()=>({model:'saved'})});await saving;assert.equal(ctx.mdKey.value,'newer unsaved fake key');assert(!button.disabled);

}
(async()=>{await voice();await model();console.log('Voice results cannot replace newer input; delayed microphones close; model loads preserve unsaved edits')})().catch(e=>{console.error(e);process.exitCode=1});
