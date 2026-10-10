function desktopNativePlayback(media, url, initialPosition, callbacks, preparation, windowed = false) {
  if (typeof ResizeObserver !== 'function') return desktopCodecHls(media, url, initialPosition, callbacks, preparation, windowed);
  const endpoint = w0(url);
  if (!endpoint) return desktopCodecHls(media, url, initialPosition, callbacks, preparation, windowed);
  let disposed = false, delegated = null, id = null, native = false, restored = false;
  let ready = false, timer, controlTimer, pollBusy = false, controlBusy = false, revision = 0;
  let pending = {}, saved = new Map(), stage = media.closest('.player-stage') || media.parentElement;
  let style = null, resize = null, lastRect = '', generation = 0, seekPending = null;
  let reportedSeek = false, fallbackStarted = false;
  let state = {time: initialPosition || 0, duration: 0, paused: false, ended: false,
    rate: media.playbackRate || 1, volume: media.volume, muted: media.muted, width: 0, height: 0,
    seeking: false, buffering: false, bufferStart: 0, bufferEnd: 0};
  const headers = {'x-api-key': endpoint.key};
  const options = {credentials: 'omit', redirect: 'error', cache: 'no-store'};
  const event = name => {if (!disposed && native) media.dispatchEvent(new Event(name));};
  async function request(path, init = {}) {
    const response = await fetch(endpoint.origin + '/desktop/hls' + path,
      {...options, ...init, headers: {...headers, ...init.headers}});
    if (!response.ok) throw Error('Desktop native session unavailable');
    return response.status === 204 ? null : response.json();
  }
  async function release(identifier) {
    if (!identifier) return true;
    const deadline = Date.now() + 15000;
    try {
      do {
        const result = await request('/' + identifier, {method:'DELETE'});
        if (result?.released !== false) return true;
        if (Date.now() >= deadline) return false;
        await new Promise(resolve=>setTimeout(resolve,100));
      } while (Date.now() < deadline);
    } catch {}
    return false;
  }
  function restore() {
    if (restored) return;
    restored = true;
    clearTimeout(timer); clearTimeout(controlTimer);
    resize?.disconnect();
    document.removeEventListener('fullscreenchange', layout);
    document.removeEventListener('visibilitychange', layout);
    stage?.classList.remove('desktop-native-playback');
    style?.remove();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(media, key, descriptor);
      else delete media[key];
    }
    saved.clear(); native = false;
    media.playbackRate = state.rate;
    media.volume = state.volume;
    media.muted = state.muted;
  }
  async function delegate(forceH264) {
    if (disposed || fallbackStarted) return;
    if (!native) {
      state.rate = media.playbackRate || state.rate;
      state.volume = media.volume; state.muted = media.muted;
    }
    fallbackStarted = true; generation++;
    const old = id; id = null;
    restore();
    // Stop the native audio before the HLS element is allowed to autoplay.
    const stopped = await release(old);
    if (disposed) return;
    if (!stopped) {callbacks.onComplete?.(false);callbacks.onError?.();return;}
    delegated = desktopCodecHls(media, url, Math.max(0, state.time), callbacks,
      forceH264 ? null : preparation, windowed, {forceH264, paused: state.paused});
  }
  async function failPreparation() {
    if (disposed || fallbackStarted) return;
    fallbackStarted = true; generation++;
    const old = id; id = null;
    restore();
    await release(old);
    if (!disposed) {callbacks.onComplete?.(false); callbacks.onError?.();}
  }
  function queue(command) {
    if (disposed || !native || fallbackStarted) return;
    Object.assign(pending, command);
    if (!controlTimer && !controlBusy) controlTimer = setTimeout(flush, 250);
  }
  async function flush() {
    controlTimer = null;
    if (disposed || !id || !native || controlBusy || !Object.keys(pending).length) return;
    controlBusy = true;
    const command = pending; pending = {};
    try {
      const result = await request('/' + id + '/control', {method: 'POST',
        headers: {'content-type': 'application/json'}, body: JSON.stringify(command)});
      revision = result.revision;
    } catch {if (!disposed) failPreparation();}
    finally {
      controlBusy = false;
      if (Object.keys(pending).length && !disposed && native) controlTimer = setTimeout(flush, 250);
    }
  }
  function layout() {
    if (!native || !stage) return;
    const rect = media.getBoundingClientRect(), scale = window.devicePixelRatio || 1;
    // Keep the existing timeline, volume, speed and fullscreen buttons above
    // the native surface; the reserved band is part of the current stage.
    const bar = Math.min(84, Math.max(0, rect.height - 1));
    const bounds = [Math.max(0, Math.round(rect.left * scale)), Math.max(0, Math.round(rect.top * scale)),
      Math.max(1, Math.round(rect.width * scale)), Math.max(1, Math.round((rect.height - bar) * scale))];
    const visible = !document.hidden && rect.width > 0 && rect.height > 0;
    const signature = JSON.stringify([bounds, visible]);
    if (signature !== lastRect) {lastRect = signature; queue({rect: bounds, visible});}
  }
  function seek(value) {
    if (disposed || !Number.isFinite(value)) return;
    if (delegated) {delegated.seek(value); return;}
    state.time = Math.max(0, Math.min(state.duration || 86400, value));
    state.ended = false;
    seekPending = state.time; state.seeking = true; reportedSeek = true;
    callbacks.onSeekTarget?.(state.time); event('seeking');
    queue({seek: state.time});
  }
  function patch() {
    // React's control effect can apply its remembered speed while the source
    // is downloading. Capture it immediately before replacing the properties.
    state.rate = media.playbackRate || state.rate;
    state.volume = media.volume; state.muted = media.muted;
    native = true;
    function property(name, descriptor) {
      saved.set(name, Object.getOwnPropertyDescriptor(media, name));
      Object.defineProperty(media, name, {configurable: true, ...descriptor});
    }
    for (const [name, key] of Object.entries({paused: 'paused', duration: 'duration', ended: 'ended',
      videoWidth: 'width', videoHeight: 'height', seeking: 'seeking'})) property(name, {get: () => state[key]});
    property('readyState', {get: () => ready ? 4 : 0});
    property('currentTime', {get: () => state.time, set: seek});
    property('buffered', {get: () => ({length: state.bufferEnd > state.bufferStart ? 1 : 0,
      start(index) {if (index !== 0 || state.bufferEnd <= state.bufferStart) throw new DOMException('Index', 'IndexSizeError'); return state.bufferStart;},
      end(index) {if (index !== 0 || state.bufferEnd <= state.bufferStart) throw new DOMException('Index', 'IndexSizeError'); return state.bufferEnd;}})});
    property('playbackRate', {get: () => state.rate, set(value) {
      if (!Number.isFinite(value) || value < .25 || value > 4) return;
      state.rate = value; queue({rate: value}); event('ratechange');
    }});
    property('volume', {get: () => state.volume, set(value) {
      if (!Number.isFinite(value) || value < 0 || value > 1) return;
      state.volume = value; queue({volume: value}); event('volumechange');
    }});
    property('muted', {get: () => state.muted, set(value) {
      state.muted = !!value; queue({muted: state.muted}); event('volumechange');
    }});
    property('play', {value: () => {
      if (state.ended) {state.ended = false; seek(0);}
      const wasPaused = state.paused; state.paused = false;
      queue({paused: false}); if (wasPaused && ready) {event('play'); event('playing');}
      return Promise.resolve();
    }});
    property('pause', {value: () => {
      const wasPaused = state.paused; state.paused = true;
      queue({paused: true}); if (!wasPaused && ready) event('pause');
    }});
    style = document.createElement('style');
    style.textContent = '.desktop-native-playback .player-chrome{opacity:1!important;pointer-events:auto!important}';
    document.head.append(style); stage?.classList.add('desktop-native-playback');
    resize = new ResizeObserver(layout); resize.observe(media);
    document.addEventListener('fullscreenchange', layout);
    document.addEventListener('visibilitychange', layout);
    layout();
  }
  async function poll(ownGeneration) {
    if (disposed || fallbackStarted || ownGeneration !== generation || pollBusy) return;
    pollBusy = true;
    try {
      const result = await request('/' + id + '/status');
      if (disposed || fallbackStarted || ownGeneration !== generation) return;
      if (result.state === 'failed' || result.native?.state === 'failed') {
        if (result.failureCode === 'source-read' || result.native?.failureCode === 'source-read') failPreparation();
        else delegate(true);
        return;
      }
      const value = result.native;
      if (value && (value.state === 'ready' || value.state === 'ended' || value.state === 'buffering' && (ready || value.outputReady)) && value.width > 0) {
        state.duration = value.duration || result.duration || state.duration;
        state.width = value.width; state.height = value.height;
        const progressive = result.sourceProgress?.kind === 'progressive';
        state.bufferStart = progressive ? value.bufferStart || 0 : 0;
        state.bufferEnd = progressive ? value.bufferEnd || 0 : state.duration;
        callbacks.onTimeline?.(state.duration, state.bufferEnd);
        callbacks.onPlayableRange?.([state.bufferStart, state.bufferEnd]);
        callbacks.onComplete?.(!progressive || result.sourceProgress.complete || value.state === 'ended');
        event('progress');
        const applied = value.revision >= revision && !controlBusy && !Object.keys(pending).length;
        if (seekPending === null || applied) state.time = value.time;
        if (!ready) {
          ready = true;
          callbacks.onWindowOrigin?.(0);
          callbacks.onReady();
          event('loadedmetadata'); event('durationchange'); event('progress');
          queue({paused: state.paused, rate: state.rate, volume: state.volume, muted: state.muted,
            ...(seekPending !== null ? {seek: seekPending} : {})});
          if (!state.paused) {event('play'); event('playing');}
        }
        if (!!value.buffering !== state.buffering) {
          state.buffering = !!value.buffering;
          if (state.buffering) {callbacks.onWaitingForResume?.(); event('waiting');}
          else {callbacks.onReady(); if (!state.paused) event('playing');}
        }
        if (reportedSeek && applied && !value.seeking) {
          reportedSeek = false; seekPending = null; state.seeking = false;
          callbacks.onSeekTarget?.(null); callbacks.onReady(); event('seeked');
        }
        event('timeupdate');
        if (value.state === 'ended' && !state.ended && applied) {
          state.ended = true; state.paused = true; state.time = state.duration;
          event('timeupdate'); event('ended');
        }
      }
      layout();
    } catch {if (!disposed && ownGeneration === generation) failPreparation();}
    finally {
      pollBusy = false;
      if (!disposed && !fallbackStarted && ownGeneration === generation) timer = setTimeout(() => poll(ownGeneration), 250);
    }
  }
  (async () => {
    try {
      const capability = await request('/capabilities');
      if (disposed) return;
      if (capability.nativePlayback !== 1) {delegate(false); return;}
      const sourceUrl = new URL(endpoint.url);
      if (state.time > 0) sourceUrl.searchParams.set('start_seconds', state.time);
      const created = await fetch(sourceUrl, {...options, method: 'POST',
        headers: {...headers, 'x-desktop-codec-negotiation': '1'}});
      if (!created.ok) throw Error('Native session preparation failed');
      const identifier = (await created.json()).id;
      if (!/^[a-f0-9]{32}$/.test(identifier)) throw Error('Invalid native session');
      if (disposed) {await release(identifier); return;}
      id = identifier;
      const deadline = Date.now() + 90000;
      let metadata;
      while (!disposed && Date.now() < deadline) {
        const result = await request('/' + id + '/status');
        if (result.state === 'failed') throw Error('Source preparation failed');
        if (result.source) {metadata = result.source; break;}
        await new Promise(resolve => setTimeout(resolve, 250));
      }
      if (disposed) return;
      // Source download/transport failure says nothing about decoder support.
      if (!metadata) {failPreparation(); return;}
      if (!metadata?.video?.contentType?.startsWith('video/mp4; codecs="hvc1.')) {delegate(false); return;}
      await request('/' + id + '/mode', {method: 'POST', headers: {'content-type': 'application/json'},
        body: JSON.stringify({mode: 'native'})});
      if (disposed) return;
      preparation?.dispose();
      patch(); poll(generation);
    } catch {if (!disposed) failPreparation();}
  })();
  return Object.assign(() => {
    if (disposed) return;
    disposed = true; generation++;
    delegated?.(); preparation?.dispose(); restore();
    const old = id; id = null; release(old);
  }, {seek});
}
