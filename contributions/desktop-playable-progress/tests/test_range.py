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
        text = '#EXTM3U\n#EXT-X-VERSION:7\n#EXT-X-TARGETDURATION:3\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:2,\nseg000000.m4s\n'
        if second:
            text += '#EXTINF:3,\nseg000001.m4s\n'
        text += '#EXT-X-ENDLIST\n'
        (self.path / "index.m3u8").write_text(text, encoding="utf-8")
        (self.path / "complete.marker").write_text("desktop-hls-v1\n", encoding="ascii")

    def test_single_endlist_is_valid_before_or_between_media_tags(self):
        self.output();self.job.done.set();playlist=self.path/'index.m3u8'
        body=playlist.read_text(encoding='utf-8').replace('#EXT-X-ENDLIST\n','')
        for anchor in ('#EXT-X-MAP:', '#EXTINF:', 'seg000000.m4s'):
            with self.subTest(anchor=anchor):
                playlist.write_text(body.replace(anchor,'#EXT-X-ENDLIST\n'+anchor,1),encoding='utf-8')
                self.assertEqual(playable_range(self.job),[0,63])

    def test_raw_download_is_not_playable(self):
        self.job.source = self.path / "source.mp4"
        self.job.source.write_bytes(b"raw")
        self.assertEqual(playable_range(self.job), [0, 0])

    def test_encryption_tags_do_not_claim_playable_fragments(self):
        self.output();self.job.done.set();playlist=self.path/'index.m3u8'
        original=playlist.read_text(encoding='utf-8')
        for tag in ('#EXT-X-KEY:METHOD=AES-128,URI="missing.key"',
                    '#EXT-X-GAP',
                    '#EXT-X-SESSION-KEY:METHOD=SAMPLE-AES,URI="key"',
                    '#EXT-X-KEY:METHOD=NONE'):
            playlist.write_text(original.replace('#EXTINF:',tag+'\n#EXTINF:',1),encoding='utf-8')
            self.assertEqual(playable_range(self.job),[0,0])

    def test_disk_growth_without_play_events_and_missing_fragment(self):
        self.output(second=True)
        self.assertEqual(playable_range(self.job), [0, 2])
        (self.path / "seg000001.m4s").write_bytes(b"two")
        self.assertEqual(playable_range(self.job), [0, 5])

    def test_missing_fragment_stops_coverage_but_not_playlist_validation(self):
        self.output(second=True)
        playlist=self.path/'index.m3u8'
        body=playlist.read_text(encoding='utf8').replace('#EXT-X-ENDLIST\n','')
        playlist.write_text(body+'#EXTINF:2,\nseg000002.m4s\n#EXT-X-ENDLIST\n',encoding='utf8')
        (self.path/'seg000002.m4s').write_bytes(b'three')
        self.assertEqual(playable_range(self.job),[0,2])
        for tail in ('#EXT-X-ENDLIST\n', '#EXT-X-MAP:URI="bad.mp4"\n', '#EXTINF:2,\n../bad\n'):
            playlist.write_text(body.replace('#EXTM3U\n','#EXTM3U\n#EXT-X-ENDLIST\n',1)+tail,encoding='utf8')
            self.assertEqual(playable_range(self.job),[0,0])

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

    def test_zero_offset_session_uses_verified_complete_cache_before_restore(self):
        self.job.source = self.path / "source.mp4"
        self.assertEqual(self.job.start_seconds, 0)
        self.assertFalse((self.path / "index.m3u8").exists())
        calls = []
        def cached(source):
            calls.append(source)
            return True
        self.assertEqual(playable_range(self.job, cached), [0, 63])
        self.assertEqual(calls, [self.job.source])

    def test_initialization_map_must_apply_to_all_counted_fragments(self):
        self.output()
        self.job.done.set()
        valid = (self.path / "index.m3u8").read_text(encoding="utf-8")
        correct = '#EXT-X-MAP:URI="init.mp4"\n'
        variants = {
            "missing": valid.replace(correct, ""),
            "different": valid.replace(correct, '#EXT-X-MAP:URI="other.mp4"\n'),
            "late": valid.replace(correct, "").replace("#EXT-X-ENDLIST", correct + "#EXT-X-ENDLIST"),
            "changed": valid.replace("#EXT-X-ENDLIST", '#EXT-X-MAP:URI="missing.mp4"\n#EXTINF:2,\nseg000001.m4s\n#EXT-X-ENDLIST'),
        }
        (self.path / "seg000001.m4s").write_bytes(b"two")
        for label, text in variants.items():
            with self.subTest(map=label):
                (self.path / "index.m3u8").write_text(text, encoding="utf-8")
                self.assertEqual(playable_range(self.job), [0, 0])

    def test_cache_validation_rechecks_asynchronous_cancel_or_failure(self):
        self.job.source = self.path / "source.mp4"
        self.job.start_seconds, self.job.window_origin = 30., 30.02
        for flag in ("cancelled", "failed"):
            with self.subTest(flag=flag):
                self.job.cancelled.clear()
                self.job.failed = False
                def cached(_):
                    if flag == "cancelled":
                        self.job.cancelled.set()
                    else:
                        self.job.failed = True
                    return True
                self.assertEqual(playable_range(self.job, cached), [0, 0])

    def test_playlist_must_start_with_required_hls_header(self):
        self.output()
        self.job.done.set()
        valid = (self.path / "index.m3u8").read_text(encoding="utf-8")
        for text in (valid.removeprefix("#EXTM3U\n"), "\n" + valid,
                     valid.replace("#EXTM3U", "#EXTM3U8", 1)):
            with self.subTest(playlist=text):
                (self.path / "index.m3u8").write_text(text, encoding="utf-8")
                self.assertEqual(playable_range(self.job), [0, 0])

    def test_target_duration_is_required_valid_unique_and_bounds_segments(self):
        self.output()
        valid = (self.path / "index.m3u8").read_text(encoding="utf-8")
        target = "#EXT-X-TARGETDURATION:3\n"
        variants = [valid.replace(target, ""), valid.replace(target, target + target),
                    valid.replace("#EXTINF:2,", "#EXTINF:4,"),
                    valid.replace("#EXTINF:2,", "#EXTINF:2e0,"),
                    valid.replace("#EXTINF:2,", "#EXTINF:2")]
        variants += [valid.replace(target, f"#EXT-X-TARGETDURATION:{value}\n")
                     for value in ("0", "-1", "3.0", "bad")]
        for text in variants:
            with self.subTest(playlist=text):
                (self.path / "index.m3u8").write_text(text, encoding="utf-8")
                self.assertEqual(playable_range(self.job), [0, 0])

    def test_fmp4_map_requires_valid_unique_compatibility_version(self):
        self.output()
        valid = (self.path / "index.m3u8").read_text(encoding="utf-8")
        version = "#EXT-X-VERSION:7\n"
        for text in (valid.replace(version, ""), valid.replace(version, version + version),
                     valid.replace(version, "#EXT-X-VERSION:5\n")):
            with self.subTest(playlist=text):
                (self.path / "index.m3u8").write_text(text, encoding="utf-8")
                self.assertEqual(playable_range(self.job), [0, 0])

    def test_invalid_window_origins_do_not_produce_invalid_json_ranges(self):
        self.output()
        self.job.done.set()
        for origin in (float("nan"), float("inf"), float("-inf"), -1, 63, 64):
            with self.subTest(origin=origin):
                self.job.window_origin = origin
                self.assertEqual(playable_range(self.job), [0, 0])

    def test_media_after_endlist_cannot_be_reported_playable(self):
        self.output()
        playlist = self.path / "index.m3u8"
        text = playlist.read_text(encoding="utf-8").replace("#EXTINF:", "#EXT-X-ENDLIST\n#EXTINF:")
        playlist.write_text(text, encoding="utf-8")
        self.assertEqual(playable_range(self.job), [0, 0])

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
