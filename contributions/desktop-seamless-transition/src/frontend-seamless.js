// One speculative next episode; React still owns episode identity/auto-continue.
const desktopStandbys = new WeakMap();

function desktopShouldPrewarm(media) {
  const duration = media.desktopTimelineDuration || media.duration;
  const position = media.currentTime + (media.desktopTimeOrigin || 0);
  return Number.isFinite(duration) && duration > 0 && !media.ended &&
    media.readyState >= 2 && !media.desktopBuffering &&
    (duration - position) / Math.max(.25, media.playbackRate || 1) <= 12;
}

function desktopRetainPicture(media) {
  const preparation = desktopStandbys.get(media);
  if (!preparation || preparation.failed) return null;
  const display = media.desktopDisplayMedia || media;
  let cover = null;
  // Native video is a separate HWND: its session is retained below. HLS can
  // retain the last decoded frame after React removes the old video element.
  if (display.videoWidth > 0 && !media.desktopNativePicture) {
    try {
      cover = document.createElement('canvas');
      cover.width = display.videoWidth; cover.height = display.videoHeight;
      cover.className = 'validation-video';
      cover.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:contain;pointer-events:none;z-index:1';
      cover.getContext('2d').drawImage(display, 0, 0, cover.width, cover.height);
      (media.closest('.player-stage') || media.parentElement).append(cover);
    } catch {cover?.remove(); cover = null;}
  }
  const cleanup = () => cover?.remove();
  preparation.retain(cleanup);
  return release => preparation.retain(release);
}

function desktopPrepareNext(url, currentMedia) {
  if (!currentMedia || !currentMedia.desktopSessionId?.())
    return {dispose() {}, claim: async () => null};
  const endpoint = w0(url), parent = currentMedia.desktopSessionId();
  const previous = desktopStandbys.get(currentMedia);
  previous?.dispose();
  let disposed = false, claimed = false, id = null, controller = null, video = null;
  let mode = null, consumer = null, retained = [], retireTimer = null;
  let known = {}, failed = false;
  const headers = {'x-api-key': endpoint.key};
  const options = {credentials: 'omit', redirect: 'error', cache: 'no-store'};
  const abort = new AbortController();
  const deadline = Date.now() + 90000;
  async function fetchJson(url, init = {}) {
    const remaining = Math.min(15000, deadline - Date.now());
    if (disposed || remaining <= 0) throw Error('Standby request expired');
    const local = new AbortController();
    let timer, cancel;
    try {
      return await Promise.race([
        (async () => {
          const response = await fetch(url, {...options, ...init, signal:local.signal,
            headers:{...headers,...init.headers}});
          if (!response.ok) throw Error('Standby unavailable');
          return response.status === 204 ? null : response.json();
        })(),
        new Promise((_, reject) => {
          cancel = () => {local.abort();reject(Error('Standby request cancelled'));};
          abort.signal.addEventListener('abort',cancel,{once:true});
          timer = setTimeout(cancel,remaining);
          if (abort.signal.aborted) cancel();
        })
      ]);
    } finally {clearTimeout(timer);abort.signal.removeEventListener('abort',cancel);}
  }
  function request(path, init = {}) {
    return fetchJson(endpoint.origin + '/desktop/hls' + path, init);
  }
  async function release() {
    if (!id) return;
    const old = id; id = null;
    try {await fetch(endpoint.origin + '/desktop/hls/' + old,
      {...options, method:'DELETE', headers, keepalive:true});} catch {}
  }
  function finishRetained() {
    clearTimeout(retireTimer); retireTimer = null;
    for (const cleanup of retained.splice(0)) cleanup();
    if (desktopStandbys.get(currentMedia) === preparation) desktopStandbys.delete(currentMedia);
  }
  function cleanup() {
    disposed = true; abort.abort(); controller?.(); video?.remove(); release(); finishRetained();
  }
  const preparation = {
    get failed() {return failed;},
    dispose() {if (!claimed) cleanup();},
    retain(fn) {
      retained.push(fn);
      // A stalled resolver/failed transfer cannot retain old sessions forever.
      retireTimer ||= setTimeout(finishRetained, 90000);
    },
    finishRetained,
    cancelClaim: cleanup,
    claim: async () => null,
    async claimRecord(wanted, position) {
      if (disposed || claimed || wanted !== url || position > .05) {preparation.dispose(); return null;}
      claimed = true;
      const result = await prepared;
      if (!result || disposed) {cleanup(); return null;}
      return {...result, settings:{rate:currentMedia.playbackRate || 1,
        volume:currentMedia.volume,muted:currentMedia.muted}};
    }
  };
  desktopStandbys.set(currentMedia, preparation);
  const callbacks = Object.fromEntries(['onTimeline','onPlayableRange','onComplete','onWindowOrigin',
    'onReady','onError','onAcceptanceHlsTransition'].map(name => [name, (...args) => {
    known[name] = args;
    if (name === 'onError') {failed = true; if (!claimed) cleanup();}
    consumer?.[name]?.(...args);
  }]));
  const prepared = (async () => {
    try {
      const capability = await request('/capabilities');
      if (capability.standbyPlayback !== 1 || disposed) return null;
      const created = await fetchJson(endpoint.url, {method:'POST',
        headers:{'x-desktop-codec-negotiation':'1','x-desktop-prewarm-parent':parent}});
      const identifier = created.id;
      if (!/^[a-f0-9]{32}$/.test(identifier)) throw Error('Invalid standby');
      id = identifier;
      if (disposed) {release(); return null;}
      let value;
      while (!disposed && Date.now() < deadline) {
        value = await request('/' + id + '/status');
        if (value.state === 'failed') throw Error('Standby source failed');
        if (value.source) break;
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      if (disposed || !value?.source) throw Error('Standby source timed out');
      mode = capability.nativePlayback === 1 && value.source.video?.contentType?.startsWith('video/mp4; codecs="hvc1.')
        ? 'native' : await desktopSupportsSource(value.source) ? 'copy' : 'h264';
      await request('/' + id + '/mode', {method:'POST', headers:{'content-type':'application/json'},body:JSON.stringify({mode})});
      if (mode === 'native') {
        let placement = null;
        while (!disposed && Date.now() < deadline) {
          value = await request('/' + id + '/status');
          if (value.state === 'failed' || value.native?.state === 'failed') throw Error('Standby decoder failed');
          if (value.native?.outputReady && placement === null) {
            const r=currentMedia.getBoundingClientRect(),s=window.devicePixelRatio || 1;
            placement=(await request('/'+id+'/control',{method:'POST',headers:{'content-type':'application/json'},
              body:JSON.stringify({rect:[Math.max(0,Math.round(r.left*s)),Math.max(0,Math.round(r.top*s)),
                Math.max(1,Math.round(r.width*s)),Math.max(1,Math.round((r.height-Math.min(84,Math.max(0,r.height-1)))*s))],
                visible:false,paused:true,muted:true,rate:currentMedia.playbackRate || 1})})).revision;
          }
          if (value.native?.outputReady && placement !== null && value.native.revision >= placement)
            return {id, mode, dispose:cleanup};
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        throw Error('Standby frame timed out');
      }
      video = document.createElement('video');
      video.className = 'validation-video'; video.playsInline = true;
      video.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:contain;pointer-events:none;opacity:0';
      video.muted = true; video.volume = 0; video.playbackRate = currentMedia.playbackRate || 1;
      (currentMedia.closest('.player-stage') || currentMedia.parentElement).append(video);
      controller = desktopCodecHls(video, url, 0, callbacks,
        {claim:async()=>id,dispose(){}}, false, {paused:true,standbyParent:parent});
      while (!disposed && !failed && Date.now() < deadline) {
        if (video.readyState >= 2 && video.videoWidth > 0 && known.onReady) break;
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      if (disposed || failed || video.readyState < 2) throw Error('Standby video timed out');
      id = controller.sessionId?.() || id;
      return {id, mode, dispose:cleanup, adopt(media, handlers, onFailure) {
        if (disposed) return null;
        const saved = new Map(), listeners = [];
        let closed = false;
        const settings = {rate:currentMedia.playbackRate || 1,volume:currentMedia.volume,muted:currentMedia.muted};
        const property = (name, descriptor) => {
          saved.set(name,Object.getOwnPropertyDescriptor(media,name));
          Object.defineProperty(media,name,{configurable:true,...descriptor});
        };
        for (const name of ['currentTime','playbackRate','volume','muted'])
          property(name,{get:()=>video[name],set:v=>{video[name]=v;}});
        for (const name of ['paused','ended','duration','readyState','videoWidth','videoHeight','buffered','seeking','error'])
          property(name,{get:()=>video[name]});
        property('play',{value:()=>video.play()}); property('pause',{value:()=>video.pause()});
        property('desktopDisplayMedia',{value:video});
        property('desktopSessionId',{value:()=>id});
        for (const name of ['play','playing','pause','ended','timeupdate','waiting','seeking','seeked','progress','volumechange','ratechange','error','loadedmetadata','durationchange']) {
          const forward=()=>{if(!closed)media.dispatchEvent(new Event(name));};
          video.addEventListener(name,forward);listeners.push([name,forward]);
        }
        consumer = handlers;
        video.playbackRate=settings.rate;video.volume=settings.volume;video.muted=settings.muted;
        video.style.opacity='1';
        for (const name of ['onTimeline','onPlayableRange','onComplete','onWindowOrigin','onReady'])
          if (known[name]) handlers[name]?.(...known[name]);
        media.dispatchEvent(new Event('loadedmetadata'));media.dispatchEvent(new Event('durationchange'));
        const restoreAdoption = () => {
          if (closed) return false;
          closed=true;consumer=null;
          for(const [name,fn] of listeners)video.removeEventListener(name,fn);
          for(const [name,descriptor] of saved){if(descriptor)Object.defineProperty(media,name,descriptor);else delete media[name];}
          return true;
        };
        request('/'+id+'/activate',{method:'POST'}).then(() => {
          if (disposed) return;
          return video.play();
        }).then(() => {
          if (disposed) return;
          if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(finishRetained);
          else requestAnimationFrame(finishRetained);
        }).catch(()=>{
          if (closed || disposed) return;
          restoreAdoption();cleanup();
          if (onFailure) onFailure(); else handlers.onError?.();
        });
        return Object.assign(() => {
          if(restoreAdoption())cleanup();
        },{seek:value=>controller?.seek(value),sessionId:()=>id});
      }};
    } catch {
      failed = true; if (!claimed) cleanup(); else {release();video?.remove();}
      return null;
    }
  })();
  return preparation;
}
