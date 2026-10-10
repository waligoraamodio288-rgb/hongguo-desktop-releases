from pathlib import Path
from types import SimpleNamespace
from threading import Event
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from desktop_playable_range import playable_range

class RangeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)
        self.job = SimpleNamespace(directory=self.path, duration=63., window_origin=0.,
            start_seconds=0., source=None, failed=False, cancelled=Event(), done=Event())

    def output(self, second=False):
        (self.path / "init.mp4").write_bytes(b"init")
        (self.path / "seg000000.m4s").write_bytes(b"one")
        text = '#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:2,\nseg000000.m4s\n'
        if second:
            text += '#EXTINF:3,\nseg000001.m4s\n'
        text += '#EXT-X-ENDLIST\n'
        (self.path / "index.m3u8").write_text(text, encoding="utf-8")
        (self.path / "complete.marker").write_text("desktop-hls-v1\n", encoding="ascii")

    def test_raw_download_is_not_playable(self):
        self.job.source = self.path / "source.mp4"
        self.job.source.write_bytes(b"raw")
        self.assertEqual(playable_range(self.job), [0, 0])

    def test_disk_growth_without_play_events_and_missing_fragment(self):
        self.output(second=True)
        self.assertEqual(playable_range(self.job), [0, 2])
        (self.path / "seg000001.m4s").write_bytes(b"two")
        self.assertEqual(playable_range(self.job), [0, 5])

    def test_committed_complete_covers_duration_but_missing_fragment_does_not(self):
        self.output()
        self.job.done.set()
        self.assertEqual(playable_range(self.job), [0, 63])
        (self.path / "seg000000.m4s").unlink()
        self.assertEqual(playable_range(self.job), [0, 0])

    def test_seek_window_keeps_missing_prefix(self):
        self.output()
        self.job.start_seconds, self.job.window_origin = 30., 30.02
        start, end = playable_range(self.job)
        self.assertAlmostEqual(start, 30.02)
        self.assertAlmostEqual(end, 32.02)
        self.job.done.set()
        self.assertEqual(playable_range(self.job), [30.02, 63])

    def test_verified_cache_callback_and_eviction(self):
        self.job.start_seconds, self.job.window_origin, self.job.source = 30., 30.02, self.path / "source.mp4"
        self.assertEqual(playable_range(self.job, lambda _: True), [0, 63])
        self.assertEqual(playable_range(self.job, lambda _: False), [0, 0])
        def failed(_):
            raise OSError("cache unavailable")
        self.assertEqual(playable_range(self.job, failed), [0, 0])

    def test_failure_cancel_and_invalid_duration(self):
        self.output()
        self.job.failed = True
        self.assertEqual(playable_range(self.job), [0, 0])
        self.job.failed = False
        self.job.cancelled.set()
        self.assertEqual(playable_range(self.job), [0, 0])
        self.job.cancelled.clear()
        self.job.duration = float("nan")
        self.assertEqual(playable_range(self.job), [0, 0])

    def test_bad_playlist_never_claims_full(self):
        self.output()
        self.job.done.set()
        for text in ["#EXTINF:nan,\nseg000000.m4s", "#EXTINF:-1,\nseg000000.m4s",
                     "#EXTINF:2,\n../secret", "#EXTINF:2,\n#EXTINF:3,\nseg000000.m4s"]:
            (self.path / "index.m3u8").write_text(text, encoding="utf-8")
            self.assertEqual(playable_range(self.job), [0, 0])

if __name__ == "__main__":
    unittest.main(verbosity=2)
