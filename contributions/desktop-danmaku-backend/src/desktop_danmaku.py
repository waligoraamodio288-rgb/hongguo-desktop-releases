"""Bounded, plain-text danmaku rendered in libmpv's video surface."""
import math
import re

DEFAULT_SETTINGS = {"opacity": 80, "lanes": 3, "fontSize": 28, "duration": 14}


def emoji_parts(text):
    return [part for part in re.split(r'(\[[^\[\]\r\n]{1,16}\])',text) if part]


def validate_settings(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_SETTINGS):
        raise ValueError("Invalid danmaku settings")
    for key, low, high in (("opacity", 10, 100), ("lanes", 1, 6),
                           ("fontSize", 18, 36), ("duration", 4, 24)):
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError("Invalid danmaku setting")
    return dict(value)


def validate_danmaku(items):
    if not isinstance(items, list) or len(items) > 300:
        raise ValueError("Invalid danmaku list")
    result = []
    for row in items:
        if not isinstance(row, dict) or set(row) != {"text", "offset_ms", "lane"}:
            raise ValueError("Invalid danmaku item")
        text, offset, lane = row["text"], row["offset_ms"], row["lane"]
        if (not isinstance(text, str) or len(text) > 200 or "\x00" in text
                or type(offset) is not int or not 0 <= offset <= 86400000
                or type(lane) is not int or not 0 <= lane < 6):
            raise ValueError("Invalid danmaku value")
        result.append(dict(row))
    return result


def active_danmaku(items, seconds, settings):
    if not math.isfinite(seconds):
        return []
    return [row for row in items if row['lane'] < settings['lanes']
            and 0 <= seconds - row['offset_ms'] / 1000 < settings['duration']]


def ass_document(items, settings=None, *, assets=None):
    """One timed track lets libass move glyphs on the video's presentation clock."""
    settings = validate_settings(DEFAULT_SETTINGS if settings is None else settings)
    items = validate_danmaku(items)
    assets = {} if assets is None else assets
    duration, size = settings["duration"], settings["fontSize"]
    alpha = f'{round(255 * (1 - settings["opacity"] / 100)):02X}'
    lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1000", "PlayResY: 562",
             "WrapStyle: 2", "ScaledBorderAndShadow: yes", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
             "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             f"Style: Default,Microsoft YaHei,{size},&H{alpha}FFFFFF,&H{alpha}FFFFFF,&H{alpha}000000,"
             "&HFF000000,0,0,0,0,100,100,0,0,1,1.5,0,7,0,0,0,1", "[Events]",
             "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    def stamp(milliseconds):
        centiseconds = round(milliseconds / 10)
        hours, rest = divmod(centiseconds, 360000)
        minutes, rest = divmod(rest, 6000)
        seconds, fraction = divmod(rest, 100)
        return f'{hours}:{minutes:02}:{seconds:02}.{fraction:02}'
    for row in items:
        if row["lane"] >= settings["lanes"]:
            continue
        # ASS syntax cannot be supplied by comment text. Fullwidth equivalents
        # preserve readability, including literal backslashes and braces.
        text = row["text"].replace("\\", "＼").replace("{", "｛").replace("}", "｝")
        text = " ".join(text.split())
        parts=emoji_parts(text)
        width = min(6000, max(60,sum(size+4 if part in assets else len(part)*size for part in parts)))
        y = 25 + row["lane"] * (size + 15)
        start = row['offset_ms']
        prefix=f'Dialogue: 0,{stamp(start)},{stamp(start + duration * 1000)},Default,,0,0,0,,'
        def movement(x,top):
            return r'{\an7\move(' + f'{1000+x:g},{top:g},{-width+x:g},{top:g},0,{duration*1000}' + r')\clip(0,0,1000,562)'
        x=0
        for part in parts:
            if part not in assets:
                lines.append(prefix+movement(x,y)+'}'+part)
                x+=len(part)*size
                continue
            scale=size/assets[part]['resolution']
            for group in assets[part]['drawing']:
                red,green,blue=group['color']
                opacity=round(255*(1-settings['opacity']/100*group['alpha']))
                points=[point for path in group['paths'] for point in path]
                min_x=min(point[0] for point in points); min_y=min(point[1] for point in points)
                shapes=[]
                for path in group['paths']:
                    pairs=[f'{(px-min_x)*scale:g} {(py-min_y)*scale:g}' for px,py in path]
                    shapes.append('m '+pairs[0]+' l '+' '.join(pairs[1:]))
                lines.append(prefix+movement(x+min_x*scale,y+min_y*scale)
                    +rf'\bord0\shad0\1c&H{blue:02X}{green:02X}{red:02X}&\1a&H{opacity:02X}&\p1'+'}'+' '.join(shapes))
            x+=size+4
    return '\n'.join(lines) + '\n'
