const fs=require('fs'),vm=require('vm'),assert=require('assert'),ts=require('../prototype-frontend/node_modules/typescript');
function section(file,a,b){const s=fs.readFileSync(file,'utf8'),start=s.indexOf(a),end=s.indexOf(b,start);assert(start>=0&&end>start);return ts.transpileModule(s.slice(start,end),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;}
async function chat(){
 const ref=v=>({value:v}),ctx={sessionId:ref('one'),messages:ref([]),loading:ref(false),input:ref('hello'),selectedExperienceMode:ref(null),selectedAIStyle:ref(null),selectedChatMode:ref('deep'),todayEmotion:ref(null),lastRiskLevel:ref('normal'),shouldShowCardButton:ref(false),shouldShowSatisfactionButtons:ref(false),viewEpoch:0,loadSessions(){},message:{error(){},warning(){}},t:x=>x,scrollToBottom(){}};let finish;ctx.sendChatMessage=()=>new Promise(resolve=>finish=resolve);vm.createContext(ctx);
 vm.runInContext(section('prototype-frontend/src/views/Chat.vue','const handleSend = async','const handleKeyPress')+'\nthis.send=handleSend',ctx);
 vm.runInContext(section('prototype-frontend/src/views/Chat.vue','const handleNewChat = ()','// 删除会话')+'\nthis.newChat=handleNewChat',ctx);
 const pending=ctx.send();ctx.newChat();ctx.input.value='new session draft';finish({data:{session_id:'one',reply:'old reply'},error:null});await pending;
 assert.equal(ctx.sessionId.value,null);assert.equal(ctx.messages.value.length,0);assert.equal(ctx.input.value,'new session draft');assert(!ctx.loading.value);
}
function exportTitle(){const code=ts.transpileModule(fs.readFileSync('prototype-frontend/src/lib/cardExport.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;const ctx={exports:{},require:()=>({renderMarkdown:s=>s})};vm.createContext(ctx);vm.runInContext(code,ctx);const html=ctx.exports.generateCardHtml({theme:'</title><script>test()</script>'});assert(!html.includes('<script>test()'));assert(html.includes('&lt;script&gt;'));}
(async()=>{await chat();exportTitle();console.log('Prototype replies remain in their original session; exported titles are escaped')})().catch(e=>{console.error(e);process.exitCode=1});
