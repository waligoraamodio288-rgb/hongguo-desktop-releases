export function installSocialStyles() {
  if (document.getElementById('desktop-social-style')) return;
    const style = document.createElement('style'); style.id = 'desktop-social-style';
    style.textContent = `.desktop-social{border-top:1px solid #ffffff20;padding:12px 0;color:inherit;font-size:13px;min-height:0}.desktop-social-toolbar,.desktop-social-tabs{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.desktop-social-toolbar small{color:#aeb5bf}.desktop-social button{padding:5px 9px;border:1px solid #ffffff25;border-radius:6px;background:#ffffff09;color:inherit;cursor:pointer}.desktop-social button:disabled{opacity:.5;cursor:default}.desktop-social-tabs{margin:10px 0}.desktop-social-tabs button[aria-selected=true]{background:#f45a4440;color:#ffab9d}.desktop-social-list{max-height:250px;overflow:auto;overscroll-behavior:contain;scrollbar-width:thin}.desktop-social-item{padding:10px 2px;border-bottom:1px solid #ffffff12;overflow-wrap:anywhere}.desktop-social-item p{margin:5px 0;white-space:pre-wrap;line-height:1.6}.desktop-social-item small,.desktop-social-status{color:#aeb5bf}.desktop-social-replies{margin:8px 0 0 12px;padding-left:10px;border-left:2px solid #ffffff20}.desktop-social-error{color:#ffb4a7}.desktop-danmaku{position:absolute;inset:0 0 84px;overflow:hidden;pointer-events:none;z-index:4}.desktop-danmaku span{position:absolute;left:0;top:0;white-space:nowrap;font:600 22px sans-serif;color:#fff;text-shadow:1px 1px 2px #000,-1px -1px 2px #000;will-change:transform}.desktop-player.mini .desktop-social{display:none}`;
    style.textContent += `
      .desktop-emoji{display:inline-block;width:1.3em;height:1.3em;vertical-align:-.25em;object-fit:contain;border:0;pointer-events:none}
      .desktop-danmaku span{font-weight:400}
      .desktop-social-controls{display:inline-flex;align-items:center;gap:6px;flex-shrink:0}
      .desktop-player-layout{height:100%;overflow:hidden;contain:size}
      .desktop-danmaku-control{display:inline-flex;align-items:center;gap:0}
      .player-stage:has(.desktop-danmaku-panel) .player-chrome{opacity:1!important;pointer-events:auto!important}
      .desktop-danmaku-panel{position:fixed;z-index:1000;box-sizing:border-box;width:320px;overflow-y:auto;background:#272832;color:#e7e7ee;border:1px solid #ffffff14;border-radius:16px;padding:18px;box-shadow:0 8px 28px #0005;font:13px sans-serif;cursor:default;text-align:left;user-select:none;color-scheme:dark;scrollbar-width:thin;scrollbar-color:#51525c transparent}
      .desktop-danmaku-heading{display:flex;align-items:center;gap:8px;padding-bottom:14px;border-bottom:1px solid #ffffff18}
      .desktop-danmaku-heading strong{font-size:16px;margin-right:auto;white-space:nowrap}
      .player-toolbar .desktop-social-controls .desktop-danmaku-panel button{display:inline-block;min-width:0;min-height:0;width:auto;height:auto;font-size:12px;background:transparent;border:0;color:#c6c6d1;padding:3px;white-space:nowrap}
      .desktop-danmaku-setting{display:grid;grid-template-columns:70px minmax(60px,1fr) 58px;align-items:center;gap:8px;margin:20px 0;color:#a9a9b5}
      .desktop-danmaku-setting input{width:100%;min-width:0;accent-color:#fb7299;cursor:pointer}
      .desktop-danmaku-setting output{text-align:right;color:#ddd;font-size:12px}
      .desktop-danmaku-setting-footer{border-top:1px solid #ffffff18;padding:16px 0;display:flex;align-items:center;justify-content:space-between;color:#a9a9b5}
      .player-toolbar .desktop-social-controls .desktop-danmaku-panel button[aria-pressed=true]{background:#fb7299;border-radius:12px;padding:4px 10px;color:#fff}
      .player-toolbar .desktop-social-controls .desktop-danmaku-panel .desktop-danmaku-list-open{display:block;width:100%;text-align:left;border-top:1px solid #ffffff18;padding:14px 0 0}
      .desktop-danmaku-list{max-height:180px;overflow-y:auto;margin-top:12px;user-select:text;scrollbar-width:thin;scrollbar-color:#51525c transparent}
      .desktop-danmaku-list small{color:#a9a9b5}.desktop-danmaku-list p{display:flex;gap:12px;overflow-wrap:anywhere;line-height:1.5;margin:10px 0}.desktop-danmaku-list time{color:#a9a9b5;flex-shrink:0}
      .player-toolbar .desktop-social-controls button{font-size:12px;min-width:44px;padding:5px 8px;height:30px;border:1px solid #ffffff28;border-radius:7px;color:#bbb}
      .player-toolbar .desktop-social-controls button[aria-pressed=true],.player-toolbar .desktop-social-controls button[aria-expanded=true]{color:#ffacc4;background:#fb72991e;border-color:#fb729970}
      /* Include the pin in the measured controls row; the original absolute pin sits outside its group. */
      .app-shell:has(.desktop-player:not(.mini)) .window-controls.dark .window-pin{position:static}
      .desktop-player header .desktop-selection-open{margin-left:auto;border:1px solid #ffffff25;border-radius:7px;background:#ffffff08;color:#eee;padding:6px 12px;cursor:pointer}
      .desktop-player header .desktop-selection-open{position:absolute;top:8px;right:190px;height:32px}
      .desktop-player-layout:not(.desktop-social-enabled){grid-template-columns:minmax(0,1fr)}
      .desktop-player-layout:not(.desktop-social-enabled) aside{display:none}
      .desktop-player-layout.desktop-social-enabled{grid-template-columns:minmax(0,1fr) clamp(320px,29vw,420px)}
      .desktop-player-layout.desktop-social-enabled aside{display:flex;overflow:hidden;padding:0;background:#1c1d22;animation:desktopDrawerIn .18s ease-out}
      .desktop-player-layout aside > :not(.desktop-social){margin-left:18px;margin-right:18px}
      .desktop-player-layout aside:has(.desktop-social:not([data-tab=episodes])) > :not(.desktop-social){display:none!important}
      .desktop-social{order:-1;display:flex;flex:1;flex-direction:column;min-height:0;border:0;padding:0}
      .desktop-social[hidden]{display:none!important}
      .desktop-social[data-tab=episodes]{flex:none}
      .desktop-social-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 18px;border-bottom:1px solid #ffffff14}
      .desktop-social-header h3{margin:0;font-size:16px;font-weight:600}
      .desktop-social-header button{font-size:20px;line-height:20px;padding:3px 7px;background:transparent;border:0}
      .desktop-social-tabs{margin:0;padding:12px 18px 10px;gap:8px;border-bottom:1px solid #ffffff14;flex-shrink:0}
      .desktop-social-tabs button{border:0;background:transparent;color:#aaa;border-radius:0;padding:5px 2px;border-bottom:2px solid transparent}
      .desktop-social-tabs button[aria-selected=true]{color:#fff;background:transparent;border-bottom-color:#fb7299}
      .desktop-social-toolbar{padding:12px 18px;font-size:13px;gap:8px;flex-shrink:0}
      .desktop-social-toolbar .desktop-social-favorite{width:100%;color:#aeb5bf;font-size:12px}
      .desktop-social-toolbar button{margin-left:auto;font-size:12px}
      .desktop-social-list{flex:1;max-height:none;min-height:0;padding:0 18px 18px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#51525c transparent}
      .desktop-social-item{padding:14px 0}.desktop-social-item strong{font-size:13px;color:#b8bbc8;font-weight:500}
      .desktop-player-layout aside .desktop-social-item p{font-size:14px;opacity:1;color:#eee;line-height:1.65;margin:7px 0}
      .desktop-social-item > button{margin-left:8px;font-size:12px;border:0;background:transparent;color:#aeb5bf;padding:3px 0}
      .desktop-social-replies{margin-left:0;border-left:0;padding-left:12px}
      .desktop-social > .desktop-social-error{padding:0 18px;font-size:12px}
      .desktop-social > .desktop-social-reload{padding:8px 18px;flex-shrink:0}
      .desktop-social-list-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;position:sticky;top:0;background:#1c1d22;padding:4px 0 8px;z-index:1}
      .desktop-social-list-heading button{background:transparent;border:0;color:#aeb5bf;font-size:12px;padding:4px 0}
      .desktop-player.mini .desktop-social-controls,.desktop-player.mini .desktop-selection-open{display:none}
      .desktop-player.theater .desktop-player-layout.desktop-social-enabled{grid-template-columns:minmax(0,1fr) clamp(320px,29vw,420px)}
      .desktop-player.theater .desktop-player-layout.desktop-social-enabled aside{display:flex}
      @keyframes desktopDrawerIn{from{opacity:0;transform:translateX(18px)}to{opacity:1;transform:translateX(0)}}
      @media(max-width:800px){.desktop-player-layout.desktop-social-enabled{grid-template-columns:minmax(0,1fr) min(44vw,340px)}.desktop-social-tabs,.desktop-social-toolbar,.desktop-social-header{padding-left:12px;padding-right:12px}.desktop-social-list{padding-left:12px;padding-right:12px}.player-toolbar .desktop-social-controls{gap:2px}.player-toolbar .desktop-social-controls button{min-width:34px;padding:4px}}
      @media(prefers-reduced-motion:reduce){.desktop-player-layout.desktop-social-enabled aside{animation:none}}
    `;
    document.head.append(style);
}

export function createSelection({React: O, jsxRuntime: b, set: desktopSocialSet}) {
function DesktopSocialSelection({media}) {
  const button = O.useRef(null);
  O.useLayoutEffect(() => {
    const header = button.current?.closest('header');
    if (!header) return;
    const layout = () => {
      const rect = header.getBoundingClientRect(), controls = document.querySelector('.window-controls');
      const controlRect = controls?.getBoundingClientRect();
      let edge = rect.right - 12;
      if (controlRect?.width && controlRect.top < rect.bottom && controlRect.bottom > rect.top) edge = Math.min(edge, controlRect.left - 12);
      const mini = header.querySelector('.player-mini-toggle');
      if (mini && mini.getBoundingClientRect().width) {
        mini.style.right = rect.right - edge + 'px';
        edge -= mini.getBoundingClientRect().width + 12;
      }
      if (button.current) button.current.style.right = rect.right - edge + 'px';
    };
    layout(); const observer = new ResizeObserver(layout);
    observer.observe(header);
    const controls = document.querySelector('.window-controls');
    if (controls) observer.observe(controls);
    window.addEventListener('resize', layout);
    return () => {observer.disconnect(); window.removeEventListener('resize', layout);};
  }, []);
  return b.jsx('button', {ref:button, className: 'desktop-selection-open', 'aria-label': '打开选集',
    'data-tauri-drag-region': 'false', onClick: () => {
      const drawer = media.current?.closest('.desktop-player-layout')?.querySelector('.desktop-social');
      desktopSocialSet(media.current, {social: !drawer || drawer.hidden || drawer.dataset.tab !== 'episodes', tab: 'episodes'});
    }, children: '选集'});
}


return DesktopSocialSelection;
}
