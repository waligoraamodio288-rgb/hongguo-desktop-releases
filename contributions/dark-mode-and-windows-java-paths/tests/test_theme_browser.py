"""Real DOM tests for the contributed controller, using a synthetic page."""

import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from generate_dark_css import generate_dark_overrides

FIXTURE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="theme-color" content="#ffffff"></head><body>
<aside class="sidebar"><nav class="main-nav"><button class="active">设置</button></nav></aside>
<section class="settings-page"><h1>设置</h1><div class="settings-row"><button>检查更新</button></div></section>
<img alt="封面"><video></video></body></html>"""
LIGHT_CSS = """body{background:#fff;color:#222}.sidebar{background:#f6f7f8}
.settings-row button{background:#fff;color:#222;border:1px solid #ccc}
.main-nav button{background:#fff;color:#222;transition:color .18s}
.main-nav button.active{background:transparent;color:#fb7299}"""


class ThemeBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel="msedge", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.route("https://theme-test.invalid/**", lambda route: route.fulfill(body=FIXTURE, content_type="text/html"))
        self.page.goto("https://theme-test.invalid/")
        self.page.add_style_tag(content=LIGHT_CSS + generate_dark_overrides(LIGHT_CSS)
                                + BASE.joinpath("dark-theme.css").read_text(encoding="utf-8"))

    def tearDown(self):
        self.page.close()

    def load_controller(self):
        self.page.add_script_tag(path=str(BASE / "theme-toggle.js"))

    def test_defaults_to_dark_and_keeps_media_unfiltered(self):
        self.load_controller()
        self.assertEqual(self.page.locator("html").get_attribute("data-local-theme"), "dark")
        self.assertEqual(self.page.locator("body").evaluate("e=>getComputedStyle(e).backgroundColor"), "rgb(22, 23, 27)")
        for selector in ("img", "video"):
            self.assertEqual(self.page.locator(selector).evaluate("e=>getComputedStyle(e).filter"), "none")
        self.page.wait_for_function('getComputedStyle(document.querySelector(".main-nav button.active")).color === "rgb(251, 114, 153)"')

    def test_light_choice_is_persisted_and_restored(self):
        self.load_controller()
        self.page.locator("#local-theme-select").select_option("light")
        self.assertEqual(self.page.evaluate('localStorage.getItem("hongguo-local-theme")'), "light")
        self.assertEqual(self.page.locator("body").evaluate("e=>getComputedStyle(e).backgroundColor"), "rgb(255, 255, 255)")
        self.page.reload()
        self.load_controller()
        self.assertEqual(self.page.locator("html").get_attribute("data-local-theme"), "light")
        self.assertEqual(self.page.locator("#local-theme-select").input_value(), "light")

    def test_system_choice_tracks_operating_system_changes(self):
        self.load_controller()
        self.page.locator("#local-theme-select").select_option("system")
        for scheme in ("dark", "light"):
            self.page.emulate_media(color_scheme=scheme)
            self.page.wait_for_function("expected=>document.documentElement.dataset.localTheme === expected", arg=scheme)
        self.assertEqual(self.page.locator('meta[name="theme-color"]').get_attribute("content"), "#ffffff")

    def test_invalid_saved_choice_falls_back_to_dark(self):
        self.page.evaluate('localStorage.setItem("hongguo-local-theme", "invalid")')
        self.load_controller()
        self.assertEqual(self.page.locator("html").get_attribute("data-local-theme"), "dark")

    def test_settings_remount_keeps_one_row_and_current_choice(self):
        self.load_controller()
        self.page.locator("#local-theme-select").select_option("light")
        self.page.evaluate("""() => {
            const old = document.querySelector('.settings-page');
            const fresh = old.cloneNode(true);
            fresh.querySelector('#local-theme-row').remove();
            old.replaceWith(fresh);
        }""")
        self.page.locator("#local-theme-select").wait_for()
        self.assertEqual(self.page.locator("#local-theme-row").count(), 1)
        self.assertEqual(self.page.locator("#local-theme-select").input_value(), "light")

    def test_storage_failure_still_allows_theme_selection(self):
        self.page.evaluate("""() => Object.defineProperty(window, 'localStorage', {
            value: {getItem() { throw new Error('disabled'); }, setItem() { throw new Error('disabled'); }}
        })""")
        self.load_controller()
        self.page.locator("#local-theme-select").select_option("light")
        self.assertEqual(self.page.locator("html").get_attribute("data-local-theme"), "light")


if __name__ == "__main__":
    unittest.main()
