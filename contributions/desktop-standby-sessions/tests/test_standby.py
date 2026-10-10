"""Standby ownership and cold-source regressions against the real session owner."""
from pathlib import Path
import tempfile
import asyncio
import queue
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from desktop_hls_service import HlsJobs, make_router
from desktop_native import NativeHost
from desktop_prefetch import EpisodePrefetcher


class StandbyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def jobs(self):
        calls=[]
        jobs=HlsJobs(self.root,lambda *args:self.root/'cold.mp4',on_start=lambda *args:calls.append(args))
        # Keep source work deterministic while exercising create/ownership.
        jobs._run=lambda *args:None
        self.addCleanup(lambda:[jobs.release(k) for k in list(jobs.jobs)])
        return jobs,calls

    def test_standby_bound_to_immediate_next_and_single_parent(self):
        jobs,calls=self.jobs()
        parent=jobs.create('1234567890123456',1)
        child=jobs.create(parent.series_id,2,negotiate_codec=True,prewarm_parent=parent.id)
        self.assertEqual(len(calls),1,'prewarm must not reset foreground prefetch')
        for series,ep in [(parent.series_id,3),('1234567890123457',2)]:
            with self.assertRaises(HTTPException):
                jobs.create(series,ep,negotiate_codec=True,prewarm_parent=parent.id)
        with self.assertRaises(HTTPException):
            jobs.create(parent.series_id,2,negotiate_codec=True,prewarm_parent=parent.id)
        with self.assertRaises(HTTPException):
            jobs.create(parent.series_id,3,negotiate_codec=True,prewarm_parent=child.id)
        jobs.release(parent.id)
        self.assertTrue(child.cancelled.is_set())

    def test_promoted_standby_survives_old_parent_release(self):
        jobs,calls=self.jobs()
        parent=jobs.create('1234567890123456',1)
        child=jobs.create(parent.series_id,2,negotiate_codec=True,prewarm_parent=parent.id)
        jobs.activate(child)
        jobs.release(parent.id)
        self.assertFalse(child.cancelled.is_set())
        self.assertIsNone(child.prewarm_parent)

    def test_warm_encoding_uses_existing_gate_and_does_not_advance_generation(self):
        prefetch=EpisodePrefetcher(lambda _:None,lambda _:({},[]),self.root/'cache',encoder=lambda *args:None)
        self.addCleanup(prefetch.close)
        parent=SimpleNamespace(id='a'*32,cancelled=threading.Event(),failed=False)
        prefetch.begin(parent,'1234567890123456',1)
        prefetch.foreground.clear()
        warm=SimpleNamespace(id='b'*32,cancelled=threading.Event(),failed=False,prewarm_parent=parent.id)
        generation=prefetch.generation
        prefetch.before_work(warm)
        self.assertEqual(prefetch.busy,warm.id)
        prefetch.finish(warm,'1234567890123456',2,None)
        self.assertEqual(prefetch.generation,generation)
        self.assertEqual(prefetch.current['episode'],1)
        self.assertFalse(prefetch.foreground)
        self.assertIsNone(prefetch.busy)

    def test_native_control_keeps_parent_until_applied_activation(self):
        jobs,_=self.jobs()
        parent=jobs.create('1234567890123456',1)
        child=jobs.create(parent.series_id,2,negotiate_codec=True,prewarm_parent=parent.id)
        child.video_mode='native';child.ready.set()
        state={'visible':False,'outputReady':True,'revision':0}
        jobs.native=SimpleNamespace(available=True,snapshot=lambda _:state,
            control=lambda *_:9,release=lambda _:None)
        routes=make_router(jobs,lambda _:True).routes
        control=next(route.endpoint for route in routes if route.path.endswith('/control'))
        async def body():return {'visible':True,'paused':False,'muted':False}
        result=asyncio.run(control(child.id,SimpleNamespace(json=body)))
        self.assertEqual(result,{'revision':9})
        self.assertEqual(child.prewarm_parent,parent.id)
        activate=next(route.endpoint for route in routes if route.path.endswith('/activate'))
        for update in ({'visible':False,'outputReady':True,'revision':9},
                       {'visible':True,'outputReady':False,'revision':9},
                       {'visible':True,'outputReady':True,'revision':8}):
            state.update(update)
            with self.assertRaises(HTTPException):activate(child.id)
            self.assertEqual(child.prewarm_parent,parent.id)
        state.update(visible=True,outputReady=True,revision=9)
        self.assertEqual(activate(child.id),{'activated':True})
        jobs.release(parent.id)
        self.assertFalse(child.cancelled.is_set())

    def test_parent_cancel_before_native_ack_cancels_queued_child(self):
        jobs,_=self.jobs()
        parent=jobs.create('1234567890123456',1)
        child=jobs.create(parent.series_id,2,negotiate_codec=True,prewarm_parent=parent.id)
        child.video_mode='native';child.activation_revision=9
        jobs.native=SimpleNamespace(snapshot=lambda _:dict(visible=False,outputReady=True,revision=8),release=lambda _:None)
        with self.assertRaises(HTTPException):jobs.activate(child)
        jobs.release(parent.id)
        self.assertTrue(child.cancelled.is_set())

    def test_activation_cancel_does_not_clear_parent_download_queue(self):
        prefetch=EpisodePrefetcher(lambda _:None,lambda _:({},[]),self.root/'cache',encoder=lambda *_:None)
        self.addCleanup(prefetch.close)
        parent=SimpleNamespace(id='a'*32,cancelled=threading.Event(),failed=False)
        prefetch.begin(parent,'1234567890123456',1);prefetch.foreground.clear()
        child=SimpleNamespace(id='b'*32,cancelled=threading.Event(),failed=False,prewarm_parent=parent.id)
        prefetch.before_work(child)
        expected=[(prefetch.generation,9,'1234567890123456')]
        prefetch.download_pending=expected.copy()
        child.prewarm_parent=None;child.cancelled.set()
        prefetch.promote(child,'1234567890123456',2)
        prefetch.finish(child,'1234567890123456',2,None)
        self.assertEqual(prefetch.download_pending,expected)
        self.assertEqual(prefetch.current['episode'],1)
        self.assertIsNone(prefetch.busy)

    def test_child_submit_failure_rolls_back_previous_pause(self):
        host=object.__new__(NativeHost);host.guard=threading.RLock()
        parent_state={'paused':False,'revision':0};commands=[]
        def submit_parent(body):
            commands.append(body);parent_state.update(body,revision=parent_state['revision']+1)
            return parent_state['revision']
        def submit_child(body):raise queue.Full()
        parent=SimpleNamespace(stop=threading.Event(),snapshot=lambda:parent_state.copy(),submit=submit_parent)
        child=SimpleNamespace(stop=threading.Event(),snapshot=lambda:{'outputReady':True},
            submit=submit_child,job=SimpleNamespace(prewarm_parent='a'*32))
        host.sessions={'a'*32:parent,'b'*32:child}
        with self.assertRaises(queue.Full):host.control('b'*32,{'visible':True,'paused':False,'muted':False})
        self.assertEqual(commands,[{'paused':True},{'paused':False}])
        self.assertFalse(parent_state['paused'])

    def test_finishing_between_activation_and_promotion_keeps_old_metadata(self):
        source=self.root/'prepared.mp4';source.write_bytes(b'prepared')
        prefetch=EpisodePrefetcher(lambda _:source,lambda _:({},[]),self.root/'cache',encoder=lambda *_:None)
        self.addCleanup(prefetch.close)
        parent=SimpleNamespace(id='a'*32,cancelled=threading.Event(),failed=False)
        prefetch.begin(parent,'1234567890123456',1)
        prefetch.foreground.clear()
        warm=SimpleNamespace(id='b'*32,cancelled=threading.Event(),failed=False,prewarm_parent=parent.id)
        prefetch.before_work(warm)
        warm.prewarm_parent=None
        prefetch.finish(warm,'1234567890123456',2,source)
        self.assertEqual(prefetch.current['episode'],1)
        self.assertIsNone(prefetch.current_source)
        self.assertFalse(prefetch.current_complete)
        self.assertFalse(prefetch.foreground)

    def test_native_standby_does_not_close_foreground_and_refuses_sound(self):
        class Session:
            def __init__(self,host,job,parent):
                self.job=job;self.stop=threading.Event();self.closed=False
                self.data={'outputReady':False,'paused':True,'revision':0}
                self.thread=SimpleNamespace(start=lambda:None)
            def close(self):self.closed=True;self.stop.set()
            def snapshot(self):return self.data
            def submit(self,body):self.data.update(body,revision=self.data['revision']+1);return self.data['revision']
        host=object.__new__(NativeHost);host.available=True;host.guard=threading.RLock();host.sessions={}
        host.parent_window=lambda:1
        parent=SimpleNamespace(id='a'*32,cancelled=threading.Event(),prewarm_parent=None)
        child=SimpleNamespace(id='b'*32,cancelled=threading.Event(),prewarm_parent=parent.id)
        with patch('desktop_native.NativeSession',Session):
            host.prepare(parent);old=host.sessions[parent.id]
            host.prepare(child);warm=host.sessions[child.id]
            self.assertFalse(old.closed)
            self.assertEqual(len(host.sessions),2)
            for body in ({'paused':False},{'muted':False},{'visible':True}):
                with self.assertRaises(ValueError):host.control(child.id,body)
            warm.data['outputReady']=True
            host.control(child.id,{'visible':True,'paused':False,'muted':False,'rate':3})
            self.assertTrue(old.data['paused'])
            self.assertFalse(warm.data['paused'])
            self.assertEqual(warm.data['rate'],3)
            host.release(parent.id);host.release(child.id)
            self.assertFalse(host.sessions)

    def test_promotion_reuses_stream_identity_without_opening_another_source(self):
        source=self.root/'existing.mp4';source.write_bytes(b'prepared')
        def unexpected(*_):raise AssertionError('must reuse the already playing source')
        prefetch=EpisodePrefetcher(unexpected,lambda _:({},[{'index':2,'vid':'1234567890123456'}]),
                                  self.root/'cache',encoder=unexpected)
        self.addCleanup(prefetch.close)
        job=SimpleNamespace(id='a'*32,source=source,cancelled=threading.Event(),failed=False,video_mode='native')
        prefetch.promote(job,'1234567890123456',2)
        self.assertIs(prefetch.current_source,source)
        self.assertEqual(prefetch.current['episode'],2)
        self.assertTrue(prefetch.snapshot()['currentSourceComplete'])
        self.assertFalse(prefetch.foreground)

    def test_hls_promotion_keeps_encoding_slot_until_worker_finishes(self):
        source=self.root/'existing.mp4';source.write_bytes(b'prepared')
        prefetch=EpisodePrefetcher(lambda _:source,lambda _:({},[{'index':2,'vid':'1234567890123456'}]),
                                  self.root/'cache',encoder=lambda *_:None)
        self.addCleanup(prefetch.close)
        prefetch.cache.contains=lambda *_,**kw:True
        job=SimpleNamespace(id='a'*32,source=source,cancelled=threading.Event(),failed=False,
                            video_mode='h264',prewarm_parent='b'*32)
        prefetch.before_work(job)
        job.prewarm_parent=None
        prefetch.promote(job,'1234567890123456',2)
        self.assertEqual(prefetch.busy,job.id)
        self.assertIn(job.id,prefetch.foreground)
        self.assertFalse(prefetch.pending)
        prefetch.finish(job,'1234567890123456',2,source)
        self.assertIsNone(prefetch.busy)
        self.assertFalse(prefetch.foreground)
        self.assertTrue(prefetch.current_complete)
        # Completion may also precede activation (a cache hit or fast encoder).
        prefetch.promote(job,'1234567890123456',2)
        self.assertFalse(prefetch.foreground)
        self.assertTrue(prefetch.current_complete)

    def test_promotion_metadata_failure_releases_finished_job(self):
        def unavailable(_):raise OSError('owned metadata failure')
        prefetch=EpisodePrefetcher(lambda _:None,unavailable,self.root/'cache',encoder=lambda *_:None)
        self.addCleanup(prefetch.close)
        prefetch._report=lambda:self.assertFalse(prefetch.condition._is_owned(),
            'diagnostic report lock must not be acquired while holding scheduler condition')
        job=SimpleNamespace(id='a'*32,source=self.root/'ready.mp4',cancelled=threading.Event(),
                            failed=False,video_mode='native')
        prefetch.promote(job,'1234567890123456',2)
        self.assertFalse(prefetch.foreground)
        self.assertFalse(prefetch.pending)


if __name__=='__main__':unittest.main()
