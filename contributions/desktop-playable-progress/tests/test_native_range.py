import sys,unittest,threading,tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from desktop_playable_range import playable_range
class NativeRange(unittest.TestCase):
    def setUp(self):
        self.job=SimpleNamespace(duration=63,window_origin=0,failed=False,cancelled=threading.Event(),video_mode='native',source=object())
    def state(self,end=12,start=0,**extra):
        return dict(state='ready',outputReady=True,bufferStart=start,bufferEnd=end,**extra)
    def test_paused_actual_range_advances_without_changing_time(self):
        self.assertEqual(playable_range(self.job,native_state=self.state(12,paused=True,time=3)),[0,12])
        self.assertEqual(playable_range(self.job,native_state=self.state(63,paused=True,time=3)),[0,63])
    def test_seek_gap_and_full_local_range(self):
        self.assertEqual(playable_range(self.job,native_state=self.state(70,30)),[30,63])
        self.assertEqual(playable_range(self.job,native_state=self.state(63)),[0,63])
    def test_failed_cancelled_and_unready_native_never_use_hls_cache(self):
        for state in ({},dict(state='preparing',bufferEnd=63),dict(state='failed',outputReady=True,bufferStart=0,bufferEnd=63)):
            self.assertEqual(playable_range(self.job,lambda _:True,native_state=state),[0,0])
        self.job.cancelled.set();self.assertEqual(playable_range(self.job,native_state=self.state(63)),[0,0])
    def test_nonfinite_reversed_or_invalid_native_range(self):
        for start,end in [(0,float('nan')),(float('inf'),63),(-1,12),(20,10),(63,70),(False,63),(0,'63')]:
            self.assertEqual(playable_range(self.job,native_state=self.state(end,start)),[0,0])
if __name__=='__main__':unittest.main()
