import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from desktop_danmaku import *
from desktop_danmaku_track import DanmakuTrack

ITEM={'text':'safe{\\pos(0,0)}[unknown]👍','offset_ms':1000,'lane':0}
class Player:
    def __init__(self): self.commands=[]; self.sid=0; self.fail=False
    def command(self,*args):
        if self.fail: raise RuntimeError('test failure')
        self.commands.append(args)
        if args[0]=='sub-add': self.sid+=1
    def get(self,key): return str(self.sid)
class DanmakuTests(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(validate_settings(DEFAULT_SETTINGS),DEFAULT_SETTINGS)
        for bad in ({**DEFAULT_SETTINGS,'duration':True},{**DEFAULT_SETTINGS,'opacity':0},{'duration':14}):
            with self.assertRaises(ValueError): validate_settings(bad)
        for bad in ([ITEM]*301,[{**ITEM,'lane':6}],[{**ITEM,'offset_ms':True}],[{**ITEM,'text':'a'*201}]):
            with self.assertRaises(ValueError): validate_danmaku(bad)
    def test_timing_and_ass_injection(self):
        text=ass_document([ITEM])
        self.assertIn('0:00:01.00,0:00:15.00',text)
        self.assertIn('｛＼pos(0,0)｝',text); self.assertNotIn(r'\pos(0,0)',text)
        self.assertIn('[unknown]',text); self.assertIn('👍',text)
        self.assertEqual(len(active_danmaku([ITEM],1,DEFAULT_SETTINGS)),1)
        self.assertEqual(active_danmaku([ITEM],15,DEFAULT_SETTINGS),[])
        self.assertEqual(active_danmaku([ITEM],float('nan'),DEFAULT_SETTINGS),[])
    def test_speed_opacity_and_lane_settings(self):
        for duration in (4,14,24):
            doc=ass_document([ITEM],{**DEFAULT_SETTINGS,'duration':duration,'opacity':50,'fontSize':36})
            self.assertIn(f',0,{duration*1000})',doc); self.assertIn('YaHei,36,&H80FFFFFF',doc)
        self.assertNotIn('Dialogue:',ass_document([{**ITEM,'lane':5}],{**DEFAULT_SETTINGS,'lanes':1}))
    def test_ordinary_poll_does_not_reload(self):
        p=Player(); track=DanmakuTrack(); track.update({'danmaku':[ITEM]}); track.apply(p)
        for _ in range(100): track.apply(p); track.update({'danmaku':[ITEM]})
        self.assertEqual(len(p.commands),1); self.assertEqual(track.loads,1)
    def test_replace_adds_before_removing_owned_track(self):
        p=Player(); track=DanmakuTrack(); track.update({'danmaku':[ITEM]}); track.apply(p)
        track.update({'danmaku':[ITEM,{**ITEM,'offset_ms':3000}]}); track.apply(p)
        self.assertEqual([c[0] for c in p.commands],['sub-add','sub-add','sub-remove'])
        self.assertEqual(p.commands[-1],('sub-remove','1'))
    def test_pause_seek_rate_use_absolute_media_timestamps(self):
        track=DanmakuTrack(); p=Player(); track.update({'danmaku':[ITEM]}); track.apply(p)
        for seconds in (2,2,8,3): self.assertTrue(track.snapshot(seconds)['danmakuVisible'])
        self.assertFalse(track.snapshot(16)['danmakuVisible']); self.assertEqual(track.loads,1)
    def test_reload_and_clear(self):
        track=DanmakuTrack(); p=Player(); track.update({'danmaku':[ITEM]}); track.apply(p)
        track.source_reloaded(); track.apply(p); self.assertEqual(track.loads,2)
        track.update({'danmaku':[]}); track.apply(p); self.assertFalse(track.snapshot(2)['danmakuVisible'])
        self.assertEqual(p.commands[-1],('sub-remove','2'))
    def test_failure_isolated_and_atomic_validation(self):
        track=DanmakuTrack(); p=Player(); p.fail=True
        track.update({'danmaku':[ITEM]}); track.apply(p); self.assertTrue(track.failed)
        with self.assertRaises(ValueError): track.update({'danmaku':[],'danmakuSettings':{}})
        self.assertEqual(track.items,[ITEM])
        p.fail=False; track.source_reloaded(); track.apply(p); self.assertFalse(track.failed)
if __name__=='__main__': unittest.main()
