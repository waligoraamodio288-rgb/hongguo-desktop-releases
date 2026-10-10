"""Native ownership/protocol regressions; rendering is verified in WebView2."""
import ctypes as C
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

import av
from fastapi import FastAPI
import uvicorn
from desktop_native import validate_control, NativeHost, NativeSession, Event
from desktop_hls_service import HlsJobs, make_router
from desktop_hls import encode_hls
from desktop_prefetch import EpisodePrefetcher


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.mp4'
        with av.open(str(self.source), 'w') as output:
            video = output.add_stream('libx264', rate=10)
            video.width = video.height = 64
            video.pix_fmt = 'yuv420p'
            for _ in range(5):
                frame = av.VideoFrame(64, 64, 'yuv420p')
                for plane in frame.planes:
                    plane.update(bytes(plane.buffer_size))
                for packet in video.encode(frame):
                    output.mux(packet)
            for packet in video.encode():
                output.mux(packet)

    def test_control_rejects_command_injection_and_invalid_values(self):
        for value in ({'path':'C:/secret'}, {'command':['loadfile','x']}, {'hwnd':1},
                      {'rate':float('nan')}, {'seek':True}, {'volume':2}, {'paused':'yes'},
                      {'rect':[-1,0,10,10]}, {'rect':[0,0,10.5,10]}, {'rect':[0,0,0,10]}, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_control(value)
        self.assertEqual(validate_control({'rate':3,'paused':True,'rect':[0,0,800,400]}),
                         {'rate':3,'paused':True,'rect':[0,0,800,400]})

    def test_missing_or_unverified_dll_disables_native(self):
        path = self.root/'not-a-dll.dll'
        self.assertFalse(NativeHost(dll_path=path).available)
        path.write_bytes(b'not executable')
        self.assertFalse(NativeHost(dll_path=path).available)

    def test_cancel_before_prepare_lock_cannot_leave_registered_session(self):
        host=NativeHost(dll_path=self.root/'missing.dll');host.available=True
        job=SimpleNamespace(id='cancel-race',cancelled=threading.Event())
        class CancelAtLock:
            def __enter__(self):job.cancelled.set()
            def __exit__(self,*args):pass
        host.guard=CancelAtLock()
        with patch('desktop_native.NativeSession') as session:
            with self.assertRaises(RuntimeError):host.prepare(job)
            session.assert_not_called()
        self.assertEqual(host.sessions,{})

    def test_cancel_at_thread_start_removes_inserted_session(self):
        host=NativeHost(dll_path=self.root/'missing.dll');host.available=True
        job=SimpleNamespace(id='cancel-start',cancelled=threading.Event())
        with patch.object(host,'parent_window',return_value=1), patch('desktop_native.NativeSession') as factory:
            session=factory.return_value;session.thread.start.side_effect=job.cancelled.set
            with self.assertRaises(RuntimeError):host.prepare(job)
            session.close.assert_called_once()
        self.assertEqual(host.sessions,{})

    def test_native_protocol_auth_no_transcode_and_cleanup(self):
        class Host:
            available = True
            active = set()
            released = []
            def prepare(self, job): self.active.add(job.id)
            def snapshot(self, identifier): return {'state':'ready','decoder':'software'}
            def control(self, identifier, body): validate_control(body); return 1
            def release(self, identifier): self.released.append(identifier); self.active.discard(identifier)
        host = Host()
        def unexpected_encoder(*a, **kw):
            raise AssertionError('Native must not encode H264')
        jobs = HlsJobs(self.root, lambda *_:self.source, native=host, encoder=unexpected_encoder)
        app = FastAPI()
        app.include_router(make_router(jobs, lambda key:key=='test-only'))
        listener = socket.socket()
        listener.bind(('127.0.0.1',0))
        origin = 'http://127.0.0.1:'+str(listener.getsockname()[1])
        server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
        thread = threading.Thread(target=lambda:server.run(sockets=[listener]), daemon=True)
        thread.start()
        def stop(): server.should_exit=True; thread.join(3)
        self.addCleanup(stop)
        def request(path, method='GET', body=None, key='test-only', extra=None):
            headers={'x-api-key':key, **(extra or {})}
            data=None
            if body is not None:
                data=json.dumps(body).encode(); headers['content-type']='application/json'
            return urllib.request.urlopen(urllib.request.Request(origin+'/desktop/hls'+path,
                method=method,headers=headers,data=data),timeout=5)
        with patch('desktop_hls_service.describe_streams',return_value={'copyEligible':False,
                       'video':{'contentType':'video/mp4; codecs="hvc1.1.6.L120.B0"'},'audio':[]}):
            with request('/capabilities') as response:
                self.assertEqual(json.load(response)['nativePlayback'],1)
            with self.assertRaises(urllib.error.HTTPError) as error:
                request('/capabilities',key='wrong')
            self.assertEqual(error.exception.code,401)
            with self.assertRaises(urllib.error.HTTPError) as error:
                request('/capabilities',extra={'Origin':'https://untrusted.invalid'})
            self.assertEqual(error.exception.code,403)
            with request('?series_id=1234567890123456&ep=1&start_seconds=0.1','POST',
                         extra={'x-desktop-codec-negotiation':'1'}) as response:
                identifier=json.load(response)['id']
            job=jobs.get(identifier)
            until=time.monotonic()+3
            while job.source_description is None and time.monotonic()<until: time.sleep(.01)
            with request('/'+identifier+'/mode','POST',{'mode':'native'}) as response:
                self.assertEqual(json.load(response)['mode'],'native')
            self.assertTrue(job.done.wait(3))
            self.assertFalse(job.failed)
            self.assertEqual(job.window_origin,0)
            self.assertFalse(job.directory.exists())
            with request('/'+identifier+'/status') as response:
                value=json.load(response)
                self.assertFalse(value['playlistReady'])
                self.assertEqual(value['native']['decoder'],'software')
                self.assertGreater(value['playableRange'][1],.1)
            with self.assertRaises(urllib.error.HTTPError) as error:
                request('/'+identifier+'/control','POST',{'command':'quit'})
            self.assertEqual(error.exception.code,400)
            with request('/'+identifier+'/control','POST',{'rate':3,'paused':True}) as response:
                self.assertEqual(json.load(response)['revision'],1)
            with request('/'+identifier,'DELETE') as response:
                self.assertEqual(response.status,204)
            self.assertFalse(host.active)
            self.assertNotIn(identifier,jobs.jobs)

    def test_native_prefetch_keeps_original_codec(self):
        calls=[]
        def encoder(*args, **kwargs):
            calls.append(kwargs.get('video_mode','h264'))
            return encode_hls(*args, **kwargs)
        prefetch=EpisodePrefetcher(lambda _:self.source,
            lambda _:('series',[{'index':1,'vid':'1234567890123456'}]),
            self.root/'cache',encoder=encoder)
        self.addCleanup(prefetch.close)
        job=SimpleNamespace(id='a'*32,cancelled=threading.Event(),failed=False,video_mode='native')
        job.source_description={'copyEligible':True}
        prefetch.begin(job,'1234567890123456',1)
        prefetch.before_work(job)
        source=prefetch.load_source('1234567890123456',1)
        prefetch.finish(job,'1234567890123456',1,source)
        self.assertTrue(prefetch.wait_idle(3))
        self.assertEqual(calls,[])
        self.assertFalse(prefetch.cache.contains(source,'copy'))
        self.assertFalse(prefetch.cache.contains(source,'h264'))
        self.assertTrue(prefetch.snapshot()['currentSourceComplete'])
        self.assertFalse(prefetch.snapshot()['currentPlayableComplete'])
        self.assertEqual(prefetch.snapshot()['cacheKind'],'original-media')

    def test_native_audio_keeps_future_source_downloads_without_any_encoding(self):
        calls, downloads = [], []
        def load(vid):
            downloads.append(vid)
            return self.source
        def encoder(*args, **kwargs):
            calls.append(kwargs)
            raise AssertionError('Native-only audio must not cause background encoding')
        episodes=[{'index':i,'vid':str(1234567890123456+i)} for i in range(1,5)]
        prefetch=EpisodePrefetcher(load,lambda _:('series',episodes),self.root/'cache',encoder=encoder)
        self.addCleanup(prefetch.close)
        job=SimpleNamespace(id='a'*32,cancelled=threading.Event(),failed=False,
                            video_mode='native',source_description={'copyEligible':False})
        prefetch.begin(job,'1234567890123456',1)
        prefetch.before_work(job)
        source=prefetch.load_source('1234567890123456',1)
        prefetch.finish(job,'1234567890123456',1,source)
        self.assertTrue(prefetch.wait_idle(3))
        self.assertEqual(calls,[])
        self.assertEqual(downloads,[e['vid'] for e in episodes])
        state=prefetch.snapshot()
        self.assertEqual(state['downloadCompletedEpisodes'],[2,3,4])
        self.assertEqual(state['failedEpisodes'],[])
        self.assertEqual(state['state'],'idle')

    def test_native_source_and_start_bypass_busy_hls_gate(self):
        class Host:
            available = True
            def __init__(self): self.prepared=[]
            def prepare(self, job): self.prepared.append(job.id)
            def release(self, identifier): pass
        host=Host()
        calls=[]
        def gate(job):
            calls.append(job.id)
            raise AssertionError('The HLS queue is unavailable')
        jobs=HlsJobs(self.root,lambda *_:self.source,native=host,before_work=gate,
                     negotiation_seconds=2)
        self.addCleanup(lambda:[jobs.release(key) for key in list(jobs.jobs)])
        job=jobs.create('1234567890123456',2,negotiate_codec=True)
        deadline=time.monotonic()+1
        while job.source_description is None and time.monotonic()<deadline:time.sleep(.01)
        self.assertIsNotNone(job.source_description)
        job.video_mode='native';job.mode_selected.set()
        self.assertTrue(job.done.wait(1))
        self.assertFalse(job.failed)
        self.assertEqual(host.prepared,[job.id])
        self.assertEqual(calls,[])

    def test_hls_encoding_still_enters_gate_after_source_selection(self):
        calls=[]
        def gate(job):
            self.assertIsNotNone(job.source)
            self.assertEqual(job.video_mode,'h264')
            calls.append(job.id)
        jobs=HlsJobs(self.root,lambda *_:self.source,encoder=encode_hls,before_work=gate)
        self.addCleanup(lambda:[jobs.release(key) for key in list(jobs.jobs)])
        job=jobs.create('1234567890123456',2)
        self.assertTrue(job.done.wait(3))
        self.assertFalse(job.failed)
        self.assertEqual(calls,[job.id])

    def test_hardware_error_retries_software_once_and_preserves_controls(self):
        self.hardware_recovery()

    def test_eof_without_a_frame_cannot_publish_ended_and_retries_once(self):
        self.hardware_recovery(empty_eof=True)

    def hardware_recovery(self,empty_eof=False):
        # This fault cannot be reliably provoked on every physical GPU. The
        # production NativeSession recovery is exercised with a bounded driver.
        class Driver:
            def __init__(self): self.events=[]; self.holds=[]
            def mpv_initialize(self, _): return 0
            def mpv_wait_event(self, *args):
                return C.pointer(self.events.pop(0) if self.events else Event(0,0,0,None))
        driver=Driver()
        created=[]
        class Player:
            def __init__(self, dll):
                self.dll=dll; self.handle=1; self.options={}; self.commands=[]; self.loads=0; created.append(self)
            def check(self, _): pass
            def option(self, key,value): self.options[key]=value
            def command(self,*args):
                self.commands.append(args)
                if args[0]=='loadfile':
                    self.loads+=1
                    if not empty_eof:driver.events.append(Event(21,0,0,None))
                    if self.loads==1 and not empty_eof:
                        def error():
                            fields=(C.c_int*2)(4,-12); driver.holds.append(fields)
                            driver.events.append(Event(7,0,0,C.cast(fields,C.c_void_p).value))
                        threading.Timer(.15,error).start()
            def get(self,key):
                return {'hwdec-current':'d3d11va' if self.loads==1 else 'no','pause':'yes',
                        'current-vo':'gpu','video-out-params':'frame','audio-device':'auto',
                        'audio-exclusive':'no','eof-reached':'yes' if empty_eof else 'no'}.get(key)
            def number(self,key,default=0):
                return {'time-pos':12.5,'video-params/w':1920,'video-params/h':1080,'duration':87}.get(key,default)
            def close(self): self.handle=None
        user=SimpleNamespace(SetThreadDpiAwarenessContext=lambda *_:None,
            CreateWindowExW=lambda *_:1,IsWindow=lambda *_:True,PeekMessageW=lambda *_:False,
            DestroyWindow=lambda *_:None)
        host=SimpleNamespace(user=user,dll=driver,hardware=True)
        job=SimpleNamespace(start_seconds=0,source=self.source,duration=87,cancelled=threading.Event())
        session=NativeSession(host,job,1)
        session.forward_input=lambda _:True
        with patch('desktop_native.Mpv',Player):
            session.thread.start()
            session.submit({'rate':3,'paused':True,'volume':.4})
            until=time.monotonic()+2
            while not session.snapshot().get('softwareRetried') and time.monotonic()<until: time.sleep(.01)
            session.close()
        self.assertTrue(session.data['softwareRetried'])
        player=created[0]
        self.assertEqual(player.loads,2)
        if empty_eof:
            self.assertEqual(session.data['state'],'failed')
            self.assertFalse(session.data.get('outputReady'))
            return
        self.assertIn(('set','start',12.5),player.commands)
        self.assertIn(('set','speed',3),player.commands)
        self.assertIn(('set','volume',40.0),player.commands)
        self.assertEqual(player.commands.count(('set','hwdec','no')),1)


if __name__=='__main__': unittest.main()
