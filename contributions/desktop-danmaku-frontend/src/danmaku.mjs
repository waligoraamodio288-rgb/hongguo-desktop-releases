export function createDanmaku({React: O, jsxRuntime: b, read, preference, set, emojis}) {
if (!read || !preference || !set || !emojis) throw Error('Missing danmaku integration dependency');
const desktopSocialRead = (...args) => read(...args);
const desktopSocialPreference = (...args) => preference(...args);
const desktopSocialSet = (...args) => set(...args);
const desktopLoadEmojis = (...args) => emojis.load(...args);
const desktopEmojiParts = (...args) => emojis.parts(...args);
const DesktopEmojiText = props => b.jsx(emojis.Text,props);
function desktopDanmakuSettings(value) {
  if (!value) try {
    value = JSON.parse(localStorage.getItem('hongguo:danmakuSettings'));
    if (value && localStorage.getItem('hongguo:danmakuSettingsVersion') !== '2') {
      value = {...value,duration:Math.min(24,Math.max(4,Math.round((value.duration || 8)*1.8)))};
      localStorage.setItem('hongguo:danmakuSettings',JSON.stringify(value));
      localStorage.setItem('hongguo:danmakuSettingsVersion','2');
    }
  } catch {}
  const defaults = {opacity: 80, lanes: 3, fontSize: 28, duration: 14}, result = {};
  for (const [name, low, high] of [['opacity',10,100],['lanes',1,6],['fontSize',18,36],['duration',4,24]]) {
    result[name] = Number.isInteger(value?.[name]) ? Math.min(high, Math.max(low, value[name])) : defaults[name];
  }
  return result;
}

function DesktopDanmakuSettings({media, sessionKey}) {
  const [open, setOpen] = O.useState(false), [list, setList] = O.useState(false);
  const [settings, setSettings] = O.useState(desktopDanmakuSettings);
  const [enabled, setEnabled] = O.useState(() => desktopSocialPreference('danmaku', true));
  const [rows, setRows] = O.useState([]), panel = O.useRef(null), hoverTimer = O.useRef(null);
  O.useEffect(() => () => clearTimeout(hoverTimer.current), []);
  O.useEffect(() => {
    const video = media.current;
    const changed = event => {
      if (event.detail.settings) setSettings(event.detail.settings);
      if (typeof event.detail.danmaku === 'boolean') setEnabled(event.detail.danmaku);
    };
    const loaded = () => setRows(video?.desktopDanmakuRows || []);
    video?.addEventListener('desktopsocialsettings', changed);
    video?.addEventListener('desktopdanmakulist', loaded); loaded();
    return () => {video?.removeEventListener('desktopsocialsettings', changed); video?.removeEventListener('desktopdanmakulist', loaded);};
  }, [sessionKey]);
  O.useLayoutEffect(() => {
    const video = media.current;
    const layout = () => {
      if (panel.current && video) {
        const rect = video.getBoundingClientRect(), node = panel.current;
        node.style.width = Math.max(180, Math.min(320, rect.width - 24)) + 'px';
        node.style.maxHeight = Math.max(120, rect.height - 104) + 'px';
        node.style.left = rect.left + 12 + 'px';
        node.style.top = Math.max(rect.top + 8, rect.bottom - 92 - node.offsetHeight) + 'px';
      }
      video?.dispatchEvent(new Event('desktopsociallayout'));
    };
    layout(); const observer = new ResizeObserver(layout);
    if (video) observer.observe(video);
    if (panel.current) observer.observe(panel.current);
    window.addEventListener('resize', layout);
    return () => {observer.disconnect(); window.removeEventListener('resize', layout);};
  }, [open, list, sessionKey]);
  const update = (name, value) => desktopSocialSet(media.current, {settings: {...settings, [name]: Number(value)}});
  return b.jsxs('span', {className: 'desktop-danmaku-control',
    onPointerEnter: () => {clearTimeout(hoverTimer.current); setOpen(true);},
    onPointerLeave: () => {hoverTimer.current = setTimeout(() => setOpen(false), 250);}, children: [
    b.jsx('button', {className: 'desktop-danmaku-toggle', 'aria-label': '弹幕', 'aria-pressed': enabled,
      'aria-expanded': open, title: '点击开关弹幕，悬停调整设置',
      onClick: () => desktopSocialSet(media.current, {danmaku: !enabled}), children: '弹幕'}),
    open && b.jsxs('section', {ref: panel, className: 'desktop-danmaku-panel', 'aria-label': '弹幕设置', children: [
      b.jsxs('div', {className: 'desktop-danmaku-heading', children: [b.jsx('strong', {children: '弹幕设置'}),
        b.jsx('button', {'aria-label': '恢复默认弹幕设置', onClick: () => desktopSocialSet(media.current,
          {settings: {opacity:80,lanes:3,fontSize:28,duration:14}}), children: '恢复默认'}),
        b.jsx('button', {'aria-label': '关闭弹幕设置', onClick: () => setOpen(false), children: '×'})]}),
      ...[['opacity','不透明度',10,100,10,settings.opacity+'%'], ['lanes','显示区域',1,6,1,'顶部 '+settings.lanes+' 行'],
        ['fontSize','字体大小',18,36,2,settings.fontSize+''], ['duration','移动速度',4,24,1,
          settings.duration<14?'较快':settings.duration>14?'较慢':'适中']].map(([name,label,min,max,step,text]) =>
        b.jsxs('label', {className: 'desktop-danmaku-setting', children: [b.jsx('span', {children:label}),
          b.jsx('input', {type:'range',min,max,step,value:name==='duration'?28-settings[name]:settings[name], 'aria-label':label,
            onChange:event=>update(name,name==='duration'?28-Number(event.target.value):event.target.value)}), b.jsx('output',{children:text})]},name)),
      b.jsxs('div', {className:'desktop-danmaku-setting-footer',children:[b.jsx('span',{children:'弹幕开关'}),
        b.jsx('button', {'aria-label':'设置面板弹幕开关','aria-pressed':enabled,
          onClick:()=>desktopSocialSet(media.current,{danmaku:!enabled}),children:enabled?'已开启':'已关闭'})]}),
      b.jsx('button', {className:'desktop-danmaku-list-open','aria-expanded':list,onClick:()=>setList(!list),
        children:(list?'收起弹幕列表':'弹幕列表')+' · '+rows.length}),
      list && b.jsxs('div', {className:'desktop-danmaku-list',children:[
        b.jsx('small',{children:'当前播放附近已加载的弹幕'}),
        ...rows.map(row=>b.jsxs('p',{children:[b.jsx('time',{children:
          Math.floor(row.offset_ms/60000)+':'+String(Math.floor(row.offset_ms/1000)%60).padStart(2,'0')}),b.jsx(DesktopEmojiText,{text:row.text})]},row.id)),
        !rows.length&&b.jsx('p',{children:enabled?'暂未加载到弹幕':'开启弹幕后加载列表'})]})]})]});
}

function desktopDanmakuRows(items, settings = desktopDanmakuSettings(), previous = []) {
  const unique = new Map();
  for (const item of items) if (item.id && item.text && Number.isInteger(item.offset_ms)) unique.set(item.id, item);
  const kept = new Map(previous.filter(row => unique.has(row.id) && row.lane < settings.lanes).map(row=>[row.id,row]));
  const lanes = Array.from({length:settings.lanes},()=>[]), gap = settings.duration * 400;
  for (const row of kept.values()) lanes[row.lane].push([row.offset_ms, row.offset_ms + gap]);
  return [...unique.values()].sort((a, b) => a.offset_ms - b.offset_ms || a.id.localeCompare(b.id)).flatMap(item => {
    if (kept.has(item.id)) return [kept.get(item.id)];
    const lane = lanes.findIndex(intervals => intervals.every(([start,end]) => item.offset_ms + gap <= start || item.offset_ms >= end));
    if (lane < 0) return [];
    lanes[lane].push([item.offset_ms, item.offset_ms + gap]);
    return [{id: item.id, text: [...item.text].slice(0, 160).join(''), offset_ms: item.offset_ms, lane}];
  }).slice(-300);
}

function desktopStartDanmaku(media, endpoint, status) {
  desktopLoadEmojis(endpoint);
  const abort = new AbortController(), stage = media.closest('.player-stage');
  const layer = document.createElement('div'); layer.className = 'desktop-danmaku';
  layer.setAttribute('aria-hidden', 'true'); stage?.append(layer);
  let stopped = false, busy = false, generation = 0, rows = [], raw = [], last = -1, lastClock = Date.now();
  let next = 0, cursor = '', ended = false, retryAt = 0, frame;
  let settings = desktopDanmakuSettings();
  const publish = () => {
    media.desktopDanmaku = rows.map(({text, offset_ms, lane}) => ({text, offset_ms, lane}));
    media.desktopDanmakuSettings = settings;
    media.desktopDanmakuRows = raw;
    media.dispatchEvent(new Event('desktopdanmaku'));
    media.dispatchEvent(new Event('desktopdanmakulist'));
  };
  const changed = event => {
    if (!event.detail.settings) return;
    settings = desktopDanmakuSettings(event.detail.settings);
    rows = desktopDanmakuRows(raw, settings); publish();
  };
  function reset() {
    generation++; raw = []; rows = []; cursor = ''; ended = false; retryAt = 0;
    last = -1; lastClock = Date.now();
    next = Math.floor(Math.max(0, media.currentTime || 0) / 30) * 30000;
    publish(); layer.replaceChildren();
  }
  async function load() {
    const time = Math.max(0, media.currentTime || 0) * 1000;
    if (busy || ended || Date.now() < retryAt || time + 5000 < next) return;
    busy = true; const own = generation, offset = next, ownCursor = cursor;
    try {
      const page = await desktopSocialRead(endpoint, 'danmaku', {offset_ms: offset, cursor: ownCursor}, abort.signal);
      if (stopped || own !== generation) return;
      raw = raw.filter(item => item.offset_ms >= time - 24000).concat(page.items).slice(-600);
      raw = [...new Map(raw.map(item=>[item.id,item])).values()];
      rows = desktopDanmakuRows(raw, settings, rows); publish();
      const advance = page.next_offset_ms > offset;
      if (advance) {next = page.next_offset_ms; cursor = page.cursor;}
      else if (page.has_more && page.cursor && page.cursor !== ownCursor) cursor = page.cursor;
      else {next = offset + 30000; cursor = '';}
      ended = Number.isFinite(media.duration) && media.duration > 0 && next >= media.duration * 1000;
      status('');
    } catch (error) {
      if (!stopped && own === generation && error.name !== 'AbortError') {
        retryAt = Date.now() + 5000; status('弹幕加载失败，正在重试');
      }
    } finally {busy = false;}
  }
  function tick() {
    if (stopped) return;
    const time = Number(media.currentTime) || 0;
    const clock = Date.now(), elapsed = Math.max(0, (clock-lastClock)/1000) * (media.playbackRate || 1);
    if (last >= 0 && (time < last - .7 || time > last + Math.max(3, elapsed + .7))) reset();
    last = time; lastClock = clock; load();
    layer.hidden = !!stage?.classList.contains('desktop-native-playback');
    if (!layer.hidden) {
      const width = media.clientWidth || stage?.clientWidth || 1000;
      const active = rows.filter(row => time * 1000 >= row.offset_ms && time * 1000 < row.offset_ms + settings.duration * 1000);
      const existing = new Map([...layer.children].map(node => [node.dataset.id, node]));
      for (const row of active) {
        let node = existing.get(row.id);
        if (!node) {node = document.createElement('span'); node.dataset.id = row.id; layer.append(node);}
        if (node.desktopEmojiVersion !== emojis.catalog || node.desktopText !== row.text) {
          node.replaceChildren(...desktopEmojiParts(row.text).map(part=>{
            if (!emojis.catalog[part]) return document.createTextNode(part);
            const image=document.createElement('img'); image.className='desktop-emoji'; image.src=emojis.catalog[part]; image.alt=part; return image;
          }));
          node.desktopEmojiVersion=emojis.catalog; node.desktopText=row.text;
        }
        existing.delete(row.id);
        const age = (time * 1000 - row.offset_ms) / (settings.duration * 1000);
        const scale = Math.max(0.3, (media.clientHeight - 84 || 562) / 562), size = settings.fontSize * scale;
        node.style.fontSize = size + 'px'; node.style.opacity = settings.opacity / 100;
        node.style.transform = `translate3d(${width - (width + node.offsetWidth) * age}px,${(25 + row.lane * (settings.fontSize+15)) * scale}px,0)`;
      }
      for (const node of existing.values()) node.remove();
    }
    frame = requestAnimationFrame(tick);
  }
  media.addEventListener('seeking', reset); media.addEventListener('desktopsocialsettings', changed); reset(); tick();
  return () => {
    stopped = true; generation++; abort.abort(); cancelAnimationFrame(frame);
    media.removeEventListener('seeking', reset); media.removeEventListener('desktopsocialsettings', changed);
    layer.remove(); rows = []; raw = []; publish();
  };
}


return {Settings:DesktopDanmakuSettings,settings:desktopDanmakuSettings,rows:desktopDanmakuRows,start:desktopStartDanmaku};
}
