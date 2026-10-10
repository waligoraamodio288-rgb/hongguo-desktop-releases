// Host supplies React, JSX runtime and its existing authenticated endpoint resolver.
export function createComments({React: O, jsxRuntime: b, resolveEndpoint,
  installStyles, danmaku, emojis}) {
if (!resolveEndpoint || !installStyles || !danmaku || !emojis) throw Error('Missing social integration dependency');
const desktopDanmakuSettings = value => danmaku.settings(value);
const DesktopDanmakuSettings = props => b.jsx(danmaku.Settings, props);
const desktopStartDanmaku = (...args) => danmaku.start(...args);
const desktopLoadEmojis = endpoint => emojis.load(endpoint);
const DesktopEmojiText = props => b.jsx(emojis.Text, props);
function desktopSocialEndpoint(session) {
  try {
    const endpoint = resolveEndpoint(session.streamUrl);
    return {...endpoint, series: new URL(endpoint.url).searchParams.get('series_id'),
      episode: new URL(endpoint.url).searchParams.get('ep')};
  } catch {return null;}
}

async function desktopSocialRead(endpoint, resource, params = {}, signal) {
  const url = new URL(endpoint.origin + '/desktop/social/' + resource);
  url.search = new URLSearchParams({series_id: endpoint.series, ep: endpoint.episode, ...params});
  const abort = new AbortController(), cancel = () => abort.abort();
  if (signal?.aborted) abort.abort();
  signal?.addEventListener('abort', cancel, {once:true});
  const timer = setTimeout(cancel, 15000);
  try {
    const response = await fetch(url, {headers: {'x-api-key': endpoint.key}, signal:abort.signal,
      credentials: 'omit', redirect: 'error', cache: 'no-store'});
    if (!response.ok) throw Error('加载失败，请重试');
    return await response.json();
  } finally {clearTimeout(timer); signal?.removeEventListener('abort', cancel);}
}

function desktopSocialPreference(name, fallback) {
  try {const value = localStorage.getItem('hongguo:' + name); return value === null ? fallback : value === 'on';}
  catch {return fallback;}
}

function desktopSocialSet(media, changes) {
  if (!media) return;
  for (const name of ['danmaku', 'social']) if (typeof changes[name] === 'boolean') {
    try {localStorage.setItem('hongguo:' + name, changes[name] ? 'on' : 'off');} catch {}
  }
  if (changes.settings) {
    changes.settings = desktopDanmakuSettings(changes.settings);
    try {localStorage.setItem('hongguo:danmakuSettings', JSON.stringify(changes.settings));} catch {}
    try {localStorage.setItem('hongguo:danmakuSettingsVersion','2');} catch {}
  }
  media.dispatchEvent(new CustomEvent('desktopsocialsettings', {detail: changes}));
}

function DesktopSocialControls({media, sessionKey}) {
  const [social, setSocial] = O.useState(false);
  O.useEffect(() => {
    const video = media.current; setSocial(false);
    const changed = event => {
      if (typeof event.detail.social === 'boolean') setSocial(event.detail.social && event.detail.tab !== 'episodes');
    };
    video?.addEventListener('desktopsocialsettings', changed);
    return () => video?.removeEventListener('desktopsocialsettings', changed);
  }, [sessionKey]);
  return b.jsxs('span', {className: 'desktop-social-controls', children: [
    b.jsx(DesktopDanmakuSettings,{media,sessionKey}),
    b.jsx('button', {className: 'desktop-social-toggle', 'aria-label': '评论与互动', 'aria-expanded': social,
      'aria-controls': 'desktop-social-drawer', title: '评论、点赞数和收藏数',
      onClick: async () => {
        if (!social && document.fullscreenElement) try {await document.exitFullscreen();} catch {}
        desktopSocialSet(media.current, {social: !social, tab: 'episode'});
      }, children: '评论'}),
  ]});
}

function SocialSession({session, media}) {
  const endpoint = desktopSocialEndpoint(session), key = session.streamUrl;
  const [stats, setStats] = O.useState(null), [statsError, setStatsError] = O.useState('');
  const [tab, setTab] = O.useState('episodes'), [page, setPage] = O.useState(null);
  const [error, setError] = O.useState(''), [busy, setBusy] = O.useState(false);
  const [refresh, setRefresh] = O.useState(0), [metricsRefresh, setMetricsRefresh] = O.useState(0);
  const [danmaku, setDanmaku] = O.useState(() => desktopSocialPreference('danmaku', true));
  const [drawer, setDrawer] = O.useState(() => desktopSocialPreference('social', false));
  const [danmakuError, setDanmakuError] = O.useState('');
  const commenting = drawer && tab !== 'episodes';
  const current = O.useRef(null);
  const [,refreshEmojis]=O.useState(0);
  O.useEffect(()=>{
    const changed=()=>refreshEmojis(value=>value+1);
    window.addEventListener('desktopemojis',changed);
    if(endpoint)desktopLoadEmojis(endpoint);
    return ()=>window.removeEventListener('desktopemojis',changed);
  },[key]);
  O.useEffect(() => {installStyles();}, []);
  O.useEffect(() => {
    const video = media.current;
    const changed = event => {
      if (typeof event.detail.danmaku === 'boolean') setDanmaku(event.detail.danmaku);
      if (typeof event.detail.social === 'boolean') setDrawer(event.detail.social);
      if (['episode', 'series', 'episodes'].includes(event.detail.tab)) setTab(event.detail.tab);
    };
    video?.addEventListener('desktopsocialsettings', changed);
    return () => video?.removeEventListener('desktopsocialsettings', changed);
  }, [key]);
  O.useEffect(() => {
    const video = media.current, layout = video?.closest('.desktop-player-layout');
    layout?.classList.toggle('desktop-social-enabled', drawer);
    layout?.querySelector('aside')?.setAttribute('aria-label', drawer ? '评论与互动抽屉' : '选集');
    const frame = requestAnimationFrame(() => video?.dispatchEvent(new Event('desktopsociallayout')));
    return () => {cancelAnimationFrame(frame); layout?.classList.remove('desktop-social-enabled');};
  }, [key, drawer]);
  O.useEffect(() => {
    const abort = new AbortController(); setStats(null); setStatsError('');
    if (endpoint && commenting) desktopSocialRead(endpoint, 'metrics', {refresh: metricsRefresh > 0}, abort.signal)
      .then(value => {if (!abort.signal.aborted) setStats(value);})
      .catch(e => {if (!abort.signal.aborted) setStatsError('互动计数加载失败，请重试');});
    return () => abort.abort();
  }, [key, metricsRefresh, commenting]);
  O.useEffect(() => {
    const own = {abort: new AbortController(), busy: false}; current.current = own;
    setPage(null); setError('');
    setBusy(false);
    if (endpoint && commenting) load('', own);
    return () => {own.abort.abort(); if (current.current === own) current.current = null;};
  }, [key, tab, refresh, drawer]);
  async function load(cursor = '', own = current.current) {
    if (!own || own.busy || own.abort.signal.aborted) return;
    own.busy = true; setBusy(true); setError('');
    try {
      const result = await desktopSocialRead(endpoint, 'comments', {kind: tab, cursor}, own.abort.signal);
      if (current.current !== own) return;
      setPage(previous => ({...result, has_more: result.has_more && result.cursor !== cursor,
        items: cursor && previous ? [...new Map([...previous.items, ...result.items].map(item => [item.id, item])).values()] : result.items}));
    } catch(e) {if (!own.abort.signal.aborted && current.current === own) setError('评论加载失败，请重试');}
    finally {own.busy = false; if (current.current === own) setBusy(false);}
  }
  O.useEffect(() => {
    setDanmakuError('');
    try {localStorage.setItem('hongguo:danmaku', danmaku ? 'on' : 'off');} catch {}
    if (!endpoint || !danmaku || !media.current) return;
    return desktopStartDanmaku(media.current, endpoint, setDanmakuError);
  }, [key, danmaku]);
  if (!endpoint) return null;
  return b.jsxs('section', {id: 'desktop-social-drawer', className: 'desktop-social', 'data-tab': tab,
    'aria-label': tab === 'episodes' ? '选集' : '评论与互动', hidden: !drawer, children: [
    tab !== 'episodes' && b.jsxs('div', {className: 'desktop-social-header', children: [
      b.jsx('h3', {children: '评论与互动'}), b.jsx('button', {'aria-label': '关闭评论抽屉', title: '关闭评论抽屉',
        onClick: () => {desktopSocialSet(media.current, {social: false}); media.current?.closest('.player-stage')?.querySelector('.desktop-social-toggle')?.focus();}, children: '×'})]}),
    b.jsxs('div', {className: 'desktop-social-tabs', role: 'tablist', 'aria-label': '抽屉内容', children: [
      ...[['episodes', '选集'], ['episode', '本集评论'], ['series', '整剧剧评']].map(([name, label]) => b.jsx('button', {
        role: 'tab', 'aria-selected': tab === name, onClick: () => desktopSocialSet(media.current, {social: true, tab: name}), children: label}, name))]}),
    tab !== 'episodes' && b.jsxs('div', {className: 'desktop-social-toolbar', children: [
      b.jsx('span', {children: '本集赞 ' + (stats ? stats.likes.toLocaleString('zh-CN') : '…')}),
      b.jsx('span', {children: '评论 ' + (stats ? stats.comments.toLocaleString('zh-CN') : '…')}),
      b.jsx('button', {onClick: () => setMetricsRefresh(n => n + 1), 'aria-label': '刷新互动计数', children: '刷新'}),
      b.jsx('small', {className: 'desktop-social-favorite', children: '整剧收藏 ' + (stats ? stats.favorites.toLocaleString('zh-CN') : '…')})]}),
    tab !== 'episodes' && statsError && b.jsx('p', {className: 'desktop-social-error', role: 'status', children: statsError}),
    tab !== 'episodes' && danmakuError && b.jsx('p', {className: 'desktop-social-error', role: 'status', children: danmakuError}),
    tab !== 'episodes' && b.jsxs('div', {className: 'desktop-social-list', role: 'tabpanel', 'aria-label': tab === 'episode' ? '本集评论' : '整剧剧评', children: [
      b.jsxs('div', {className: 'desktop-social-list-heading', children: [
        b.jsx('small', {className: 'desktop-social-status', children: page ? '共 ' + page.total.toLocaleString('zh-CN') + ' 条' : '评论'}),
        b.jsx('button', {disabled: busy, onClick: () => setRefresh(n => n + 1), children: '刷新评论'})]}),
      page?.items.map(item => b.jsx(DesktopSocialComment, {item, endpoint, replies: tab === 'episode'}, key + tab + item.id)),
      page && !page.items.length && b.jsx('p', {className: 'desktop-social-status', children: '暂无评论'}),
      error && b.jsxs('p', {className: 'desktop-social-error', role: 'status', children: [error, ' ', b.jsx('button', {
        onClick: () => load(page?.cursor || ''), children: '重试'})]}),
      busy && b.jsx('p', {className: 'desktop-social-status', role: 'status', children: '正在加载…'}),
      page?.has_more && b.jsx('button', {disabled: busy, onClick: () => load(page.cursor), children: '加载更多评论'})]})]});
}

function DesktopSocialComment({item, endpoint, replies}) {
  const [open, setOpen] = O.useState(false), [page, setPage] = O.useState(null);
  const [busy, setBusy] = O.useState(false), [error, setError] = O.useState('');
  const own = O.useRef(null);
  O.useEffect(() => {
    own.current = {abort: new AbortController(), busy: false};
    return () => {own.current.abort.abort();};
  }, []);
  async function load(cursor = '') {
    const request = own.current;
    if (!request || request.busy || request.abort.signal.aborted) return;
    request.busy = true; setBusy(true); setError('');
    try {
      const result = await desktopSocialRead(endpoint, 'replies', {comment_id: item.id, cursor}, request.abort.signal);
      if (own.current === request && !request.abort.signal.aborted) setPage(previous => ({...result, has_more: result.has_more && result.cursor !== cursor,
        items: cursor && previous ? [...new Map([...previous.items, ...result.items].map(row => [row.id, row])).values()] : result.items}));
    } catch (e) {if (!request.abort.signal.aborted) setError('回复加载失败，请重试');}
    finally {request.busy = false; if (!request.abort.signal.aborted) setBusy(false);}
  }
  return b.jsxs('article', {className: 'desktop-social-item', children: [
    b.jsx('strong', {children: item.author}),
    b.jsx('p', {children: b.jsx(DesktopEmojiText,{text:item.text || (item.image_count ? '[图片评论]' : '[无文字评论]')})}),
    b.jsx('small', {children: (item.created_at ? new Date(item.created_at * 1000).toLocaleDateString('zh-CN') + ' · ' : '') + '赞 ' + item.likes}),
    replies && item.replies > 0 && b.jsx('button', {'aria-expanded': open, onClick: () => {
      setOpen(!open); if (open) {own.current?.abort.abort(); own.current = {abort:new AbortController(),busy:false}; setBusy(false);} else if (!page && !busy) load();}, children: open ? '收起回复' : '查看 ' + item.replies + ' 条回复'}),
    open && b.jsxs('div', {className: 'desktop-social-replies', children: [
      page?.items.map(row => b.jsx(DesktopSocialComment, {item: row, endpoint, replies: false}, row.id)),
      page && !page.items.length && b.jsx('p', {children: '暂无回复'}),
      busy && b.jsx('p', {role: 'status', children: '正在加载回复…'}),
      error && b.jsxs('p', {role: 'status', children: [error, ' ', b.jsx('button', {onClick: () => load(page?.cursor || ''), children: '重试'})]}),
      page?.has_more && b.jsx('button', {disabled: busy, onClick: () => load(page.cursor), children: '加载更多回复'})]})]});
}

function DesktopSocial(props) {return b.jsx(SocialSession, props, props.session.streamUrl);}
return {Drawer:DesktopSocial, Controls:DesktopSocialControls, Comment:DesktopSocialComment,
  read:desktopSocialRead, preference:desktopSocialPreference, set:desktopSocialSet, endpoint:desktopSocialEndpoint};
}
