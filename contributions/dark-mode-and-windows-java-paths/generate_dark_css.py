"""Build reviewable, scoped dark overrides without redistributing app bundles.

This is a migration aid for the existing hexadecimal palette, not a general CSS
color engine. Prefer explicit source-level color tokens when integrating it.
"""

import argparse
import colorsys
import re
from pathlib import Path

import tinycss2


PREFIX = 'html[data-local-theme="dark"]'
COLOR_PROPERTIES = {
    "color", "background", "background-color", "background-image", "border",
    "border-color", "border-top", "border-top-color", "border-bottom",
    "border-bottom-color", "border-left", "border-left-color", "border-right",
    "border-right-color", "outline", "outline-color", "box-shadow", "fill", "stroke",
}
QR_SELECTORS = ("qr-frame", "qr-login", "qr-uri")


def _dark_hex(value: str, role: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8}", value):
        return value
    expanded = "".join(char * 2 for char in value) if len(value) in (3, 4) else value
    rgb = tuple(int(expanded[index:index + 2], 16) / 255 for index in (0, 2, 4))
    hue, light, saturation = colorsys.rgb_to_hls(*rgb)
    if role.startswith("background"):
        if light < .72 or (saturation > .35 and light < .90):
            return value
        replacement = "3d2632" if saturation > .35 else "24272e"
        replacement = {"ffffff": "16171b", "f6f7f8": "1c1e23", "f1f2f3": "272a31"}.get(
            expanded[:6].lower(), replacement
        )
    elif role.startswith("border") or role.startswith("outline"):
        if light < .65 or saturation > .35:
            return value
        replacement = "454c59"
    elif role in ("color", "fill", "stroke"):
        if light > .83:
            return value
        if saturation > .30 and hue < .1 and light < .6:
            replacement = "ff9292"
        elif saturation > .25 and .2 < hue < .5 and light < .6:
            replacement = "89d9a4"
        elif saturation > .35:
            return value
        else:
            replacement = "e8e9ed" if light < .23 else "b8bdc7"
    else:
        return value
    return replacement + expanded[6:]


def _rewrite_colors(tokens, role):
    # Hash tokens in actual values are colors; URL and string tokens are opaque.
    for token in tokens:
        if token.type == "hash":
            token.value = _dark_hex(token.value, role)
            token.is_identifier = bool(re.match(r"[a-zA-Z_]", token.value))
        elif token.type == "function" and token.lower_name != "url":
            _rewrite_colors(token.arguments, role)


def _selectors(prelude):
    chunks, current = [], []
    for token in prelude:
        if token.type == "literal" and token.value == ",":
            chunks.append(tinycss2.serialize(current).strip())
            current = []
        else:
            current.append(token)
    chunks.append(tinycss2.serialize(current).strip())
    scoped = []
    for selector in chunks:
        if not selector or any(excluded in selector for excluded in QR_SELECTORS):
            continue
        root = re.match(r"^(?:html|:root)(?=[\s.#:\[>+~]|$)", selector)
        scoped.append(PREFIX + selector[root.end():] if root else PREFIX + " " + selector)
    return scoped


def _overrides(rules):
    output = []
    for rule in rules:
        if rule.type == "at-rule" and rule.content is not None and rule.lower_at_keyword in (
            "media", "supports", "layer"
        ):
            nested = _overrides(tinycss2.parse_rule_list(rule.content, skip_whitespace=True, skip_comments=True))
            if nested:
                output.append("@" + rule.at_keyword + tinycss2.serialize(rule.prelude) + "{" + nested + "}")
        elif rule.type == "qualified-rule":
            selectors = _selectors(rule.prelude)
            declarations = []
            for declaration in tinycss2.parse_declaration_list(rule.content, skip_whitespace=True, skip_comments=True):
                if declaration.type != "declaration" or declaration.lower_name not in COLOR_PROPERTIES:
                    continue
                _rewrite_colors(declaration.value, declaration.lower_name)
                value = tinycss2.serialize(declaration.value)
                declarations.append(declaration.lower_name + ":" + value + ("!important" if declaration.important else ""))
            # Replay unchanged color declarations too: later transparent/brand
            # declarations must still win over earlier recolored declarations.
            if selectors and declarations:
                output.append(",".join(selectors) + "{" + ";".join(declarations) + "}")
    return "".join(output)


def generate_dark_overrides(source_css: str) -> str:
    return _overrides(tinycss2.parse_stylesheet(source_css, skip_whitespace=True, skip_comments=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Private/local application CSS; never committed here")
    parser.add_argument("output", type=Path, help="Output CSS containing scoped overrides only")
    args = parser.parse_args()
    generated = generate_dark_overrides(args.source.read_text(encoding="utf-8"))
    supplemental = Path(__file__).with_name("dark-theme.css").read_text(encoding="utf-8")
    args.output.write_text(generated + "\n" + supplemental, encoding="utf-8")


if __name__ == "__main__":
    main()
