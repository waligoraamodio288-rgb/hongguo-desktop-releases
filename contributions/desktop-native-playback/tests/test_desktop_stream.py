"""Range/CENC regressions and first-segment readiness before input completion."""
import io
from pathlib import Path
import random
import tempfile
import threading
import unittest
import json
import socket
import time
import urllib.request
import urllib.error

import av
from desktop_stream import ProgressiveSource, SourceReadError, open_media
from desktop_hls import encode_hls


KEY = "11" * 16  # Public test fixture key, never a provider key.


class Response:
    def __init__(self, data, start, end):
        self.status_code = 206
        self.headers = {"Content-Range": f"bytes {start}-{end}/{len(data)}", "ETag": '"fixture"'}
        self.data, self.start, self.end = data, start, end
        self.closed = False

    def iter_content(self, size):
        for offset in range(self.start, self.end + 1, size):
            yield self.data[offset:min(offset + size, self.end + 1)]

    def close(self):
        self.closed = True


def source_for(data, **kwargs):
    calls = []
    def request(method, url, **options):
        start, end = map(int, options["headers"]["Range"].split("=")[1].split("-"))
        value = Response(data, start, min(end, len(data) - 1))
        calls.append(value)
        return value
    return ProgressiveSource("https://fixture.invalid/video.mp4?private=not-logged",
                             request=request, identity="fixture", **kwargs), calls


class StreamTests(unittest.TestCase):

    def test_authenticated_http_ranges_head_invalid_and_release(self):
        from fastapi import FastAPI
        import uvicorn
        from desktop_hls_service import HlsJobs, Job, make_router
        data = random.Random(3).randbytes(300000)
        source, calls = source_for(data, key=KEY)
        source.block(0, lambda: False)
        with tempfile.TemporaryDirectory() as temp:
            jobs = HlsJobs(temp, lambda *_: source)
            identifier = 'a' * 32
            job = Job(identifier, Path(temp) / identifier, source=source)
            job.done.set()
            jobs.jobs[identifier] = job
            app = FastAPI()
            app.include_router(make_router(jobs, lambda value: value == 'test-only'))
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            origin = 'http://127.0.0.1:' + str(listener.getsockname()[1])
            server = uvicorn.Server(uvicorn.Config(app, log_level='critical'))
            worker = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
            worker.start()
            def request(method='GET', **headers):
                return urllib.request.urlopen(urllib.request.Request(
                    origin + '/desktop/hls/' + identifier + '/source.mp4', method=method,
                    headers={'x-api-key': 'test-only', **headers}), timeout=5)
            try:
                for _ in range(100):
                    if server.started: break
                    time.sleep(.01)
                with request('HEAD') as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(int(response.headers['content-length']), len(data))
                    self.assertEqual(response.read(), b'')
                self.assertEqual(len(calls), 1)
                for value, expected in [('bytes=100000-100019', data[100000:100020]),
                                        ('bytes=-31', data[-31:]), ('bytes=299970-', data[299970:])]:
                    with request(Range=value) as response:
                        self.assertEqual(response.status, 206)
                        self.assertEqual(response.read(), expected)
                for headers, code in [({'x-api-key': 'wrong'}, 401),
                                      ({'Origin': 'https://untrusted.invalid'}, 403),
                                      ({'Range': 'bytes=999999-'}, 416),
                                      ({'Range': 'bytes=0-1,3-4'}, 416)]:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        request(**headers)
                    self.assertEqual(error.exception.code, code)
                self.assertNotIn(KEY, json.dumps(source.snapshot()))
                jobs.release(identifier)
                with self.assertRaises(urllib.error.HTTPError) as error: request()
                self.assertEqual(error.exception.code, 404)
            finally:
                server.should_exit = True
                worker.join(5)
                listener.close()

    def test_range_seek_short_reads_cancel_and_memory_bound(self):
        data = random.Random(1).randbytes(300000)
        source, calls = source_for(data)
        source.max_blocks = 2
        with source.reader() as reader:
            self.assertEqual(reader.read(30), data[:30])
            self.assertEqual(source.snapshot()["receivedBytes"], 65536)
            reader.seek(-50, 2)
            self.assertEqual(reader.read(100), data[-50:])
            reader.seek(100000)
            self.assertEqual(reader.read(20), data[100000:100020])
            self.assertLessEqual(source.snapshot()["cachedBytes"], 2 * 65536)
            reader.stopped.set()
            with self.assertRaises(InterruptedError): reader.read(10)
        self.assertTrue(all(r.closed for r in calls))
        self.assertNotIn("private", repr(source))
        self.assertNotIn("private", str(source.cache_identity()))

    def test_bad_range_and_transport_error_are_source_failures(self):
        for kind in ("ignored", "changed", "short", "transport"):
            with self.subTest(kind=kind):
                def request(*args, **kwargs):
                    if kind == "transport": raise RuntimeError("secret-provider-url")
                    r = Response(b"x" * 200000, 0, 65535)
                    if kind == "ignored": r.status_code = 200
                    if kind == "changed": r.headers["Content-Range"] = "bytes 1-65535/200000"
                    if kind == "short": r.data = b"x"
                    return r
                source = ProgressiveSource("https://fixture.invalid/v", request=request, identity="fixture")
                with self.assertRaises(SourceReadError) as error:
                    source.reader().read(10)
                self.assertTrue(source.network_failed.is_set())
                self.assertNotIn("secret", str(error.exception))

    def test_encrypted_packets_and_h264_first_segment_before_full_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "encrypted.mp4"
            rng = random.Random(7)
            with av.open(str(fixture), "w", format="mp4", options={
                    "movflags": "+faststart", "encryption_scheme": "cenc-aes-ctr",
                    "encryption_key": KEY, "encryption_kid": "22" * 16}) as output:
                video = output.add_stream("libx264", rate=10)
                video.width = video.height = 64
                video.pix_fmt = "yuv420p"
                video.options = {"preset": "ultrafast", "g": "20", "crf": "18"}
                for index in range(180):
                    frame = av.VideoFrame(64, 64, "yuv420p")
                    frame.pts = index
                    for plane in frame.planes: plane.update(rng.randbytes(plane.buffer_size))
                    for packet in video.encode(frame): output.mux(packet)
                for packet in video.encode(): output.mux(packet)
            data = fixture.read_bytes()
            source, calls = source_for(data, key=KEY)
            with open_media(source) as media:
                frame = next(media.decode(video=0))
                self.assertEqual(frame.width, 64)
            self.assertFalse(source.snapshot()["complete"])
            evidence = []
            out = root / "hls"
            encode_hls(source, out, lambda:evidence.append({
                "progress": source.snapshot(), "complete": (out / "complete.marker").exists(),
                "segment": (out / "seg000000.m4s").exists()}))
            self.assertTrue(evidence[0]["segment"])
            self.assertFalse(evidence[0]["complete"])
            self.assertFalse(evidence[0]["progress"]["complete"])
            self.assertTrue((out / "complete.marker").is_file())
            self.assertTrue(all(r.closed for r in calls))


if __name__ == "__main__": unittest.main()
