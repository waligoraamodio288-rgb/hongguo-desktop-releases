"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { validateRange, rangeStyle, createRangePoller } = require("../src/playable-range.cjs");

const deferred = () => {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
};
function harness(fetchStatus) {
  const ranges = [], timers = new Map();
  let next = 0;
  const poller = createRangePoller({ fetchStatus, onRange: r => ranges.push(r),
    setTimer: (callback, delay) => { timers.set(++next, { callback, delay }); return next; },
    clearTimer: id => timers.delete(id) });
  return { poller, ranges, timers, async tick() {
    const [id, timer] = timers.entries().next().value;
    timers.delete(id);
    await timer.callback();
  }};
}

test("invalid ranges never claim ready bytes; full and window styles differ", () => {
  for (const value of [null, [0], [0, Infinity], [-1, 2], [4, 2], [0, 64], ["0", 2]])
    assert.equal(validateRange(value, 63), null);
  assert.equal(validateRange([0, 0], NaN), null);
  assert.deepEqual(rangeStyle([0, 63], 63), { "--buffered-start": "0%", "--buffered": "100%" });
  assert.deepEqual(rangeStyle([30, 60], 120), { "--buffered-start": "25%", "--buffered": "50%" });
  assert.deepEqual(rangeStyle(null, 63), { "--buffered-start": "0%", "--buffered": "0%" });
});

test("pause needs no play/timeupdate event to grow range to 100 percent", async () => {
  let step = 0;
  const h = harness(async () => ({ duration: 63, playableRange: [0, ++step === 1 ? 20 : 63],
    state: step === 1 ? "preparing" : "complete" }));
  await h.poller.start("session-a");
  assert.deepEqual(h.ranges, [[0, 0], [0, 20]]);
  assert.equal([...h.timers.values()][0].delay, 1500);
  await h.tick();
  assert.deepEqual(h.ranges.at(-1), [0, 63]);
  assert.equal([...h.timers.values()][0].delay, 10000);
  // Resume only changes the host playback state; the same range stays valid.
  await h.tick();
  assert.deepEqual(h.ranges.at(-1), [0, 63]);
  h.poller.stop();
});

test("switch resets immediately and late responses cannot fill the new episode", async () => {
  const old = deferred();
  let signal;
  const h = harness((id, options) => id === "old" ? (signal = options.signal, old.promise)
    : Promise.resolve({ duration: 63, playableRange: [0, 4], state: "preparing" }));
  const pending = h.poller.start("old");
  await h.poller.start("new");
  assert.equal(signal.aborted, true);
  old.resolve({ duration: 63, playableRange: [0, 63], state: "complete" });
  await pending;
  assert.deepEqual(h.ranges, [[0, 0], [0, 0], [0, 4]]);
  assert.equal(h.timers.size, 1);
  h.poller.stop();
});

test("unmount invalidates a response even when the fetcher ignores abort", async () => {
  const response = deferred();
  const h = harness(() => response.promise);
  const pending = h.poller.start("a");
  h.poller.stop();
  response.resolve({ duration: 63, playableRange: [0, 63], state: "complete" });
  await pending;
  assert.deepEqual(h.ranges, [[0, 0]]);
  assert.equal(h.timers.size, 0);
});

test("a failed request retains range, retries, and does not clear on resume", async () => {
  let step = 0;
  const h = harness(async () => {
    if (++step === 2) throw new Error("temporary local API failure");
    return { duration: 63, playableRange: [0, 63], state: "complete" };
  });
  await h.poller.start("a");
  await h.tick();
  assert.deepEqual(h.ranges.at(-1), [0, 63]);
  assert.equal([...h.timers.values()][0].delay, 1500);
  await h.tick();
  assert.deepEqual(h.ranges.at(-1), [0, 63]);
  h.poller.stop();
});

test("cache invalidation from server can reduce a previously full range", async () => {
  let step = 0;
  const h = harness(async () => ({ duration: 63, playableRange: [0, ++step === 1 ? 63 : 8], state: "complete" }));
  await h.poller.start("a");
  await h.tick();
  assert.deepEqual(h.ranges.at(-1), [0, 8]);
  h.poller.stop();
});
