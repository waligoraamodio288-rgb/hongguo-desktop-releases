"""Native admission and autonomous session ownership regressions."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest

import av
from fastapi import HTTPException
from desktop_hls_service import HlsJobs, make_router


def eventually(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('condition did not become true')


class LifecycleTests(unittest.TestCase):
    def test_delete_reports_pending_until_native_teardown_and_preserves_output(self):
        native=SimpleNamespace(release=lambda _:False)
        jobs=self.jobs(native=native)
        jobs._run=lambda *_:None
        job=jobs.create('1234567890123456',1)
        job.directory.mkdir();(job.directory/'owned').write_bytes(b'owned');job.done.set()
        delete=next(r.endpoint for r in make_router(jobs,lambda _:True).routes if r.path.endswith('/{identifier}') and 'DELETE' in r.methods)
        self.assertEqual(delete(job.id).status_code,202)
        self.assertIn(job.id,jobs.jobs);self.assertTrue(job.directory.exists())
        native.release=lambda _:True
        self.assertEqual(delete(job.id).status_code,204)
        self.assertNotIn(job.id,jobs.jobs);self.assertFalse(job.directory.exists())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'owned.mp4'
        with av.open(str(self.source), 'w') as output:
            video = output.add_stream('libx264', rate=10)
            video.width = video.height = 64
            video.pix_fmt = 'yuv420p'
            for i in range(20):
                frame = av.VideoFrame(64, 64, 'yuv420p')
                frame.pts = i
                for plane in frame.planes:
                    plane.update(bytes(plane.buffer_size))
                for packet in video.encode(frame): output.mux(packet)
            for packet in video.encode(): output.mux(packet)

    def jobs(self, **kwargs):
        jobs = HlsJobs(self.root, lambda *_: self.source, **kwargs)
        self.addCleanup(lambda: jobs.close() if hasattr(jobs, 'close') else
                        [jobs.release(key) for key in list(jobs.jobs)])
        return jobs

    def test_native_admitted_while_encoder_busy_and_total_bound_retained(self):
        encoding = threading.Event()
        unblock = threading.Event()
        prepared = threading.Event()
        def encode(source, target, ready, **kwargs):
            encoding.set()
            unblock.wait(3)
        self.addCleanup(unblock.set)
        native = SimpleNamespace(prepare=lambda _: prepared.set(), release=lambda _: None)
        jobs = self.jobs(encoder=encode, native=native, max_workers=1, max_jobs=2)
        first = jobs.create('1234567890123456', 1)
        self.assertTrue(encoding.wait(2))
        second = jobs.create('1234567890123456', 2, negotiate_codec=True)
        eventually(lambda: second.source_description is not None)
        with jobs.guard:
            second.video_mode = 'native'
            second.mode_selected.set()
        self.assertTrue(prepared.wait(1), 'native waited for an encoder slot')
        self.assertTrue(second.done.wait(1))
        self.assertFalse(second.failed)
        with self.assertRaises(HTTPException) as error:
            jobs.create('1234567890123456', 3)
        self.assertEqual(error.exception.status_code, 503)
        unblock.set()
        self.assertTrue(first.done.wait(2))

    def test_queued_hls_cancel_does_not_run_encoder_or_exceed_workers(self):
        entered = threading.Event()
        unblock = threading.Event()
        calls = []
        def encode(*args, **kwargs):
            calls.append(1)
            entered.set()
            unblock.wait(3)
        self.addCleanup(unblock.set)
        jobs = self.jobs(encoder=encode, max_workers=1)
        first = jobs.create('1234567890123456', 1)
        self.assertTrue(entered.wait(2))
        second = jobs.create('1234567890123456', 2)
        time.sleep(.15)
        self.assertEqual(len(calls), 1)
        jobs.release(second.id)
        self.assertTrue(second.done.wait(1))
        self.assertEqual(second.failure_code, 'cancelled')
        unblock.set()
        self.assertTrue(first.done.wait(2))
        self.assertEqual(len(calls), 1)

    def test_expiry_runs_without_new_requests_and_close_stops_reaper(self):
        releases = []
        native = SimpleNamespace(prepare=lambda job: job.directory.mkdir(), release=releases.append)
        jobs = self.jobs(native=native, idle_seconds=.25)
        job = jobs.create('1234567890123456', 1, negotiate_codec=True)
        eventually(lambda: job.source_description is not None)
        with jobs.guard:
            job.video_mode = 'native'
            job.mode_selected.set()
        self.assertTrue(job.done.wait(1))
        (job.directory / 'partial').write_bytes(b'partial')
        eventually(lambda: job.id not in jobs.jobs)
        self.assertIn(job.id, releases)
        self.assertFalse(job.directory.exists())
        jobs.close()
        self.assertTrue(jobs.reaper is None or not jobs.reaper.is_alive())
        with self.assertRaises(HTTPException):
            jobs.create('1234567890123456', 2)
