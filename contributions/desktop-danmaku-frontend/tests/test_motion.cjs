const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const CustomEvent = globalThis.CustomEvent || class extends Event {constructor(type,options){super(type);this.detail=options.detail;}};
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../src/danmaku.mjs'),'utf8').replace('export function','function');
let frames = [], requests = [], errors = [], events = new Map();
const preferences = new Map(); let preferenceEvent;
const layer = {children: [], hidden: false, setAttribute(){}, append(node){this.children.push(node); node.remove=()=>this.children=this.children.filter(n=>n!==node);}, replaceChildren(){this.children=[];}, remove(){this.removed=true;}};
const stage = {clientWidth:1000,classList:{contains:()=>false},append(){}};
const media = {currentTime:0,duration:192,clientWidth:1000,closest:()=>stage,
  dispatchEvent(){},addEventListener:(name,fn)=>events.set(name,fn),removeEventListener:name=>events.delete(name)};
const context = vm.createContext({URL,URLSearchParams,AbortController,Event,CustomEvent,Date,console,
  localStorage:{getItem:key=>preferences.get(key)??null,setItem:(key,value)=>preferences.set(key,value)},
  window:{dispatchEvent(){}},
  document:{createTextNode:text=>({textContent:text}),createElement:tag=>tag==='div'?layer:{dataset:{},style:{},offsetWidth:100,replaceChildren(...nodes){this.children=nodes;this.textContent=nodes.map(n=>n.textContent||'').join('');}}},
  requestAnimationFrame:fn=>{frames.push(fn);return frames.length;},cancelAnimationFrame(){},
  fetch:async(url,options)=>{if(new URL(url).pathname.endsWith('/emojis'))return {ok:true,json:async()=>({items:{}})};requests.push({url:new URL(url),options});return {ok:true,json:async()=>({items:[
    {id:'3000000000000000001',text:'<img onerror=alert(1)>',offset_ms:1000}],next_offset_ms:30000,cursor:'opaque',has_more:true})};}});
vm.runInContext(source + `
const preferencesRead=(name,fallback)=>localStorage.getItem('hongguo:'+name)===null?fallback:localStorage.getItem('hongguo:'+name)==='on';
const api=createDanmaku({read:async(endpoint,resource,params,signal)=>{
 const url=new URL(endpoint.origin+'/desktop/social/'+resource); url.search=new URLSearchParams(params);
 const r=await fetch(url,{signal}); return r.json();},preference:preferencesRead,
 set:(media,changes)=>{for(const name of ['social','danmaku'])if(typeof changes[name]==='boolean')localStorage.setItem('hongguo:'+name,changes[name]?'on':'off');
 if(changes.settings){changes.settings=api.settings(changes.settings);localStorage.setItem('hongguo:danmakuSettings',JSON.stringify(changes.settings));localStorage.setItem('hongguo:danmakuSettingsVersion','2');}
 media.dispatchEvent(new CustomEvent('desktopsocialsettings',{detail:changes}));},
 emojis:{load(){},catalog:Object.create(null),parts:text=>[String(text)],Text(){}}});
const desktopStartDanmaku=api.start,desktopDanmakuRows=api.rows,desktopDanmakuSettings=api.settings;
const desktopSocialPreference=preferencesRead,desktopSocialSet=(media,changes)=>{
for(const name of ['social','danmaku'])if(typeof changes[name]==='boolean')localStorage.setItem('hongguo:'+name,changes[name]?'on':'off');
if(changes.settings){changes.settings=api.settings(changes.settings);localStorage.setItem('hongguo:danmakuSettings',JSON.stringify(changes.settings));localStorage.setItem('hongguo:danmakuSettingsVersion','2');}
media.dispatchEvent(new CustomEvent('desktopsocialsettings',{detail:changes}));};
`, context);
const run = expression => vm.runInContext(expression, context);
context.media=media; context.endpoint={origin:'http://127.0.0.1:1234',key:'abc',series:'1000000000000000001',episode:'1'};
async function step(time){media.currentTime=time;frames.shift()?.();await new Promise(r=>setImmediate(r));}
(async()=>{
  const stop = run('desktopStartDanmaku(media,endpoint,()=>{})');
  await new Promise(r=>setImmediate(r)); await step(2);
  assert.equal(requests.length,1);assert.equal(requests[0].url.searchParams.get('offset_ms'),'0');
  assert.equal(layer.children[0].textContent,'<img onerror=alert(1)>');
  const paused=layer.children[0].style.transform;await step(2);assert.equal(layer.children[0].style.transform,paused);
  events.get('desktopsocialsettings')({detail:{settings:{opacity:50,lanes:1,fontSize:36,duration:12}}});
  await step(2);assert.equal(layer.children[0].style.opacity,.5);
  assert.equal(media.desktopDanmakuSettings.fontSize,36);
  await step(3);assert.notEqual(layer.children[0].style.transform,paused);
  media.currentTime=70;events.get('seeking')();await step(70);
  assert.equal(requests.at(-1).url.searchParams.get('offset_ms'),'60000');
  assert.equal(requests.at(-1).url.searchParams.get('cursor'),'');
  stop();assert.equal(media.desktopDanmaku.length,0);assert.equal(layer.removed,true);assert.equal(events.size,0);
  const rows=run(`desktopDanmakuRows(Array.from({length:100},(_,i)=>({id:String(i),text:'x',offset_ms:1000})))`);
  assert.equal(rows.length,3);assert.equal(new Set(rows.map(r=>r.lane)).size,3);
  const retained = run(`(()=>{const all=Array.from({length:12},(_,i)=>({id:String(i),text:'x',offset_ms:i*1600}));
    const first=desktopDanmakuRows(all);const second=desktopDanmakuRows(all.slice(3).concat({id:'late',text:'late',offset_ms:7000}),desktopDanmakuSettings(),first);
    return first.filter(r=>Number(r.id)>=3).every(r=>second.find(n=>n.id===r.id)?.lane===r.lane);})()`);
  assert.equal(retained,true,'pagination must keep existing lanes');
  media.dispatchEvent=event=>preferenceEvent=event.detail;
  assert.equal(run("desktopSocialPreference('social',false)"),false);
  run('desktopSocialSet(media,{social:true,danmaku:false})');
  assert.equal(run("desktopSocialPreference('social',false)"),true);
  assert.equal(run("desktopSocialPreference('danmaku',true)"),false);
  assert.equal(preferenceEvent.social,true);assert.equal(preferenceEvent.danmaku,false);
  run('desktopSocialSet(media,{social:false})');
  assert.equal(run("desktopSocialPreference('social',true)"),false);
  assert.equal(run("desktopSocialPreference('danmaku',true)"),false,'drawer preference must not alter danmaku');
  run('desktopSocialSet(media,{settings:{opacity:50,lanes:2,fontSize:32,duration:10}})');
  assert.equal(run('desktopDanmakuSettings().opacity'),50);
  assert.equal(run('desktopDanmakuSettings().lanes'),2);
  assert.equal(run('desktopDanmakuSettings({opacity:1000,lanes:-1,fontSize:34,duration:null}).opacity'),100);
  assert.equal(run('desktopDanmakuSettings({}).duration'),14);
  preferences.set('hongguo:danmakuSettings',JSON.stringify({opacity:50,lanes:2,fontSize:32,duration:8}));
  preferences.delete('hongguo:danmakuSettingsVersion');
  assert.equal(run('desktopDanmakuSettings().duration'),14);
  assert.equal(run('desktopDanmakuSettings().duration'),14,'migration must happen once');
  assert.equal(run('desktopDanmakuSettings().opacity'),50);
  const crowded=run(`desktopDanmakuRows([{id:'a',text:'x',offset_ms:0},{id:'b',text:'长'.repeat(160),offset_ms:5600}],{opacity:80,lanes:1,fontSize:28,duration:14})`);
  assert.equal(crowded.length,1,'wide trailing row must not catch a narrow row in the same lane');
  const spaced=run(`desktopDanmakuRows([{id:'a',text:'x',offset_ms:0},{id:'b',text:'长'.repeat(160),offset_ms:15000}],{opacity:80,lanes:1,fontSize:28,duration:14})`);
  assert.equal(spaced.length,2);
  // Verify the actual separation equation through the overlapping interval.
  const safePair=run(`desktopDanmakuRows([{id:'a',text:'x',offset_ms:0},{id:'b',text:'长'.repeat(160),offset_ms:12000}],{opacity:80,lanes:1,fontSize:28,duration:14})`);
  assert.equal(safePair.length,2);
  for(let time=12;time<14;time+=.1){
    const right=1000-(1000+60)*time/14+60;
    const left=1000-(1000+4480)*(time-12)/14;
    assert.ok(left-right>=16,'no chase collision throughout shared lifetime');
  }
  preferences.set('hongguo:danmaku','on'); frames=[]; requests=[];let aborted=0;
  context.fetch=async(url,options)=>{
    const u=new URL(url);requests.push({url:u,options});
    if(u.searchParams.get('offset_ms')==='0')return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>{aborted++;reject(new DOMException('Aborted','AbortError'));},{once:true}));
    return {ok:true,json:async()=>({items:[{id:'new',text:'after seek',offset_ms:61000}],next_offset_ms:90000,cursor:'',has_more:false})};
  };
  media.currentTime=0;media.dispatchEvent=()=>{};
  const stopSeek=run('desktopStartDanmaku(media,endpoint,()=>{})');
  media.currentTime=70;events.get('seeking')();await step(70);
  assert.equal(aborted,1);assert.equal(requests.at(-1).url.searchParams.get('offset_ms'),'60000');
  events.get('desktopsocialsettings')({detail:{danmaku:false}});
  assert.equal(media.desktopDanmaku.length,0);assert.equal(layer.children.length,0);
  const before=requests.length;await step(95);assert.equal(requests.length,before);
  events.get('desktopsocialsettings')({detail:{danmaku:true}});await step(95);
  assert.ok(requests.length>before,'standalone renderer resumes when toggled on');
  stopSeek();assert.equal(events.size,0);
  console.log('PASS: opaque cursor, media clock, pause/seek, escaping, density, cleanup');
  console.log('PASS: independent persistent drawer/danmaku preferences and settings event');
  console.log('PASS: live settings rendering, validation and persistence');
  console.log('PASS: pagination preserves in-flight lanes');
  console.log('PASS: per-generation seek abort, standalone on/off, width-aware collision prevention');
})().catch(e=>{console.error(e);process.exitCode=1;});
