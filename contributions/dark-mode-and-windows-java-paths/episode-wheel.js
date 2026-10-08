;(() => {
  const installed = Symbol.for('hongguo.episodeWheel');
  if (window[installed]) return;
  window[installed] = true;

  // Three ordinary 16px lines form one step. Small trackpad deltas accumulate;
  // a continuous gesture (including momentum and player remounts) fires once.
  const stepPixels = 48;
  const quietMs = 240;
  const gesture = { last: -Infinity, direction: 0, total: 0, fired: false };
  const controls = '.player-chrome,.player-toolbar,.player-timeline,aside,button,input,select,textarea,a,' +
    '[role="slider"],[role="button"],[contenteditable]:not([contenteditable="false"])';

  document.addEventListener('wheel', event => {
    if (event.defaultPrevented || !event.cancelable || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;
    if (!Number.isFinite(event.deltaY) || event.deltaY === 0 || Math.abs(event.deltaX) >= Math.abs(event.deltaY)) return;
    const target = event.target instanceof Element ? event.target : null;
    const stage = target?.closest('.player-stage');
    if (!stage || target.closest(controls)) return;
    const video = stage.querySelector('video');
    if (!video || video.controls) return;
    const previous = stage.querySelector('.player-toolbar button[aria-label="上一集"]');
    const next = stage.querySelector('.player-toolbar button[aria-label="下一集"]');
    if (!previous && !next) return;

    const now = performance.now();
    if (now - gesture.last > quietMs) {
      gesture.direction = 0;
      gesture.total = 0;
      gesture.fired = false;
    }
    gesture.last = now;
    event.preventDefault();
    if (gesture.fired) return;

    const direction = Math.sign(event.deltaY);
    const button = direction < 0 ? previous : next;
    if (!button || button.matches(':disabled') || button.getAttribute('aria-disabled') === 'true' || stage.getAttribute('aria-busy') === 'true') {
      // Never queue a wheel request while loading or at an episode endpoint.
      gesture.total = 0;
      gesture.fired = true;
      return;
    }
    if (gesture.direction !== direction) gesture.total = 0;
    gesture.direction = direction;
    const linePixels = parseFloat(getComputedStyle(video).lineHeight) || 16;
    const unit = event.deltaMode === 1 ? linePixels : event.deltaMode === 2 ? (stage.clientHeight || innerHeight) : 1;
    gesture.total += Math.abs(event.deltaY) * unit;
    if (gesture.total < stepPixels) return;
    gesture.fired = true;
    gesture.total = 0;
    button.click();
  }, { capture: true, passive: false });
})();
