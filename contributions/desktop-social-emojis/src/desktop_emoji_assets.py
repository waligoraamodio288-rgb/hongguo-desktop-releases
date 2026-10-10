"""Validated injectable PNG catalog and ASS vector shapes; no network or APK access."""
import base64
import json
import math
import re
from pathlib import Path

def load_assets(path):
    data=Path(path).read_bytes()
    if len(data)>16*1024*1024: raise ValueError('Emoji catalog too large')
    return validate_assets(json.loads(data.decode('utf-8')))

def validate_assets(assets):
    if not isinstance(assets,dict) or len(assets)>256: raise ValueError('Invalid emoji assets')
    output={}; points_total=0
    for name,row in assets.items():
        if not isinstance(name,str) or not re.fullmatch(r'\[[^\[\]\r\n]{1,16}\]',name): raise ValueError('Invalid emoji name')
        if not isinstance(row,dict) or set(row)!={'src','resolution','drawing'}: raise ValueError('Invalid emoji shape')
        src=row['src']; resolution=row['resolution']
        if not isinstance(src,str) or not src.startswith('data:image/png;base64,') or len(src)>1024*1024: raise ValueError('Invalid emoji PNG')
        try: png=base64.b64decode(src.split(',',1)[1],validate=True)
        except (ValueError,TypeError): raise ValueError('Invalid emoji base64') from None
        if not png.startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError('Invalid emoji PNG header')
        if type(resolution) is not int or not 1<=resolution<=256: raise ValueError('Invalid emoji resolution')
        if not isinstance(row['drawing'],list) or len(row['drawing'])>128: raise ValueError('Invalid emoji drawing')
        for group in row['drawing']:
            if not isinstance(group,dict) or set(group)!={'color','alpha','paths'}: raise ValueError('Invalid emoji group')
            if not isinstance(group['color'],list) or len(group['color'])!=3 or any(type(c) is not int or not 0<=c<=255 for c in group['color']): raise ValueError('Invalid emoji color')
            if type(group['alpha']) not in (int,float) or not math.isfinite(group['alpha']) or not 0<=group['alpha']<=1: raise ValueError('Invalid emoji alpha')
            if not isinstance(group['paths'],list) or not group['paths']: raise ValueError('Empty emoji paths')
            for path in group['paths']:
                if not isinstance(path,list) or len(path)<3: raise ValueError('Invalid emoji path')
                points_total+=len(path)
                if points_total>2000000: raise ValueError('Emoji paths too large')
                for point in path:
                    if not isinstance(point,list) or len(point)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=resolution for n in point): raise ValueError('Invalid emoji coordinate')
        output[name]=row
    return output

def catalog(assets):
    return {name:row['src'] for name,row in assets.items()}
