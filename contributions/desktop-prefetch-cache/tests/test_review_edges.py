"""Regression cases from asynchronous upstream review; no real media or account."""
from pathlib import Path
import tempfile,threading,time,unittest,uuid
from unittest.mock import patch
from desktop_hls import EncodingCancelled
from desktop_prefetch import EpisodePrefetcher
from desktop_playable_cache import PlayableEpisodeCache
from job_fixture import Job
from test_prefetch import complete_output,encoder,PROFILE_FILES

class ReviewEdges(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.mp4';self.source.write_bytes(b'fixture')
        self.output=self.root/'output';complete_output(self.output)
    def cache(self,root=None):
        return PlayableEpisodeCache(root or self.root/'cache',encoder=encoder,profile_files=PROFILE_FILES)
    def test_single_endlist_is_valid_anywhere_but_trailing_extinf_is_not_complete(self):
        cache=self.cache();playlist=self.output/'index.m3u8'
        body=playlist.read_text(encoding='utf-8').replace('#EXT-X-ENDLIST\n','')
        for anchor in ('#EXT-X-MAP:', '#EXTINF:', 'seg000000.m4s'):
            with self.subTest(anchor=anchor):
                playlist.write_text(body.replace(anchor,'#EXT-X-ENDLIST\n'+anchor,1),encoding='utf-8')
                cache.store(self.source,self.output);self.assertTrue(cache.contains(self.source))
        playlist.write_text(body+'#EXT-X-ENDLIST\n#EXTINF:2,\n',encoding='utf-8')
        with self.assertRaises(ValueError):cache.store(self.source,self.output)

    def test_inaccessible_optional_cache_does_not_break_construction(self):
        blocked=self.root/'not-directory';blocked.write_bytes(b'file')
        cache=self.cache(blocked/'cache')
        self.assertFalse(cache.contains(self.source))
        with patch('desktop_playable_cache.plain',side_effect=PermissionError('denied')):
            disabled=self.cache(self.root/'denied')
        self.assertFalse(disabled.contains(self.source))
    def test_bad_owner_bytes_are_unowned_not_a_scan_failure(self):
        cache=self.cache();unknown=cache.root/('f'*64);unknown.mkdir()
        (unknown/'owner.marker').write_bytes(b'\xff');(unknown/'data').write_bytes(b'unknown')
        cache.store(self.source,self.output)
        self.assertTrue(cache.contains(self.source));self.assertTrue((unknown/'data').exists())
    def test_cancelled_store_does_not_reserve_or_evict(self):
        cache=self.cache()
        with patch.object(cache,'_reserve',wraps=cache._reserve) as reserve:
            with self.assertRaises(EncodingCancelled):cache.store(self.source,self.output,cancelled=lambda:True)
            reserve.assert_not_called()
    def test_unavailable_store_does_not_read_source_or_media(self):
        cache=self.cache();cache.available=False
        with patch.object(cache,'_identity',side_effect=AssertionError('unneeded hash')):
            self.assertIsNone(cache.store(self.source,self.output))
    def test_impossible_reservation_preserves_existing_owned_cache(self):
        cache=self.cache();target=cache.store(self.source,self.output)
        before={p.name:p.read_bytes() for p in target.iterdir()}
        for needed in (cache.quota_bytes+1, cache.quota_bytes):
            with self.subTest(needed=needed):
                unknown=cache.root/('e'*64)
                unknown.mkdir(exist_ok=True);(unknown/'owner.marker').write_bytes(b'unknown')
                with self.assertRaises(OSError):cache._reserve(needed)
                self.assertEqual(before,{p.name:p.read_bytes() for p in target.iterdir()})
    def test_seek_window_forwards_explicit_copy_mode(self):
        cache=self.cache()
        with patch.object(cache,'encoder') as encode:
            cache.encode(self.source,self.root/'seek',start_seconds=1,video_mode='copy')
        self.assertEqual(encode.call_args.kwargs['video_mode'],'copy')
    def test_source_and_artifact_hashing_can_be_cancelled_mid_read(self):
        cache=self.cache()
        self.source.write_bytes(b'x'*(3*1024*1024))
        (self.output/'seg000000.m4s').write_bytes(b'x'*(3*1024*1024))
        stored=cache.store(self.source,self.output)
        class SlowRead:
            def __init__(self, stream, stopped):self.stream,self.stopped=stream,stopped
            def __enter__(self):return self
            def __exit__(self,*a):self.stream.close()
            def read(self,size):
                value=self.stream.read(size);self.stopped.set();return value
        original=Path.open
        for cancelled_path in (self.source,stored/'seg000000.m4s'):
            for operation in ('contains','restore'):
                stopped=threading.Event()
                def open_file(path,*a,**kw):
                    stream=original(path,*a,**kw)
                    return SlowRead(stream,stopped) if path==cancelled_path and a and a[0]=='rb' else stream
                with patch.object(Path,'open',open_file):
                    with self.assertRaises(EncodingCancelled):
                        if operation=='contains':cache.contains(self.source,cancelled=stopped.is_set)
                        else:cache.restore(self.source,self.root/'restored-cancelled',stopped.is_set)
                self.assertFalse((self.root/'restored-cancelled').exists())
    def test_background_validation_cancels_and_releases_scheduler_slot_on_switch(self):
        future=self.root/'future.mp4';future.write_bytes(b'future')
        episodes=[{'index':n,'vid':str(10000000+n)} for n in (1,2)]
        value=EpisodePrefetcher(lambda vid:self.source if vid=='10000001' else future,
            lambda _:({},episodes),self.root/'cache',encoder=encoder,profile_files=PROFILE_FILES)
        self.addCleanup(value.close)
        job=Job(uuid.uuid4().hex,self.root/'current');value.begin(job,'series',1)
        source=value.load_source('series',1);value.before_work(job)
        value.cache.encode(source,job.directory)
        entered,release=threading.Event(),threading.Event();original=value.cache._digest
        def digest(path,cancelled=lambda:False):
            if path==future:entered.set();release.wait(2)
            return original(path,cancelled)
        with patch.object(value.cache,'_digest',side_effect=digest):
            value.finish(job,'series',1,source);self.assertTrue(entered.wait(1))
            new=Job(uuid.uuid4().hex,self.root/'next');value.begin(new,'series',2);release.set()
            started=time.monotonic();value.before_work(new)
            self.assertLess(time.monotonic()-started,.5)
        new.failed=True;value.finish(new,'series',2,None)
    def test_lru_touch_failure_preserves_a_valid_hit(self):
        cache=self.cache();cache.store(self.source,self.output);target=self.root/'restored'
        with patch('desktop_playable_cache.os.utime',side_effect=PermissionError('read only')):
            self.assertTrue(cache.restore(self.source,target))
        self.assertTrue((target/'complete.marker').is_file())
    def test_finish_does_not_hold_scheduler_lock_during_cache_io(self):
        value=EpisodePrefetcher(lambda _:self.source,lambda _:({},[{'index':1,'vid':'10000001'}]),self.root/'cache',encoder=encoder,profile_files=PROFILE_FILES)
        self.addCleanup(value.close)
        job=Job(uuid.uuid4().hex,self.root/'session');value.begin(job,'series',1);source=value.load_source('series',1)
        entered,release,switched=threading.Event(),threading.Event(),threading.Event()
        def contains(*a,**kw):entered.set();release.wait(2);return False
        def switch():value.begin(Job(uuid.uuid4().hex,self.root/'next'),'series',2);switched.set()
        with patch.object(value.cache,'contains',side_effect=contains):
            finish=threading.Thread(target=lambda:value.finish(job,'series',1,source));finish.start()
            self.assertTrue(entered.wait(1));change=threading.Thread(target=switch);change.start()
            responsive=switched.wait(.4);release.set();finish.join(2);change.join(2)
        self.assertTrue(responsive,'begin must not wait for full-source/full-cache hashing')
        self.assertFalse(value.pending,'old completion must not publish into the new generation')

    def test_native_progressive_current_downloads_three_originals_without_encoding(self):
        source=object();downloads=[];encodes=[]
        episodes=[{'index':n,'vid':str(10000000+n)} for n in range(1,5)]
        def download(vid):downloads.append(int(vid)-10000000);return self.source
        value=EpisodePrefetcher(lambda _:source,lambda _:({},episodes),self.root/'cache',encoder=lambda *a,**k:encodes.append(a),profile_files=PROFILE_FILES,download_loader=download,source_status=lambda _:dict(kind='progressive',complete=False))
        self.addCleanup(value.close)
        job=Job(uuid.uuid4().hex,self.root/'session');job.video_mode='native'
        value.begin(job,'series',1);current=value.load_source('series',1);value.finish(job,'series',1,current)
        self.assertTrue(value.wait_idle(2));self.assertEqual(downloads,[2,3,4]);self.assertFalse(encodes)
        self.assertEqual(value.snapshot()['cacheKind'],'original-media');self.assertFalse(value.snapshot()['currentSourceComplete'])
    def test_blocked_stale_source_loading_does_not_reserve_encoder(self):
        entered,release=threading.Event(),threading.Event()
        episodes=[{'index':n,'vid':str(10000000+n)} for n in (1,2)]
        def load(vid):
            if vid=='10000001':entered.set();release.wait(2)
            return self.source
        value=EpisodePrefetcher(load,lambda _:({},episodes),self.root/'cache',encoder=encoder,profile_files=PROFILE_FILES,ahead=0)
        self.addCleanup(value.close)
        old=Job(uuid.uuid4().hex,self.root/'old');value.begin(old,'series',1)
        loading=threading.Thread(target=lambda:value.load_source('series',1));loading.start();self.assertTrue(entered.wait(1))
        new=Job(uuid.uuid4().hex,self.root/'new');value.begin(new,'series',2)
        try:
            value.before_work(new);self.assertEqual(value.busy,new.id)
        finally:release.set();loading.join(2)
        old.cancelled.set();value.finish(old,'series',1,None);new.failed=True;value.finish(new,'series',2,None)

if __name__=='__main__':unittest.main()
