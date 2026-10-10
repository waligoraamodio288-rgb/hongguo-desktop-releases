"""Real Opus input verifies the fallback, including audio flushing and seeking."""
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import av
from desktop_hls import encode_hls, EncodingCancelled
from desktop_hls_budget import EncodingBudgetExceeded
from desktop_codec import aac_lc


class AudioFallbackTests(unittest.TestCase):
    def test_only_qualified_aac_lc_can_be_copied(self):
        self.assertTrue(aac_lc(SimpleNamespace(name='aac',extradata=b'\x12\x10',profile='LC')))
        for extra,profile in ((b'',None),(b'\x12',None),(b'\x2b\x92','HE-AAC'),
                              (b'\xeb\x92','HE-AACv2'),(b'\x12\x10','HE-AAC')):
            self.assertFalse(aac_lc(SimpleNamespace(name='aac',extradata=extra,profile=profile)))

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.source=self.root/'opus.mkv'
        with av.open(str(self.source),'w') as output:
            video=output.add_stream('libx264',rate=10)
            video.width=video.height=64;video.pix_fmt='yuv420p'
            audio=output.add_stream('libopus',rate=48000);audio.layout='stereo'
            for n in range(30):
                frame=av.VideoFrame(64,64,'yuv420p')
                for plane in frame.planes:plane.update(bytes(plane.buffer_size))
                frame.pts=n;frame.time_base=Fraction(1,10)
                for packet in video.encode(frame):output.mux(packet)
                for block in range(5):
                    frame=av.AudioFrame(format='flt',layout='stereo',samples=960)
                    frame.sample_rate=48000;frame.time_base=Fraction(1,48000)
                    frame.pts=(n*5+block)*960
                    for plane in frame.planes:plane.update(bytes(plane.buffer_size))
                    for packet in audio.encode(frame):output.mux(packet)
            for stream in (video,audio):
                for packet in stream.encode(None):output.mux(packet)

    def test_real_opus_fallback_decodes_video_and_aac_with_common_seek_origin(self):
        for start in (0,1.05):
            target=self.root/str(start);origins=[]
            encode_hls(self.source,target,start_seconds=start,on_window=lambda a,b:origins.append(a))
            with av.open(str(target/'index.m3u8')) as media:
                self.assertEqual(media.streams.video[0].codec_context.name,'h264')
                self.assertEqual(media.streams.audio[0].codec_context.name,'aac')
                frames=list(media.decode(video=0))
            with av.open(str(target/'index.m3u8')) as media:
                sound=list(media.decode(audio=0))
            self.assertTrue(frames);self.assertTrue(sound)
            self.assertLess(abs(frames[0].time-sound[0].time),.05)
            self.assertLess(abs(frames[-1].time-sound[-1].time),.15)
            self.assertGreater(sum(f.samples for f in sound),48000)
            self.assertTrue((target/'complete.marker').exists())
            if start:self.assertGreaterEqual(origins[0],start)

    def test_non_aac_budget_and_cancellation_do_not_commit(self):
        with self.assertRaises(EncodingBudgetExceeded):
            encode_hls(self.source,self.root/'budget',max_output_bytes=1)
        counter=[0]
        def cancel():counter[0]+=1;return counter[0]>20
        with self.assertRaises(EncodingCancelled):
            encode_hls(self.source,self.root/'cancel',cancelled=cancel)
        for name in ('budget','cancel'):
            self.assertFalse((self.root/name/'complete.marker').exists())

    def test_rejected_aac_qualification_uses_real_aac_encoder(self):
        first=self.root/'first';encode_hls(self.source,first)
        # Force the unsupported-profile decision on a decodable AAC fixture;
        # actual HE-AAC encoder availability is not assumed in the test host.
        with patch('desktop_hls.aac_lc',return_value=False):
            target=self.root/'recoded';encode_hls(first/'index.m3u8',target)
        with av.open(str(target/'index.m3u8')) as media:
            self.assertEqual(media.streams.audio[0].codec_context.profile,'LC')
            self.assertTrue(list(media.decode(audio=0)))
