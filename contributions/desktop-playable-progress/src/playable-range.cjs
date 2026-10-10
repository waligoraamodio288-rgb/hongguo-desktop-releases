"use strict";

function validateRange(range, duration) {
  return Number.isFinite(duration) && duration > 0 &&
    Array.isArray(range) && range.length === 2 && range.every(Number.isFinite) &&
    range[0] >= 0 && range[1] >= range[0] && range[1] <= duration + 0.001
    ? [Math.min(range[0], duration), Math.min(range[1], duration)] : null;
}

function rangeStyle(range, duration) {
  const [start, end] = validateRange(range, duration) || [0, 0];
  const percent = value => `${duration > 0 ? value / duration * 100 : 0}%`;
  return { "--buffered-start": percent(start), "--buffered": percent(end) };
}

// fetchStatus(sessionId, {signal}) must use the host's authenticated local API.
// Playback pause/resume is deliberately not a lifecycle event for this poller.
function createRangePoller({ fetchStatus, onRange, onError = () => {},
  setTimer = setTimeout, clearTimer = clearTimeout }) {
  let epoch = 0, timer = null, request = null;
  function stop() {
    epoch++;
    if (timer !== null) clearTimer(timer);
    timer = null;
    if (request) request.abort();
    request = null;
  }
  function start(sessionId) {
    stop();
    const current = epoch;
    onRange([0, 0]);
    async function tick() {
      if (epoch !== current) return;
      const controller = new AbortController();
      request = controller;
      let delay = 1500;
      try {
        const status = await fetchStatus(sessionId, { signal: controller.signal });
        if (epoch !== current) return;
        onRange(validateRange(status.playableRange, status.duration) || [0, 0]);
        delay = status.state === "complete" ? 10000 : 1500;
      } catch (error) {
        if (epoch !== current) return;
        onError(error); // Keep the last valid range on a transient transport error.
      } finally {
        if (request === controller) request = null;
        if (epoch === current) timer = setTimer(tick, delay);
      }
    }
    return tick();
  }
  return { start, stop };
}

module.exports = { validateRange, rangeStyle, createRangePoller };
