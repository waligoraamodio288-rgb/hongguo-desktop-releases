import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from fractions import Fraction
from types import SimpleNamespace

import av
from fastapi import FastAPI
import uvicorn
from desktop_codec import describe_streams, video_codec_string
from desktop_hls import encode_hls, EncodingCancelled
from desktop_hls_budget import EncodingBudgetExceeded
from desktop_hls_service import HlsJobs, make_router
from desktop_playable_cache import PlayableEpisodeCache


class CodecTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.mp4'
        with av.open(str(self.source), 'w') as out:
            v = out.add_stream('libx264', rate=10)
            v.width = v.height = 64
            v.pix_fmt = 'yuv420p'
            for n in range(20):
                f = av.VideoFrame(64, 64, 'yuv420p')
                for p in f.planes:
                    p.update(bytes(p.buffer_size))
                f.pts, f.time_base = n, Fraction(1, 10)
                for p in v.encode(f): out.mux(p)
            for p in v.encode(): out.mux(p)

    def test_codec_profiles_and_unknown(self):
        self.assertEqual(video_codec_string('h264', bytes.fromhex('01640028ffe100')), 'avc1.640028')
        extra = bytes.fromhex('010160000000b0000000000078') + bytes(10)
        self.assertEqual(video_codec_string('hevc', extra), 'hvc1.1.6.L120.B0')
        self.assertIsNone(video_codec_string('hevc', b''))

    def test_native_video_description_survives_hls_audio_restrictions(self):
        video = SimpleNamespace(codec_context=SimpleNamespace(
            name='hevc', extradata=bytes.fromhex('010160000000b0000000000078') + bytes(10),
            width=1920, height=1080, bit_rate=2000000), average_rate=30)
        for name, extra in [('aac', bytes.fromhex('eb8a0800')), ('aac', bytes.fromhex('2b9208')),
                            ('aac', b''), ('opus', b'OpusHead')]:
            with self.subTest(codec=name, extra=extra):
                audio = SimpleNamespace(codec_context=SimpleNamespace(name=name, extradata=extra))
                media = SimpleNamespace(streams=SimpleNamespace(video=[video], audio=[audio]))
                description = describe_streams(media)
                self.assertFalse(description['copyEligible'])
                self.assertTrue(description['video']['contentType'].startswith('video/mp4; codecs="hvc1.'))
                self.assertEqual(description['audio'][0]['codec'], name)
        video.codec_context.extradata = b''
        self.assertEqual(describe_streams(media), {'copyEligible': False})

    def test_actual_h264_copy_and_mode_cache(self):
        target = self.root / 'copy'
        encode_hls(self.source, target, video_mode='copy')
        with av.open(str(target / 'index.m3u8')) as media:
            self.assertEqual(media.streams.video[0].codec_context.name, 'h264')
            frames=list(media.decode(video=0))
            self.assertEqual(len(frames), 20)
            self.assertLess(abs(frames[0].time), .00001)
            self.assertLess(abs(frames[-1].time-1.9), .00001)
        cache = PlayableEpisodeCache(self.root / 'cache', encoder=encode_hls)
        cache.store(self.source, target, video_mode='copy')
        self.assertTrue(cache.contains(self.source, 'copy'))
        self.assertFalse(cache.contains(self.source, 'h264'))
        cache.encode(self.source, self.root / 'restore', video_mode='copy')
        self.assertEqual((target / 'init.mp4').read_bytes(), (self.root / 'restore/init.mp4').read_bytes())

    def test_copy_cancel_budget_and_window_rejection(self):
        with self.assertRaises(EncodingCancelled):
            encode_hls(self.source, self.root / 'cancel', video_mode='copy', cancelled=lambda: True)
        with self.assertRaises(EncodingBudgetExceeded):
            encode_hls(self.source, self.root / 'budget', video_mode='copy', max_output_bytes=1)
        with self.assertRaises(ValueError):
            encode_hls(self.source, self.root / 'window', video_mode='copy', start_seconds=1)
        self.assertFalse((self.root / 'cancel/complete.marker').exists())
        self.assertFalse((self.root / 'budget/complete.marker').exists())

    def test_actual_precise_seek_stays_h264(self):
        origins = []
        target = self.root / 'seek'
        encode_hls(self.source, target, start_seconds=1.05, on_window=lambda a,b:origins.append((a,b)))
        self.assertGreaterEqual(origins[0][0], 1.05)
        self.assertLess(origins[0][0], 1.15)
        with av.open(str(target / 'index.m3u8')) as media:
            self.assertEqual(media.streams.video[0].codec_context.name, 'h264')
            first = next(media.decode(video=0))
            self.assertLess(abs(first.time), .01)

    def test_real_http_negotiation_auth_timeout_cancel_and_old_client(self):
        jobs = HlsJobs(self.root, lambda *_: self.source, negotiation_seconds=.25)
        app = FastAPI()
        app.include_router(make_router(jobs, lambda value: value == 'test-only-key'))
        import socket
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
        thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        thread.start()
        def stop():
            server.should_exit = True
            thread.join(5)
            sock.close()
        self.addCleanup(stop)
        for _ in range(100):
            if server.started: break
            time.sleep(.01)
        def request(path='', method='GET', body=None, headers=None):
            h = {'x-api-key': 'test-only-key', **(headers or {})}
            req = urllib.request.Request(f'http://127.0.0.1:{port}/desktop/hls'+path,
                method=method, headers=h, data=None if body is None else json.dumps(body).encode())
            with urllib.request.urlopen(req, timeout=5) as r:
                return None if r.status == 204 else json.load(r)
        query = '?series_id=1234567890123456&ep=1'
        with self.assertRaises(urllib.error.HTTPError) as error:
            request('/capabilities', headers={'x-api-key': 'wrong'})
        self.assertEqual(error.exception.code, 401)
        with self.assertRaises(urllib.error.HTTPError) as error:
            request('/capabilities', headers={'origin': 'https://untrusted.invalid'})
        self.assertEqual(error.exception.code, 403)
        identifier = request(query, 'POST', headers={'x-desktop-codec-negotiation': '1'})['id']
        for _ in range(100):
            status = request('/'+identifier+'/status')
            if status['source']: break
            time.sleep(.001)
        self.assertTrue(status['source']['copyEligible'])
        self.assertEqual(request('/'+identifier+'/mode', 'POST', {'mode':'copy'}), {'mode':'copy'})
        self.assertTrue(jobs.get(identifier).done.wait(5))
        self.assertFalse(jobs.get(identifier).failed)
        with self.assertRaises(urllib.error.HTTPError) as error:
            request('/'+identifier+'/mode', 'POST', {'mode':'h264'})
        self.assertEqual(error.exception.code, 409)
        request('/'+identifier, 'DELETE')
        for negotiated in (False, True):
            h = {'x-desktop-codec-negotiation':'1'} if negotiated else {}
            identifier = request(query, 'POST', headers=h)['id']
            job = jobs.get(identifier)
            self.assertTrue(job.done.wait(5))
            self.assertFalse(job.failed)
            self.assertEqual(job.video_mode, 'h264')
            request('/'+identifier, 'DELETE')
        identifier = request(query, 'POST', headers={'x-desktop-codec-negotiation':'1'})['id']
        job = jobs.get(identifier)
        request('/'+identifier, 'DELETE')
        self.assertTrue(job.done.wait(5))
        self.assertFalse(job.directory.exists())

    @unittest.skipUnless(os.environ.get('DESKTOP_HEVC_TEST_SOURCE'), 'local HEVC fixture not specified')
    def test_actual_hevc_audio_video_packet_identity(self):
        source = Path(os.environ['DESKTOP_HEVC_TEST_SOURCE'])
        target = self.root / 'hevc'
        with av.open(str(source)) as media:
            self.assertTrue(describe_streams(media)['copyEligible'])
            expected = [(p.stream.type, bytes(p)) for p in media.demux() if p.dts is not None]
        encode_hls(source, target, video_mode='copy')
        with av.open(str(target / 'index.m3u8')) as media:
            self.assertEqual(media.streams.video[0].codec_context.name, 'hevc')
            actual = [(p.stream.type, bytes(p)) for p in media.demux() if p.dts is not None]
        for kind in ('video', 'audio'):
            self.assertEqual([p for k,p in expected if k==kind], [p for k,p in actual if k==kind])


if __name__ == '__main__': unittest.main()
