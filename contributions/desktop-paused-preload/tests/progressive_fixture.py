"""Owned, rate-limited CENC fixture. Only a public test key is used."""
import re
import threading
import time
from pathlib import Path

KEY = "11" * 16


class ProgressiveFixture:
    def __init__(self, app, work, sources):
        import av
        from fastapi import Request
        from fastapi.responses import Response, StreamingResponse
        self.files, self.sources, self.rows = {}, [], []
        self.delay, self.fail = .12, False
        for number, source in enumerate(sources):
            target = Path(work) / ("owned-cenc-" + str(number) + ".mp4")
            with av.open(str(source)) as media, av.open(str(target), "w", format="mp4", options={
                    "movflags": "+faststart", "encryption_scheme": "cenc-aes-ctr",
                    "encryption_key": KEY, "encryption_kid": "22" * 16}) as output:
                streams = {s.index: output.add_stream_from_template(s) for s in media.streams if s.type in ("video", "audio")}
                for packet in media.demux():
                    if packet.dts is not None and packet.stream.index in streams:
                        packet.stream = streams[packet.stream.index]
                        output.mux(packet)
            self.files[number] = target

        @app.get('/owned-cenc/{number}')
        def serve(number: int, request: Request):
            if self.fail:
                return Response(status_code=503)
            data = self.files[number]
            match = re.fullmatch(r'bytes=(\d+)-(\d+)', request.headers.get('range', ''))
            if not match:
                return Response(status_code=416)
            start, end = map(int, match.groups())
            end = min(end, data.stat().st_size - 1)
            def body():
                time.sleep(self.delay)
                with data.open('rb') as stream:
                    stream.seek(start)
                    yield stream.read(end - start + 1)
                self.rows.append({'source': number, 'start': start, 'bytes': end - start + 1})
            return StreamingResponse(body(), status_code=206, headers={
                'Content-Range': f'bytes {start}-{end}/{data.stat().st_size}',
                'Content-Length': str(end - start + 1), 'ETag': '"owned-cenc-v1"'})

    def source(self, origin, number):
        import requests
        from desktop_stream import ProgressiveSource
        value = ProgressiveSource(origin + '/owned-cenc/' + str(number), request=requests.request,
                                  identity='owned-' + str(number), key=KEY)
        self.sources.append(value)
        return value
