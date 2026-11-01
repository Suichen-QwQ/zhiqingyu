const fs=require('fs'),vm=require('vm'),assert=require('assert');const h=fs.readFileSync('frontend/index.html','utf8'),start=h.indexOf("  let cloudState='pending'"),end=h.indexOf('  function pushDiaryItem(',start);
const values=new Map([['zqy-pending-bad','{broken'],['zqy-pending-good',JSON.stringify({sessions:[{id:'recoverable'}],diary:{}})]]);
const c={saveT:null,cloudT:null,sessionStorage:{getItem:()=>null,setItem(){}},localStorage:{get length(){return values.size},key:i=>[...values.keys()][i],getItem:k=>values.get(k)||null}};
vm.createContext(c);vm.runInContext(h.slice(start,end)+'\nthis.records=cloudPendingRecords;this.dirty=cloudUnsynced',c);
const records=c.records();assert(records['zqy-pending-bad'].unreadable);assert.equal(records['zqy-pending-bad'].raw,'{broken');assert.equal(records['zqy-pending-good'].sessions[0].id,'recoverable');assert(c.dirty());console.log('corrupt pending records do not hide later recoverable snapshots passed');
