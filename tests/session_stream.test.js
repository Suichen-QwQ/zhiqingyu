const fs=require('fs'),vm=require('vm'),assert=require('assert');const html=fs.readFileSync('frontend/index.html','utf8');
const start=html.indexOf('  async function askYu('),end=html.indexOf('  /* ===== 表情包',start);
const cancelStart=html.indexOf('  window.zqyCancelChat=function('),cancelEnd=html.indexOf('  const typingVis=',cancelStart);
const a={id:'a',msgs:[{id:'question',role:'me',text:'hi'}]},b={id:'b',msgs:[]},DB={sessions:[a,b],activeId:'a'};
let abortRead,readCount=0,saved=0;
const el={querySelector:()=>({}),remove:()=>{}};
const ctx={DB,activeRequest:null,window:{},curSess:()=>DB.sessions.find(s=>s.id===DB.activeId),
 typingEl:{querySelector:()=>({}),style:{}},thinkEl:{classList:{remove:()=>{}}},sendEl:{hidden:false},stopEl:{hidden:true},
 profileId:()=> 'p',personaPayload:()=>({name:'test'}),userPayload:()=>({}),toolPayload:()=>({}),consumeTmp:()=>({}),
 uid:()=> 'ai-reply',requestAnimationFrame:f=>f(),scrollChat:()=>{},setTimeout:()=>0,clearTimeout:()=>{},
 AbortController,DOMException,TextDecoder,dbSave:()=>saved++,showToast:()=>{},bubbleEl:()=>el,msgsBox:{insertBefore:()=>{}},appendStreamText:()=>{},
 fetch:async(url,options)=>({ok:true,body:{getReader:()=>({read:()=>{
   if(readCount++===0)return Promise.resolve({done:false,value:new TextEncoder().encode('event: delta\ndata: {"text":"partial"}\n\n')});
   return new Promise((resolve,reject)=>{abortRead=()=>reject(new DOMException('Aborted','AbortError'));options.signal.addEventListener('abort',abortRead);});
 }})}})};
vm.createContext(ctx);vm.runInContext(html.slice(cancelStart,cancelEnd)+html.slice(start,end)+'\nthis.run=askYu',ctx);
(async()=>{const task=ctx.run('hi','question');await new Promise(setImmediate);DB.activeId='b';ctx.window.zqyCancelChat();const newer={sessionId:'b'};ctx.activeRequest=newer;ctx.typingEl.style.display='new-request';await task;
 assert.equal(a.msgs[1].text,'partial');assert.equal(b.msgs.length,0);assert.equal(ctx.activeRequest,newer);assert.equal(ctx.typingEl.style.display,'new-request');assert(saved);console.log('session switch preserves original partial reply and newer request state passed');
 a.msgs=[a.msgs[0]];DB.activeId='a';readCount=0;ctx.activeRequest=null;
 const second=ctx.run('hi','question');await new Promise(setImmediate);
 const detached=a.msgs;a.msgs=a.msgs.slice();ctx.activeRequest.stopped=true;ctx.activeRequest.ctrl.abort();await second;
 assert.equal(a.msgs.length,2);assert.equal(a.msgs[1].text,'partial');assert.equal(detached.length,1);
 console.log('partial reply uses the current message buffer after array replacement passed');
})().catch(e=>{console.error(e);process.exitCode=1});
