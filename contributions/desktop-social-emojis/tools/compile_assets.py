"""Compile host-owned local images, without extracting or downloading provider assets."""
import argparse
import base64
import io
import json
from pathlib import Path

def compile_assets(mapping):
    from PIL import Image
    result={}
    for name, source_path in mapping.items():
        with Image.open(source_path) as source:
            image=source.convert('RGBA'); png=io.BytesIO(); image.save(png,format='PNG',optimize=True)
            small=image.resize((48,48),Image.Resampling.LANCZOS)
            palette=small.convert('RGB').quantize(colors=16)
            pixels=palette.convert('RGB'); alpha=small.getchannel('A'); groups={}
            for y in range(48):
                x=0
                while x<48:
                    opacity=round(alpha.getpixel((x,y))/255*7)
                    if not opacity:x+=1;continue
                    color=pixels.getpixel((x,y)); end=x+1
                    while end<48 and pixels.getpixel((end,y))==color and round(alpha.getpixel((end,y))/255*7)==opacity:end+=1
                    groups.setdefault((*color,opacity),[]).append([x,y,end-x]); x=end
            drawings=[]
            for key,runs in groups.items():
                mask={(x,y) for rx,y,width in runs for x in range(rx,rx+width)}
                edges={}
                def add(a,b):edges.setdefault(a,[]).append(b)
                for x,y in sorted(mask):
                    if (x,y-1) not in mask:add((x,y),(x+1,y))
                    if (x+1,y) not in mask:add((x+1,y),(x+1,y+1))
                    if (x,y+1) not in mask:add((x+1,y+1),(x,y+1))
                    if (x-1,y) not in mask:add((x,y+1),(x,y))
                paths=[]
                while edges:
                    start=next(iter(edges)); point=start; path=[start]
                    while True:
                        options=edges[point]; following=options.pop()
                        if not options:del edges[point]
                        point=following
                        if point==start:break
                        path.append(point)
                    simple=[]
                    for index,point in enumerate(path):
                        a=path[index-1]; b=path[(index+1)%len(path)]
                        if (point[0]-a[0])*(b[1]-point[1])!=(point[1]-a[1])*(b[0]-point[0]):simple.append(list(point))
                    if len(simple)>=3:paths.append(simple)
                drawings.append({'color':list(key[:3]),'alpha':key[3]/7,'paths':paths})
            result[name]={'src':'data:image/png;base64,'+base64.b64encode(png.getvalue()).decode(),
                'resolution':48,'drawing':drawings}
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mapping',type=Path,help='JSON object: [tag] -> local image path, relative to this JSON')
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    mapping=json.loads(args.mapping.read_text(encoding='utf8'))
    mapping={name:args.mapping.parent/path for name,path in mapping.items()}
    args.output.write_text(json.dumps(compile_assets(mapping),ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
