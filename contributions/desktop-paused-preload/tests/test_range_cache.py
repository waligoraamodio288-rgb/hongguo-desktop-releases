from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile,threading,unittest
from unittest.mock import patch
from desktop_range_cache import RangeDiskCache,preload
from desktop_stream import RangeReader


class RangeCacheTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'cache'

    def test_fast_parallel_writes_reserve_exact_budget_and_do_not_overshoot(self):
        cache=RangeDiskCache(self.path,65536*4+3,65536*100);self.addCleanup(cache.close)
        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(lambda i:cache.store(i,b'x'*65536,lambda:False),range(100)))
        self.assertEqual(cache.snapshot()['cacheFileBytes'],65536*4)
        self.assertEqual(self.path.stat().st_size,65536*4)
        self.assertTrue(cache.snapshot()['preloadLimited'])
        self.assertFalse(cache.snapshot()['cacheComplete'])

    def test_cancel_close_and_duplicate_blocks_never_append_payload(self):
        cache=RangeDiskCache(self.path,100,100)
        cache.store(0,b'hello',lambda:True);self.assertEqual(self.path.stat().st_size,0)
        cache.store(0,b'hello',lambda:False);cache.store(0,b'bad',lambda:False)
        self.assertEqual(cache.read(0),b'hello');self.assertEqual(cache.snapshot()['cacheFileBytes'],5)
        cache.close();cache.store(1,b'x',lambda:False)
        self.assertIsNone(cache.read(0));self.assertEqual(self.path.stat().st_size,5)

    def test_fast_background_fill_replays_seek_without_network_and_stops_at_cap(self):
        class Source:
            size=65536*20;block_size=65536
            def __init__(self):self.calls=0
            def block(self,index,cancelled):self.calls+=1;return bytes([index])*65536
            def reader(self,stopped,cache=None):return RangeReader(self,stopped,cache=cache)
        for budget in (65536*20,65536*4):
            self.path.unlink(missing_ok=True);source=Source()
            cache=RangeDiskCache(self.path,budget,source.size)
            preload(source,cache,lambda:False)
            self.assertEqual(source.calls,budget//65536)
            with source.reader(lambda:False,cache=cache) as reader:
                reader.seek(65536*2+10);self.assertEqual(reader.read(20),bytes([2])*20)
            self.assertEqual(source.calls,budget//65536)
            self.assertEqual(cache.snapshot()['cacheComplete'],budget==source.size)
            self.assertLessEqual(self.path.stat().st_size,budget)
            cache.close()

    def test_optional_disk_failure_leaves_source_readable_and_incomplete(self):
        cache=RangeDiskCache(self.path,100,100);self.addCleanup(cache.close)
        with patch.object(cache.file,'write',side_effect=OSError('full')):
            cache.store(0,b'abc',lambda:False)
        self.assertTrue(cache.snapshot()['preloadLimited'])
        self.assertFalse(cache.snapshot()['cacheComplete']);self.assertIsNone(cache.read(0))
