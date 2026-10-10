const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../src/frontend-codec.js'),'utf8');
const flush=async()=>{for(let i=0;i<10;i++)await new Promise(setImmediate)};
(async()=>{
  let supported=true,calls=[],controllers=[],timers=new Map(),tid=0;
  const c={URL,Headers,Number,Math,Date,queueMicrotask,
    setTimeout:(fn,delay)=>{timers.set(++tid,{fn,delay});return tid},clearTimeout:id=>timers.delete(id),
    MediaSource:{isTypeSupported:()=>supported},navigator:{mediaCapabilities:{decodingInfo:async()=>({supported})}},
    fetch:async(url,init={})=>{
      calls.push([url,init]);
      if(url.endsWith('/mode'))return {ok:true,json:async()=>JSON.parse(init.body)};
      const body={source:{copyEligible:true,video:{contentType:'video/mp4; codecs="hvc1.1.6.L120.B0"'},audio:[]},videoMode:null,startSeconds:0};
      return {ok:true,clone(){return this},json:async()=>body};
    }};
  const fake=(media,url,target,callbacks,prep,transport)=>{
    const index=controllers.length;
    const dispose=()=>{};dispose.seek=()=>{};
    controllers.push({target,callbacks,transport});
    // The wrapper must preserve selected transport and callback ownership.
    transport.usedCopy=()=>index===0;
    return dispose;
  };
  c.ek=fake;c.desktopLegacyHls=(m,u,t,cb,p,a,f)=>fake(m,u,t,cb,p,f);
  vm.createContext(c);vm.runInContext(source,c);
  const desc={copyEligible:true,video:{contentType:'video/mp4; codecs="hvc1.1.6.L120.B0"'},audio:[]};
  assert.equal(await c.desktopSupportsSource(desc),true);
  assert.equal(await c.desktopSupportsSource({...desc,copyEligible:false,audio:[{codec:'aac',profile:'HE-AACv2'}]}),false);
  supported=false;assert.equal(await c.desktopSupportsSource(desc),false);supported=true;
  const fetcher=c.desktopCreateCodecFetch();
  await fetcher('http://127.0.0.1:4567/desktop/hls',{method:'POST'});
  assert.equal(calls.at(-1)[1].headers.get('x-desktop-codec-negotiation'),'1');
  const status='http://127.0.0.1:4567/desktop/hls/'+'a'.repeat(32)+'/status';
  await fetcher(status);assert.equal(fetcher.usedCopy(),true);
  fetcher.close();await assert.rejects(fetcher(status));
  await assert.rejects(c.desktopCreateCodecFetch()('https://example.com/desktop/hls'));
  for(const windowed of [false,true]){
    controllers=[];timers.clear();let errors=0,ready=0,pauses=0;
    const listeners={};
    const media={currentTime:0,playbackRate:1.5,videoWidth:1920,
      pause(){pauses++;listeners.pause?.()},addEventListener(n,f){listeners[n]=f},removeEventListener(n){delete listeners[n]}};
    const dispose=c.desktopCodecHls(media,'http://127.0.0.1',0,{onReady(){ready++},onError(){errors++}},null,windowed);
    controllers[0].callbacks.onReady();
    media.currentTime=37;listeners.timeupdate();listeners.pause();
    controllers[0].callbacks.onAcceptanceHlsTransition({kind:'controllerFailPause'});
    media.currentTime=0;
    controllers[0].callbacks.onError();
    assert.equal(controllers.length,2);assert.equal(controllers[1].target,37);
    assert.equal(media.playbackRate,1.5);
    controllers[1].callbacks.onReady();await flush();
    assert(pauses>0,'fallback must restore paused playback');
    const previousPauses=pauses;listeners.play();
    assert.equal(pauses,previousPauses+1,'internal autoplay must not resume a paused video');
    controllers[0].callbacks.onError();assert.equal(errors,0);
    controllers[1].callbacks.onError();assert.equal(errors,1);assert.equal(controllers.length,2);
    dispose();assert.deepEqual(Object.keys(listeners),[]);
    controllers=[];timers.clear();media.videoWidth=0;
    const end=c.desktopCodecHls(media,'http://127.0.0.1',0,{onReady(){},onError(){}},null,windowed);
    controllers[0].callbacks.onReady();
    [...timers.values()].find(t=>t.delay===8000).fn();
    assert.equal(controllers.length,2,'audio-only success must fall back');end();
  }
  console.log('PASS: codec detection, negotiation, position/rate/pause, one retry, stale callbacks and missing video');
  // HLS audio copy restrictions must not prevent native HEVC selection.
  const nativeCalls=[],nativeTimers=new Map();let delegated=0,nativeTid=0;
  const stage={classList:{add(){},remove(){}}};
  const nativeMedia={playbackRate:2,volume:1,muted:false,closest:()=>stage,
    dispatchEvent(){},getBoundingClientRect:()=>({left:0,top:0,width:800,height:500})};
  const nc={URL,Event,Number,Math,Date,DOMException,
    window:{devicePixelRatio:1},ResizeObserver:class{observe(){}disconnect(){}},
    document:{hidden:false,head:{append(){}},createElement:()=>({remove(){}}),addEventListener(){},removeEventListener(){}},
    setTimeout:(fn,delay)=>{nativeTimers.set(++nativeTid,{fn,delay});return nativeTid},clearTimeout:id=>nativeTimers.delete(id),
    w0:()=>({origin:'http://127.0.0.1:4567',url:'http://127.0.0.1:4567/desktop/hls?series_id=1234567890123456&ep=1',key:'test-only'}),
    desktopCodecHls:()=>{delegated++;return ()=>{}},
    fetch:async(url,init={})=>{
      url=String(url);
      nativeCalls.push([url,init]);
      let body={state:'preparing',source:{...desc,copyEligible:false,audio:[{codec:'aac',profile:'HE-AACv2'}]}};
      if(url.endsWith('/capabilities'))body={nativePlayback:1};
      else if(init.method==='POST'&&!url.endsWith('/mode'))body={id:'a'.repeat(32)};
      else if(url.endsWith('/mode'))body=JSON.parse(init.body);
      return {ok:true,status:init.method==='DELETE'?204:200,json:async()=>body};
    }};
  vm.createContext(nc);vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../src/frontend-native.js'),'utf8'),nc);
  const nativeDispose=nc.desktopNativePlayback(nativeMedia,'http://127.0.0.1',4,{},null);
  await flush();
  assert.equal(delegated,0);
  assert.equal(nativeCalls.filter(([url])=>url.endsWith('/mode')).length,1);
  assert.equal(JSON.parse(nativeCalls.find(([url])=>url.endsWith('/mode'))[1].body).mode,'native');
  nativeDispose();await flush();
  assert(nativeCalls.some(([,init])=>init.method==='DELETE'));
  console.log('PASS: HE-AACv2 keeps native HEVC selection while HLS packet copy remains disabled');
  for(const kind of ['source-timeout','source-failed','transport-failed','native-source-failed','native-failed','native-stopping']){
    nativeCalls.length=0;nativeTimers.clear();delegated=0;
    let errors=0,modeChosen=false,clock=0,forced;
    nc.Date={now:()=>kind==='source-timeout'||kind==='native-stopping'&&modeChosen?(clock+=90001):0};
    nc.desktopCodecHls=(...args)=>{delegated++;forced=args[6]?.forceH264;return ()=>{}};
    nc.fetch=async(url,init={})=>{
      url=String(url);nativeCalls.push([url,init]);
      let body;
      if(url.endsWith('/capabilities'))body={nativePlayback:1};
      else if(init.method==='DELETE')return kind==='native-stopping'?{ok:true,status:202,json:async()=>({released:false})}:{ok:true,status:204};
      else if(url.endsWith('/mode')){modeChosen=true;body=JSON.parse(init.body)}
      else if(init.method==='POST')body={id:'b'.repeat(32)};
      else if(kind==='transport-failed')throw Error('Simulated transport error');
      else if(kind==='source-failed')body={state:'failed',source:null};
      else if(kind==='native-source-failed'&&modeChosen)body={state:'complete',native:{state:'failed',failureCode:'source-read'}};
      else if((kind==='native-failed'||kind==='native-stopping')&&modeChosen)body={state:'complete',native:{state:'failed'}};
      else body={state:'preparing',source:desc};
      return {ok:true,status:200,json:async()=>body};
    };
    const end=nc.desktopNativePlayback(nativeMedia,'http://127.0.0.1',0,{onError(){errors++}},null);
    await flush();
    assert.equal(delegated,kind==='native-failed'?1:0,kind+' must distinguish source failure from decoding failure');
    assert.equal(errors,kind==='native-failed'?0:1);
    if(kind==='native-failed')assert.equal(forced,true);
    assert(nativeCalls.some(([,init])=>init.method==='DELETE'),kind+' releases the session');
    end();await flush();
  }
  console.log('PASS: slow/missing source and transport errors never cause H264; actual native failure falls back once');
  nativeCalls.length=0;nativeTimers.clear();let modeChosen=false;
  nc.Date=Date;
  nc.fetch=async(url,init={})=>{
    url=String(url);nativeCalls.push([url,init]);let body;
    if(url.endsWith('/capabilities'))body={nativePlayback:1};
    else if(init.method==='DELETE')return {ok:true,status:204};
    else if(url.endsWith('/mode')){modeChosen=true;body={mode:'native'}}
    else if(url.endsWith('/control'))body={revision:1};
    else if(init.method==='POST')body={id:'c'.repeat(32)};
    else body={state:'complete',source:desc,native:modeChosen?{state:'ended',outputReady:true,
      width:1920,height:1080,time:90,duration:90,paused:true,rate:2,volume:1,muted:false,revision:100}:null};
    return {ok:true,status:200,json:async()=>body};
  };
  const stopAfterEof=nc.desktopNativePlayback(nativeMedia,'http://127.0.0.1',0,{onReady(){}},null);
  await flush();
  for(let turn=0;turn<2;turn++){
    const entries=[...nativeTimers];nativeTimers.clear();
    for(const [,entry] of entries)await entry.fn();
    await flush();
  }
  assert.equal(nativeMedia.ended,true);
  nativeMedia.currentTime=25;
  assert.equal(nativeMedia.ended,false,'seek clears EOF immediately');
  await nativeMedia.play();await flush();
  for(const [key,entry] of [...nativeTimers])if(entry.delay===250){nativeTimers.delete(key);await entry.fn();}
  await flush();
  const seeks=nativeCalls.filter(([url,init])=>url.endsWith('/control')&&JSON.parse(init.body).seek!==undefined)
    .map(([,init])=>JSON.parse(init.body).seek);
  assert(seeks.length>0&&seeks.every(value=>value===25),'play must not replace the accepted target with seek(0)');
  assert.equal(nativeMedia.currentTime,25);stopAfterEof();await flush();
  console.log('PASS: EOF seek preserves the selected target when play resumes');
})().catch(e=>{console.error(e);process.exitCode=1});
