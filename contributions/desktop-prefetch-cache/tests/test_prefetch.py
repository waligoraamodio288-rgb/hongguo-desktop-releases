import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

from desktop_hls import EncodingCancelled
from job_fixture import Job
from desktop_prefetch import EpisodePrefetcher
from desktop_playable_cache import PlayableEpisodeCache


PROFILE_FILES = (Path(__file__).parent / "desktop_hls.py",
                 Path(__file__).parent / "encoder_budget_fixture.py")

SERIES = "1234567890123456"


def metadata(count=8):
    return [{"index": n, "vid": str(10000000 + n)} for n in range(1, count + 1)]


def complete_output(directory, payload=b"fragment"):
    directory = Path(directory)
    directory.mkdir(parents=False, exist_ok=False)
    (directory / "init.mp4").write_bytes(b"init")
    (directory / "seg000000.m4s").write_bytes(payload)
    (directory / "index.m3u8").write_text(
        '#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:2,\nseg000000.m4s\n#EXT-X-ENDLIST\n', encoding="utf-8")
    (directory / "complete.marker").write_text("desktop-hls-v1\n", encoding="ascii")


def encoder(source, directory, on_ready=lambda: None, *, cancelled=lambda: False, **kwargs):
    if cancelled():
        raise EncodingCancelled()
    complete_output(directory)
    if kwargs.get("start_seconds"):
        kwargs["on_window"](kwargs["start_seconds"], 100.0)
    on_ready()


class PrefetchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        self.sources = {}
        for item in metadata():
            source = self.root / (item["vid"] + ".mp4")
            source.write_bytes(b"source")
            self.sources[item["vid"]] = source

    def make(self, loader=None, encode=encoder, **kwargs):
        self.calls = []
        def source(vid):
            self.calls.append(int(vid) - 10000000)
            return self.sources[vid]
        value = EpisodePrefetcher(loader or source, lambda sid: ({}, metadata()),
                                 self.root / "cache", encoder=encode, profile_files=PROFILE_FILES, **kwargs)
        self.addCleanup(value.close)
        return value

    def job(self, value, episode):
        job = Job(uuid.uuid4().hex, self.root / uuid.uuid4().hex)
        value.begin(job, SERIES, episode)
        value.before_work(job)
        source = value.load_source(SERIES, episode)
        return job, source

    def complete(self, value, episode):
        job, source = self.job(value, episode)
        value.encode(source, job.directory)
        value.finish(job, SERIES, episode, source)
        return job, source

    def test_download_overlaps_current_but_future_encoding_waits_for_completion(self):
        downloaded = threading.Event()
        encoded = []
        def load(vid):
            self.calls.append(int(vid) - 10000000)
            if vid == "10000005":
                downloaded.set()
            return self.sources[vid]
        def tracked(source, directory, on_ready=lambda: None, **kwargs):
            encoded.append(Path(source).stem)
            encoder(source, directory, on_ready, **kwargs)
        value = self.make(load, encode=tracked)
        job, source = self.job(value, 2)
        job.ready.set()  # A first playable segment is not entire completion.
        self.assertTrue(downloaded.wait(3))
        self.assertEqual(self.calls, [2, 3, 4, 5])
        self.assertEqual(encoded, [])
        self.assertIsNone(value.worker)
        self.assertFalse(value.snapshot()["currentPlayableComplete"])
        value.encode(source, job.directory)
        self.assertEqual(encoded, ["10000002"])
        value.finish(job, SERIES, 2, source)
        self.assertTrue(value.wait_idle(3))
        self.assertEqual(self.calls, [2, 3, 4, 5])
        self.assertEqual(encoded, ["10000002", "10000003", "10000004", "10000005"])
        self.assertEqual(value.snapshot()["completedEpisodes"], [3, 4, 5])
        self.assertTrue(value.snapshot()["currentPlayableComplete"])
        for n in range(2, 6):
            self.assertTrue(value.cache.contains(self.sources[str(10000000 + n)]))

    def test_prefetched_playback_does_not_encode_again(self):
        value = self.make()
        self.complete(value, 2)
        self.assertTrue(value.wait_idle(3))
        value.cache.encoder = lambda *a, **k: self.fail("Unexpected encoding on cache hit")
        job, source = self.job(value, 3)
        value.encode(source, job.directory, job.ready.set)
        self.assertTrue(job.ready.is_set())
        self.assertTrue((job.directory / "complete.marker").is_file())
        value.close()
        value.finish(job, SERIES, 3, source)

    def test_tail_unsorted_metadata_and_duplicate_vid(self):
        value = self.make()
        value.episode_loader = lambda sid: ({}, list(reversed(metadata(5))) + [{"index": 6, "vid": "10000005"}])
        self.complete(value, 4)
        self.assertTrue(value.wait_idle(3))
        self.assertEqual(self.calls, [4, 5])

    def test_background_failure_isolated_and_continues(self):
        def load(vid):
            if vid == "10000003":
                raise RuntimeError("https://secret.invalid/?token=private")
            return self.sources[vid]
        value = self.make(load, status_path=self.root / "status.json")
        self.complete(value, 2)
        self.assertTrue(value.wait_idle(3))
        value._report()
        snapshot = json.loads((self.root / "status.json").read_text())
        self.assertEqual(snapshot["failedEpisodes"], [3])
        self.assertEqual(snapshot["completedEpisodes"], [4, 5])
        self.assertNotIn("private", (self.root / "status.json").read_text())

    def test_foreground_failure_queues_nothing(self):
        value = self.make()
        job, source = self.job(value, 2)
        job.failed = True
        value.finish(job, SERIES, 2, source)
        self.assertTrue(value.wait_idle(3))
        self.assertIsNone(value.worker)

    def test_new_foreground_cancels_background_encoder_and_drops_old_queue(self):
        started, cancelled = threading.Event(), threading.Event()
        self.addCleanup(cancelled.set)
        def blocked(source, directory, on_ready=lambda: None, *, cancelled=lambda: False):
            if Path(source).name == "10000002.mp4":
                started.set()
                while not cancelled():
                    threading.Event().wait(0.01)
                raise EncodingCancelled()
            encoder(source, directory, on_ready, cancelled=cancelled)
        value = self.make(encode=blocked)
        self.complete(value, 1)
        self.assertTrue(started.wait(3))
        newer = Job(uuid.uuid4().hex, self.root / uuid.uuid4().hex)
        value.begin(newer, SERIES, 6)
        value.before_work(newer)
        self.assertIsNone(value.active)
        source = value.load_source(SERIES, 6)
        value.encode(source, newer.directory)
        value.finish(newer, SERIES, 6, source)
        self.assertTrue(value.wait_idle(3))
        self.assertEqual(self.calls[0], 1)
        self.assertEqual([n for n in self.calls if n >= 6], [6, 7, 8])
        self.assertFalse(value.cache.contains(self.sources["10000002"]))

    def test_waiting_foreground_is_serial_and_cancel_releases_queue(self):
        value = self.make(ahead=0)
        first, source = self.job(value, 1)
        second = Job(uuid.uuid4().hex, self.root / uuid.uuid4().hex)
        value.begin(second, SERIES, 2)
        second.cancelled.set()
        with self.assertRaises(EncodingCancelled):
            value.before_work(second)
        second.failed = True
        value.finish(second, SERIES, 2, None)
        self.assertEqual(value.busy, first.id)
        value.encode(source, first.directory)
        value.finish(first, SERIES, 1, source)
        self.assertTrue(value.wait_idle(0))

    def test_seek_window_then_current_full_before_future(self):
        encoded = []
        def tracked(source, directory, on_ready=lambda: None, **kwargs):
            encoded.append((Path(source).stem, kwargs.get("start_seconds", 0)))
            encoder(source, directory, on_ready, **kwargs)
        value = self.make(encode=tracked)
        job, source = self.job(value, 2)
        job.start_seconds = 10
        windows = []
        value.encode(source, job.directory, start_seconds=10, on_window=lambda *args: windows.append(args))
        self.assertEqual(windows, [(10, 100.0)])
        value.finish(job, SERIES, 2, source)
        self.assertTrue(value.wait_idle(3))
        self.assertEqual(encoded, [("10000002", 10), ("10000002", 0), ("10000003", 0), ("10000004", 0), ("10000005", 0)])

    def test_current_cache_failure_blocks_future_preparation(self):
        value = self.make()
        job, source = self.job(value, 2)
        complete_output(job.directory)
        value.cache.encoder = lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full"))
        value.finish(job, SERIES, 2, source)
        self.assertTrue(value.wait_idle(3))
        self.assertEqual(self.calls[0], 2)
        self.assertEqual(value.snapshot()["failedEpisodes"], [2])

    def test_worker_start_failure_does_not_fail_completed_current(self):
        value = self.make()
        job, source = self.job(value, 2)
        value.encode(source, job.directory)
        with patch("desktop_prefetch.threading.Thread.start", side_effect=RuntimeError("thread limit")):
            value.finish(job, SERIES, 2, source)
        self.assertTrue(value.wait_idle(0))
        self.assertEqual(value.snapshot()["failedEpisodes"], [3, 4, 5])

    def test_diagnostic_io_failure_does_not_fail_current(self):
        value = self.make(status_path=self.root / "missing/status.json", ahead=0)
        self.complete(value, 1)
        self.assertTrue(value.wait_idle(3))

    def test_one_background_download_and_switch_discards_old_waiters(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []
        def load(vid):
            calls.append(int(vid) - 10000000)
            if vid == "10000002":
                started.set()
                if not release.wait(3):
                    raise OSError("test timeout")
            return self.sources[vid]
        value = self.make(load)
        first, source = self.job(value, 1)
        self.assertTrue(started.wait(3))
        self.assertEqual(calls, [1, 2])
        first.cancelled.set()
        value.finish(first, SERIES, 1, source)
        second, second_source = self.job(value, 6)
        self.assertEqual(calls, [1, 2, 6])
        value.encode(second_source, second.directory)
        value.finish(second, SERIES, 6, second_source)
        release.set()
        self.assertTrue(value.wait_idle(3))
        self.assertEqual(calls, [1, 2, 6, 7, 8])
        self.assertEqual(value.snapshot()["downloadCompletedEpisodes"], [7, 8])
        self.assertEqual(value.snapshot()["completedEpisodes"], [7, 8])

    def test_downloader_start_failure_isolated(self):
        value = self.make()
        with patch("desktop_prefetch.threading.Thread.start", side_effect=RuntimeError("thread limit")):
            job, source = self.job(value, 2)
        value.encode(source, job.directory)
        value.finish(job, SERIES, 2, source)
        self.assertTrue(value.wait_idle(3))
        self.assertTrue(value.snapshot()["currentPlayableComplete"])
        self.assertEqual(value.snapshot()["failedEpisodes"], [3, 4, 5])



class PlayableCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        self.source = self.root / "source.mp4"
        self.source.write_bytes(b"source")
        self.cache = PlayableEpisodeCache(self.root / "cache", encoder=encoder, profile_files=PROFILE_FILES)
        self.output = self.root / "original-output"
        complete_output(self.output)

    def test_incomplete_and_corrupted_cache_are_not_hits(self):
        artifact = self.cache.store(self.source, self.output)
        self.assertTrue(self.cache.contains(self.source))
        fragment = artifact / "seg000000.m4s"
        fragment.write_bytes(b"changed!")
        self.assertFalse(self.cache.contains(self.source))
        self.cache.store(self.source, self.output)
        (artifact / "complete.marker").unlink()
        self.assertFalse(self.cache.contains(self.source))

    def test_source_and_encoding_policy_fingerprints_invalidate(self):
        self.cache.store(self.source, self.output)
        self.cache.profile = "changed-policy"
        self.assertFalse(self.cache.contains(self.source))
        self.cache.store(self.source, self.output)
        self.source.write_bytes(b"modified source")
        self.assertFalse(self.cache.contains(self.source))

    def test_same_metadata_different_source_content_cannot_play_another_episode(self):
        self.cache.store(self.source, self.output)
        other = self.root / "other" / self.source.name
        other.parent.mkdir()
        other.write_bytes(b"second")
        stamp = self.source.stat()
        os.utime(other, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertEqual(other.name, self.source.name)
        self.assertEqual(other.stat().st_size, stamp.st_size)
        self.assertEqual(other.stat().st_mtime_ns, stamp.st_mtime_ns)
        self.assertFalse(self.cache.contains(other))
        self.assertFalse(self.cache.restore(other, self.root / "wrong-session"))
        second_output = self.root / "second-output"
        complete_output(second_output, payload=b"second-episode")
        self.cache.store(other, second_output)
        replay = self.root / "correct-session"
        self.assertTrue(self.cache.restore(other, replay))
        self.assertEqual((replay / "seg000000.m4s").read_bytes(), b"second-episode")

    def test_source_change_with_preserved_size_and_mtime_invalidates_cache(self):
        self.cache.store(self.source, self.output)
        stamp = self.source.stat()
        self.source.write_bytes(b"other!")
        os.utime(self.source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertEqual(self.source.stat().st_size, stamp.st_size)
        self.assertEqual(self.source.stat().st_mtime_ns, stamp.st_mtime_ns)
        self.assertFalse(self.cache.contains(self.source))

    def test_restore_publishes_completion_marker_after_every_media_file(self):
        self.cache.store(self.source, self.output)
        replay = self.root / "replay"
        copy = shutil.copyfile
        observed = []
        def watched(source, destination):
            observed.append(Path(destination).name)
            self.assertFalse((replay / "complete.marker").exists())
            if Path(destination).name == "complete.marker":
                self.assertTrue((replay / "index.m3u8").is_file())
                self.assertTrue((replay / "init.mp4").is_file())
                self.assertTrue((replay / "seg000000.m4s").is_file())
            return copy(source, destination)
        with patch("desktop_playable_cache.shutil.copyfile", side_effect=watched):
            self.assertTrue(self.cache.restore(self.source, replay))
        self.assertEqual(observed[-1], "complete.marker")

    def test_restore_cancelled_after_media_copy_never_publishes_marker(self):
        self.cache.store(self.source, self.output)
        replay = self.root / "cancelled-replay"
        cancel = threading.Event()
        copy = shutil.copyfile
        def watched(source, destination):
            result = copy(source, destination)
            if Path(destination).name.endswith(".m4s"):
                self.assertFalse((replay / "complete.marker").exists())
                cancel.set()
            return result
        with patch("desktop_playable_cache.shutil.copyfile", side_effect=watched):
            with self.assertRaises(EncodingCancelled):
                self.cache.restore(self.source, replay, cancel.is_set)
        self.assertFalse(replay.exists())

    def test_restore_partial_copy_failure_cleans_incomplete_session(self):
        self.cache.store(self.source, self.output)
        replay = self.root / "interrupted-replay"
        copy = shutil.copyfile
        def interrupted(source, destination):
            if Path(destination).name.endswith(".m4s"):
                Path(destination).write_bytes(b"partial")
                raise OSError("copy interrupted")
            return copy(source, destination)
        with patch("desktop_playable_cache.shutil.copyfile", side_effect=interrupted):
            with self.assertRaisesRegex(OSError, "copy interrupted"):
                self.cache.restore(self.source, replay)
        self.assertFalse(replay.exists())

    def test_cancelled_commit_is_not_visible_and_stage_is_removed(self):
        with self.assertRaises(EncodingCancelled):
            self.cache.store(self.source, self.output, cancelled=lambda: True)
        self.assertFalse(self.cache.contains(self.source))
        self.assertEqual(list(self.cache.root.iterdir()), [])

    def test_quota_eviction_preserves_playing_session_and_unknown_directory(self):
        first = self.cache.store(self.source, self.output)
        first_bytes = sum(path.stat().st_size for path in first.iterdir())
        output_bytes = sum(path.stat().st_size for path in self.output.iterdir())
        self.cache.quota_bytes = first_bytes + output_bytes + 65536 - 1
        session = self.root / "playing"
        self.assertTrue(self.cache.restore(self.source, session))
        unknown = self.cache.root / "user-data"
        unknown.mkdir()
        (unknown / "keep.txt").write_text("keep")
        second = self.root / "second.mp4"
        second.write_bytes(b"other source")
        self.cache.store(second, self.output)
        self.assertFalse(first.exists())
        self.assertTrue((session / "seg000000.m4s").is_file())
        self.assertTrue((unknown / "keep.txt").is_file())

    def test_unsafe_playlist_cannot_be_committed(self):
        (self.output / "index.m3u8").write_text(
            '#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n../secret\n#EXT-X-ENDLIST\n')
        with self.assertRaises(ValueError):
            self.cache.store(self.source, self.output)

    def test_unowned_directory_cannot_be_deleted(self):
        directory = self.cache.root / ("a" * 64)
        directory.mkdir()
        (directory / "keep.txt").write_text("keep")
        with self.assertRaises(ValueError):
            self.cache._remove_owned(directory)
        self.assertTrue((directory / "keep.txt").is_file())

    def test_cache_io_failure_falls_back_to_original_encode(self):
        with patch.object(self.cache, "store", side_effect=OSError("disk full")):
            output = self.root / "new-output"
            self.cache.encode(self.source, output)
            self.assertTrue((output / "complete.marker").is_file())

    def test_missing_source_is_a_cache_miss(self):
        self.cache.store(self.source, self.output)
        self.source.unlink()
        self.assertFalse(self.cache.contains(self.source))

    def test_orphan_stage_counts_toward_quota_without_being_deleted(self):
        stage = self.cache.root / ("stage-" + "a" * 32)
        stage.mkdir()
        (stage / "segment").write_bytes(b"x" * 100)
        self.cache.quota_bytes = 50
        with self.assertRaises(OSError):
            self.cache._reserve(1)
        self.assertTrue((stage / "segment").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
