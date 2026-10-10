const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2],'utf8');
const tick=async()=>{for(let n=0;n<30;n++)await new Promise(setImmediate)};
async function scenario(fault){
  let now=0,errors=0,released=0,finished=0,cancelled=0,selected=false,activated=false;
  const timers=new Set();
  const media=new EventTarget();Object.assign(media,{playbackRate:2,volume:.4,muted:false,
    closest:()=>({classList:{add(){},remove(){}}}),
    getBoundingClientRect:()=>({left:0,top:0,width:800,height:600})});
  const prep={claimRecord:async()=>({id:'a'.repeat(32),mode:'native',dispose(){}}),dispose(){},
    finishRetained(){if(fault==='success')assert(activated,'old picture retained until activate ACK');finished++},cancelClaim(){cancelled++}};
  const context={URL,Event,Number,Math,Map,AbortController,window:{devicePixelRatio:1},
    Date:{now:()=>now},ResizeObserver:class{observe(){}disconnect(){}},
    document:{hidden:false,head:{append(){}},createElement:()=>({remove(){}}),addEventListener(){},removeEventListener(){}},
    setTimeout(fn,delay){if(delay>=15000)return 999;const id=setTimeout(()=>{now+=250;fn()},1);timers.add(id);return id;},
    clearTimeout:id=>{timers.delete(id);clearTimeout(id)},
    w0:()=>({origin:'http://127.0.0.1',url:'http://127.0.0.1/desktop/hls?ep=2',key:'test'}),
    desktopCodecHls(){throw Error('should report activation failure')},
    fetch:async(url,init={})=>{
      let body={};url=String(url);
      if(init.method==='DELETE'){released++;return {ok:true,status:204}}
      if(url.endsWith('/capabilities'))body={nativePlayback:1};
      else if(url.endsWith('/mode')){selected=true;body={mode:'native'}}
      else if(url.endsWith('/control'))body={revision:10};
      else if(url.endsWith('/activate')){activated=true;body={activated:true}}
      else if(url.endsWith('/status')){
        if(selected&&fault==='hung')return new Promise(()=>{});
        body={state:'complete',source:{video:{contentType:'video/mp4; codecs="hvc1.1"'}},
          native:selected?{state:'ready',outputReady:fault!=='frame',visible:fault!=='visible',
            revision:fault==='revision'?0:10,width:1920,height:1080,time:0,duration:90}:null};
      }
      return {ok:true,status:200,json:async()=>body};
    }};
  vm.createContext(context);vm.runInContext(source,context);
  const dispose=context.desktopNativePlayback(media,'http://127.0.0.1',0,{onReady(){},onError(){errors++}},prep);
  for(let n=0;n<80&&!errors&&!activated;n++){await tick();await new Promise(r=>setTimeout(r,1))}
  if(fault==='success'){assert(activated);assert.equal(errors,0);assert.equal(released,0);assert(finished>0)}
  else {assert.equal(errors,1,fault+' must report bounded activation failure');
    assert.equal(released,1);assert(finished>0&&cancelled>0);}
  dispose();for(const timer of timers)clearTimeout(timer);
}
(async()=>{for(const fault of ['visible','frame','revision','hung','success'])await scenario(fault);
  console.log('PASS: native visible/frame/revision and hanging-status ACK failures release and report error');
})().catch(error=>{console.error(error);process.exitCode=1});
