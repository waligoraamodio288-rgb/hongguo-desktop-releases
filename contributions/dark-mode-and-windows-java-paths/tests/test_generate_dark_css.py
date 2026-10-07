"""Regression tests use synthetic CSS; no shipped application bundle is needed."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_dark_css import generate_dark_overrides


class DarkCssTests(unittest.TestCase):
    def test_scopes_html_and_root_without_an_impossible_html_descendant(self):
        self.assertEqual(
            generate_dark_overrides("html, :root, body {background:#fff;color:#222}"),
            'html[data-local-theme="dark"],html[data-local-theme="dark"],'
            'html[data-local-theme="dark"] body{background:#16171b;color:#e8e9ed}',
        )

    def test_preserves_alpha_and_important_for_neutral_colors(self):
        self.assertEqual(
            generate_dark_overrides(".card{background:#fff8;border:1px solid #ccc;color:#666!important}"),
            'html[data-local-theme="dark"] .card{background:#16171b88;'
            'border:1px solid #454c59;color:#b8bdc7!important}',
        )

    def test_does_not_recolor_url_fragments_or_quoted_text(self):
        self.assertEqual(
            generate_dark_overrides('.card{background:linear-gradient(#fff,#f6f7f8),url("#fff");'
                                    'fill:url(#fff);content:"#fff"}'),
            'html[data-local-theme="dark"] .card{background:linear-gradient(#16171b,#1c1e23),url("#fff");fill:url(#fff)}',
        )

    def test_preserves_brand_background_and_white_foreground(self):
        self.assertEqual(
            generate_dark_overrides(".primary{background:#fb7299;color:#fff}"),
            'html[data-local-theme="dark"] .primary{background:#fb7299;color:#fff}',
        )

    def test_replays_later_unchanged_declarations_to_preserve_the_cascade(self):
        self.assertEqual(
            generate_dark_overrides(".card{background:#fff}.card.active{background:transparent}"),
            'html[data-local-theme="dark"] .card{background:#16171b}'
            'html[data-local-theme="dark"] .card.active{background:transparent}',
        )

    def test_recurses_into_conditions_without_rewriting_keyframes(self):
        self.assertEqual(
            generate_dark_overrides("@media (min-width:600px){@supports(display:grid){"
                                    ".card{background:#fff}}}@keyframes blink{to{background:#fff}}"),
            '@media (min-width:600px){@supports(display:grid){'
            'html[data-local-theme="dark"] .card{background:#16171b}}}',
        )

    def test_excludes_qr_selectors_without_discarding_an_unrelated_selector(self):
        self.assertEqual(
            generate_dark_overrides(".qr-frame, .card{background:#fff}"),
            'html[data-local-theme="dark"] .card{background:#16171b}',
        )

    def test_keeps_function_selector_commas_inside_their_selector(self):
        self.assertEqual(
            generate_dark_overrides(":is(.card,.panel), .dialog{color:#222}"),
            'html[data-local-theme="dark"] :is(.card,.panel),'
            'html[data-local-theme="dark"] .dialog{color:#e8e9ed}',
        )

    def test_ignores_custom_properties_and_layout(self):
        self.assertEqual(generate_dark_overrides(":root{--paper:#fff;padding:20px;width:100%}"), "")


if __name__ == "__main__":
    unittest.main()
