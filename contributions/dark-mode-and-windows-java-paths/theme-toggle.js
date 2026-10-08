;(() => {
  const key = 'hongguo-local-theme';
  const valid = ['dark', 'light', 'system'];
  const media = matchMedia('(prefers-color-scheme: dark)');
  let preference = 'dark';
  try { const saved = localStorage.getItem(key); if (valid.includes(saved)) preference = saved; } catch {}
  function apply() {
    const dark = preference === 'dark' || (preference === 'system' && media.matches);
    document.documentElement.dataset.localTheme = dark ? 'dark' : 'light';
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = dark ? '#16171b' : '#ffffff';
  }
  function mount() {
    const section = document.querySelector('.settings-page');
    if (!section || section.querySelector('#local-theme-row')) return;
    const row = document.createElement('div');
    row.id = 'local-theme-row'; row.className = 'settings-row';
    const label = document.createElement('label');
    label.htmlFor = 'local-theme-select'; label.textContent = '外观';
    const select = document.createElement('select');
    select.id = 'local-theme-select'; select.setAttribute('aria-label', '外观主题');
    [['dark','深色'],['light','浅色'],['system','跟随系统']].forEach(([value,text]) => {
      const option = document.createElement('option'); option.value=value; option.textContent=text; select.append(option);
    });
    select.value = preference;
    select.addEventListener('change', () => {
      preference = select.value;
      try { localStorage.setItem(key, preference); } catch {}
      apply();
    });
    row.append(label,select);
    const heading = section.querySelector('h1');
    if (heading) heading.after(row); else section.prepend(row);
  }
  apply();
  media.addEventListener('change', apply);
  const start = () => { mount(); new MutationObserver(mount).observe(document.body,{childList:true,subtree:true}); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
})();
