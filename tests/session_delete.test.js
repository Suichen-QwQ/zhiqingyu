const fs=require('fs'),vm=require('vm'),assert=require('assert');const h=fs.readFileSync('frontend/index.html','utf8');
const start=h.indexOf('  function delMsg('),end=h.indexOf("  msgsBox.addEventListener('click'",start);
let canceled=0;const session={id:'s',msgs:[{id:'q',role:'me'},{id:'emote',role:'me',type:'emote'},{id:'reply',role:'ai',replyTo:'q'}]},DB={activeId:'s'};
Object.defineProperty(DB,'msgs',{get:()=>session.msgs,set:v=>session.msgs=v});
const ctx={DB,window:{zqyCancelChat:id=>{assert.equal(id,'s');canceled++}},dbSave:()=>{},renderMsgs:()=>{},renderLive:()=>{},renderCal:()=>{},refreshStats:()=>{},showToast:()=>{}};
vm.createContext(ctx);vm.runInContext(h.slice(start,end)+'\ndelMsg("q");',ctx);
assert.equal(session.msgs.length,1);assert.equal(session.msgs[0].id,'emote');assert.equal(canceled,1);console.log('deletion stops generation and removes linked replies across intervening messages passed');
