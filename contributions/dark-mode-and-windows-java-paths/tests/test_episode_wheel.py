"""Exercise the DOM controller with real enabled episode buttons in Edge."""

import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

CONTROLLER = Path(__file__).resolve().parents[1] / "episode-wheel.js"
FIXTURE = """<!doctype html><html><head><meta charset="utf-8"><style>
body {margin:0; min-height:1400px; font:16px/20px sans-serif}
.desktop-player-layout {display:flex; gap:20px}
.player-stage {position:relative; width:700px; height:360px}
video {width:100%; height:100%; background:#222}
.player-chrome {position:absolute; bottom:0; width:100%; height:80px; background:#eee}
aside {width:250px; height:360px; overflow-y:auto}
aside div {height:1400px}
</style></head><body><div class="desktop-player-layout"><div class="player-stage">
<video class="validation-video"></video><div class="player-chrome" aria-label="播放控制">
<div class="player-timeline"><input type="range" aria-label="播放进度"></div>
<div class="player-toolbar"><button aria-label="上一集">上一集</button>
<button aria-label="下一集">下一集</button><select aria-label="播放速度"><option>1</option></select>
<span contenteditable="true">可编辑输入</span></div></div></div>
<aside aria-label="选集"><div>选集列表</div></aside></div><p id="current-episode"></p>
<script>
window.episode = 3; window.busy = false;
window.renderPlayer = () => {
  document.querySelector('#current-episode').textContent = String(window.episode);
  document.querySelector('button[aria-label="上一集"]').disabled = window.busy || window.episode === 1;
  document.querySelector('button[aria-label="下一集"]').disabled = window.busy || window.episode === 5;
};
window.bindPlayer = () => {
  document.querySelector('button[aria-label="上一集"]').onclick = () => {window.episode--; window.renderPlayer();};
  document.querySelector('button[aria-label="下一集"]').onclick = () => {window.episode++; window.renderPlayer();};
  window.renderPlayer();
};
window.bindPlayer();
</script></body></html>"""


class EpisodeWheelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel="msedge", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1100, "height": 800})
        self.page.set_content(FIXTURE)
        self.page.add_script_tag(path=str(CONTROLLER))

    def tearDown(self):
        self.page.close()

    def episode(self):
        return self.page.locator("#current-episode").text_content()

    def wheel(self, selector="video", **options):
        return self.page.locator(selector).evaluate("""(element, options) => {
            const event = new WheelEvent('wheel', {bubbles:true, cancelable:true, deltaY:120, ...options});
            element.dispatchEvent(event);
            return event.defaultPrevented;
        }""", options)

    def next_gesture(self):
        self.page.wait_for_timeout(300)

    def test_real_mouse_wheel_down_and_up_use_existing_buttons(self):
        self.page.locator("video").hover(position={"x": 200, "y": 120})
        self.page.mouse.wheel(0, 120)
        self.page.wait_for_function('window.episode === 4', timeout=1500)
        self.next_gesture()
        self.page.mouse.wheel(0, -120)
        self.page.wait_for_function('window.episode === 3', timeout=1500)

    def test_small_trackpad_deltas_accumulate_without_skipping(self):
        for _ in range(3):
            self.assertTrue(self.wheel(deltaY=15))
        self.assertEqual(self.episode(), "3")
        self.wheel(deltaY=3)
        self.assertEqual(self.episode(), "4")
        for _ in range(10):
            self.wheel(deltaY=80)
        self.assertEqual(self.episode(), "4")
        self.next_gesture()
        self.wheel(deltaY=120)
        self.assertEqual(self.episode(), "5")

    def test_loading_does_not_queue_an_episode_change(self):
        self.page.evaluate("window.busy = true; window.renderPlayer()")
        self.assertTrue(self.wheel())
        self.assertEqual(self.episode(), "3")
        self.page.evaluate("window.busy = false; window.renderPlayer()")
        self.wheel()
        self.assertEqual(self.episode(), "3")
        self.next_gesture()
        self.wheel()
        self.assertEqual(self.episode(), "4")

    def test_first_and_last_disabled_buttons_do_not_cross_endpoints(self):
        self.page.evaluate("window.episode = 1; window.renderPlayer()")
        self.wheel(deltaY=-120)
        self.assertEqual(self.episode(), "1")
        self.next_gesture()
        self.wheel(deltaY=120)
        self.assertEqual(self.episode(), "2")
        self.page.evaluate("window.episode = 5; window.renderPlayer()")
        self.next_gesture()
        self.wheel(deltaY=120)
        self.assertEqual(self.episode(), "5")

    def test_controls_and_sidebar_keep_their_native_wheel(self):
        for selector in (".player-chrome", ".player-toolbar", ".player-timeline", "input", "select",
                         'button[aria-label="下一集"]', '[contenteditable="true"]', "aside"):
            self.assertFalse(self.wheel(selector))
        self.assertEqual(self.episode(), "3")
        self.page.locator("aside").hover(position={"x": 100, "y": 100})
        self.page.mouse.wheel(0, 200)
        self.page.wait_for_function("document.querySelector('aside').scrollTop > 0", timeout=1500)
        self.assertEqual(self.episode(), "3")

    def test_modifiers_horizontal_and_uncancelable_events_are_ignored(self):
        for modifier in ("ctrlKey", "altKey", "metaKey", "shiftKey"):
            self.assertFalse(self.wheel(**{modifier: True}))
        self.assertFalse(self.wheel(deltaX=120, deltaY=10))
        self.assertFalse(self.wheel(deltaX=120, deltaY=0))
        self.assertFalse(self.wheel(cancelable=False))
        self.assertEqual(self.episode(), "3")
        self.wheel()
        self.assertEqual(self.episode(), "4")

    def test_line_and_page_modes_are_normalized(self):
        self.wheel(deltaY=1, deltaMode=1)
        self.wheel(deltaY=1, deltaMode=1)
        self.assertEqual(self.episode(), "3")
        self.wheel(deltaY=1, deltaMode=1)
        self.assertEqual(self.episode(), "4")
        self.next_gesture()
        self.wheel(deltaY=-1, deltaMode=2)
        self.assertEqual(self.episode(), "3")

    def test_player_remount_and_duplicate_script_keep_one_handler(self):
        self.page.add_script_tag(path=str(CONTROLLER))
        self.page.evaluate("""() => {
            const stage = document.querySelector('.player-stage');
            stage.replaceWith(stage.cloneNode(true)); window.bindPlayer();
        }""")
        self.wheel()
        self.assertEqual(self.episode(), "4")
        self.page.evaluate("""() => {
            const stage = document.querySelector('.player-stage');
            stage.replaceWith(stage.cloneNode(true)); window.bindPlayer();
        }""")
        self.wheel()
        self.assertEqual(self.episode(), "4", "Momentum after an episode remount must not skip again")

    def test_native_video_controls_remain_usable(self):
        self.page.locator("video").evaluate("video => video.controls = true")
        self.assertFalse(self.wheel())
        self.assertEqual(self.episode(), "3")


if __name__ == "__main__":
    unittest.main()
