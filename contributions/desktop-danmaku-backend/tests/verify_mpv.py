"""Optional real libmpv property check with synthetic local audio, no visible window."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import wave

parser=argparse.ArgumentParser()
parser.add_argument('--native-package',type=Path,required=True)
parser.add_argument('--dll',type=Path,required=True)
args=parser.parse_args()
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(args.native_package/'src')]
from desktop_native import NativeHost,Mpv
from desktop_danmaku import ass_document
from desktop_danmaku_track import DanmakuTrack
host=NativeHost(parent_pid=os.getpid(),dll_path=args.dll)
if not host.available:raise RuntimeError('Verified native package DLL unavailable')
player=Mpv(host.dll)
try:
    for name,value in {'vo':'null','ao':'null','terminal':'no','pause':'yes'}.items():player.option(name,value)
    player.check(player.dll.mpv_initialize(player.handle))
    with tempfile.TemporaryDirectory() as folder:
        path=os.path.join(folder,'fixture.wav')
        with wave.open(path,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*8000*5)
        player.command('loadfile',path)
        deadline=time.monotonic()+5
        while not player.get('duration') and time.monotonic()<deadline:time.sleep(.05)
        assert player.get('duration')
        caption=ass_document([{'text':'fixture caption','offset_ms':0,'lane':0}])
        player.command('sub-add','memory://'+caption,'select','original caption')
        original=player.get('sid');assert original and original.isdigit()
        override=player.get('secondary-sub-ass-override')
        track=DanmakuTrack();track.update({'danmaku':[{'text':'overlay','offset_ms':0,'lane':1}]});track.apply(player)
        assert not track.failed and player.get('secondary-sid')==original and player.get('sid')==track.track_id
        track.update({'danmaku':[]});track.apply(player)
        assert not track.failed and player.get('sid')==original and player.get('secondary-sid')=='no'
        assert player.get('secondary-sub-ass-override')==override
        print(json.dumps({'pass':True,'scope':'actual libmpv synthetic audio, subtitle selection/restoration; no pixel or Win32 claim'}))
finally:player.close()
