"""Authenticated desktop HLS sessions. No upstream credentials or protocol code.

The Rust parent owns the unique work directory and removes it AFTER killing its
backend job. Sessions additionally release their own output on player close/expiry.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re
import math
import shutil
import threading
import time
import uuid
import queue
from desktop_codec import describe_streams
from desktop_stream import ProgressiveSource, SourceReadError, open_media, source_progress

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import FileResponse, Response, StreamingResponse, JSONResponse
from desktop_hls import encode_hls, EncodingCancelled
from desktop_hls_budget import EncodingBudgetExceeded


class InvalidStartPosition(ValueError):
    """A valid numeric request lies outside this source's known timeline."""


@dataclass
class Job:
    id: str
    directory: Path
    cancelled: threading.Event = field(default_factory=threading.Event)
    ready: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    failed: bool = False
    failure_code: str | None = None
    duration: float | None = None
    touched: float = field(default_factory=time.monotonic)
    start_seconds: float = 0.0
    window_origin: float | None = 0.0
    source: Path | ProgressiveSource | None = None
    stream_url: str | None = None
    stream_key: str | None = field(default=None, repr=False)
    negotiate_codec: bool = False
    source_description: dict | None = None
    video_mode: str = "h264"
    mode_selected: threading.Event = field(default_factory=threading.Event)


class HlsJobs:
    def __init__(self, root, source_loader, *, encoder=encode_hls, max_jobs=4, max_workers=2, idle_seconds=300,
                 on_start=None, before_work=None, on_finish=None, full_cache_ready=None, negotiation_seconds=12, native=None):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir() or self.root.is_symlink():
            raise ValueError("Desktop work directory is unavailable")
        self.source_loader, self.encoder = source_loader, encoder
        self.max_jobs, self.max_workers, self.idle_seconds = max_jobs, max_workers, idle_seconds
        self.jobs = {}
        self.guard = threading.RLock()
        self.on_start, self.before_work, self.on_finish = on_start, before_work, on_finish
        self.full_cache_ready = full_cache_ready
        self.negotiation_seconds = negotiation_seconds
        self.native = native
        self.encoder_slots = threading.BoundedSemaphore(max_workers)
        self.closed = threading.Event()
        self.reaper = None

    def _reap(self):
        while not self.closed.wait(min(1.0, max(.05, self.idle_seconds / 4))):
            with self.guard:
                expired = [job.id for job in self.jobs.values()
                           if job.cancelled.is_set() or time.monotonic() - job.touched > self.idle_seconds]
            for identifier in expired:
                # Recheck under the lock: a status poll may have renewed it.
                with self.guard:
                    job = self.jobs.get(identifier)
                    if job and (job.cancelled.is_set() or time.monotonic() - job.touched > self.idle_seconds):
                        self.release(identifier)
            with self.guard:
                if not self.jobs:
                    self.reaper = None
                    return

    def close(self):
        self.closed.set()
        with self.guard:
            remaining = list(self.jobs.values())
        for job in remaining:
            self.release(job.id)
        reaper = self.reaper
        if reaper and reaper is not threading.current_thread():
            reaper.join(5)

    def _remove_output(self, job):
        # Only our generated UUID child; never a source file or a caller's path.
        target = job.directory
        if target.parent != self.root or target.name != job.id or not re.fullmatch(r"[0-9a-f]{32}", job.id):
            raise ValueError("Unsafe session output")
        if target.is_symlink() or (target.exists() and target.resolve().parent != self.root):
            raise ValueError("Session output escaped work directory")
        if target.exists():
            shutil.rmtree(target)

    def _expire(self):
        for job in list(self.jobs.values()):
            if time.monotonic() - job.touched > self.idle_seconds:
                self.release(job.id)

    def create(self, series_id, episode, *, start_seconds=0, negotiate_codec=False):
        if not re.fullmatch(r"[0-9]{8,24}", series_id) or not 1 <= episode <= 100000:
            raise HTTPException(400, "Invalid episode identity")
        if (not isinstance(start_seconds, (int, float)) or isinstance(start_seconds, bool)
                or not math.isfinite(start_seconds) or not 0 <= start_seconds <= 86400):
            raise HTTPException(400, "Invalid desktop start position")
        with self.guard:
            self._expire()
            if self.closed.is_set():
                raise HTTPException(503, "Desktop sessions are closed")
            if len(self.jobs) >= self.max_jobs:
                raise HTTPException(503, "Desktop session limit reached; retry shortly")
            identifier = uuid.uuid4().hex
            job = Job(identifier, self.root / identifier,
                      start_seconds=float(start_seconds), window_origin=None if start_seconds else 0.0,
                      negotiate_codec=negotiate_codec)
            self.jobs[identifier] = job
            try:
                if self.reaper is None:
                    self.reaper = threading.Thread(target=self._reap, daemon=True)
                    self.reaper.start()
                if self.on_start:
                    self.on_start(job, series_id, episode)
                threading.Thread(target=self._run, args=(job, series_id, episode), daemon=True).start()
            except Exception:
                job.failed = True
                if self.on_finish:
                    try:
                        self.on_finish(job, series_id, episode, None)
                    except Exception:
                        pass
                self.jobs.pop(identifier, None)
                raise
            return job

    def _run(self, job, series_id, episode):
        source = None
        encoder_acquired = False
        try:
            source = self.source_loader(series_id, episode)
            job.source = source if isinstance(source, ProgressiveSource) else Path(source)
            if job.cancelled.is_set():
                raise EncodingCancelled()
            import av
            with open_media(source, cancelled=job.cancelled.is_set) as media:
                if media.duration and media.duration > 0:
                    job.duration = media.duration / av.time_base
                if job.negotiate_codec:
                    try:
                        job.source_description = describe_streams(media)
                    except (ValueError, TypeError, AttributeError, OverflowError):
                        job.source_description = {"copyEligible": False}
            if job.negotiate_codec:
                job.mode_selected.wait(self.negotiation_seconds)
                with self.guard:
                    job.mode_selected.set()
                if job.cancelled.is_set():
                    raise EncodingCancelled()
            if job.start_seconds and (job.duration is None or job.start_seconds >= job.duration):
                raise InvalidStartPosition()
            if job.video_mode == "native":
                self.native.prepare(job)
                job.window_origin = 0.0
                job.ready.set()
                return
            # This gate owns encoding, not source downloads or native playback.
            # A cached native episode must not wait for an HLS worker to unwind.
            while not job.cancelled.is_set():
                if self.encoder_slots.acquire(timeout=.1):
                    encoder_acquired = True
                    break
            if job.cancelled.is_set():
                raise EncodingCancelled()
            if self.before_work:
                self.before_work(job)
            if job.start_seconds:
                def window(origin, duration):
                    with self.guard:
                        if job.cancelled.is_set():
                            raise EncodingCancelled()
                        if (job.window_origin is not None
                                or not isinstance(origin, (int, float)) or isinstance(origin, bool)
                                or not isinstance(duration, (int, float)) or isinstance(duration, bool)
                                or not math.isfinite(origin) or not math.isfinite(duration)
                                or not job.start_seconds <= origin < duration <= 86400
                                or job.duration is None or abs(duration - job.duration) > 0.001):
                            raise ValueError("Invalid desktop window metadata")
                        job.window_origin = float(origin)

                def ready():
                    with self.guard:
                        if job.cancelled.is_set():
                            raise EncodingCancelled()
                        if job.window_origin is None:
                            raise ValueError("Desktop window origin is unavailable")
                        job.ready.set()
                self.encoder(source, job.directory, ready, cancelled=job.cancelled.is_set,
                             start_seconds=job.start_seconds, on_window=window)
            else:
                # Preserve the original zero-start encoder contract, including
                # callers that inject an older encoder for ordinary playback.
                extra = {"video_mode": "copy"} if job.video_mode == "copy" else {}
                self.encoder(source, job.directory, job.ready.set, cancelled=job.cancelled.is_set, **extra)
            if job.start_seconds and job.window_origin is None:
                raise ValueError("Desktop window completion is unavailable")
            if not (job.directory / "complete.marker").is_file():
                raise ValueError("Encoder completion was not verified")
        except InvalidStartPosition:
            job.failed = True
            job.failure_code = "start-position"
        except EncodingCancelled:
            job.failed = True
            job.failure_code = "cancelled"
        except EncodingBudgetExceeded:
            job.failed = True
            job.failure_code = "output-budget"
        except SourceReadError:
            job.failed = True
            job.failure_code = "source-read"
        except Exception:
            # Fixed categories only; never expose provider exception text.
            job.failed = True
            job.failure_code = "processing"
        finally:
            if self.on_finish:
                try:
                    self.on_finish(job, series_id, episode, source)
                except Exception:
                    pass  # Optional prefetch bookkeeping is not a media failure.
            if encoder_acquired:
                self.encoder_slots.release()
            with self.guard:
                job.done.set()
                job.ready.set()
                if job.cancelled.is_set():
                    if self.native and self.native.release(job.id) is False:
                        return  # Native owner still holds its window/source.
                    try:
                        self._remove_output(job)
                    except OSError:
                        # Keep it registered for a later cleanup attempt/quota.
                        return
                    self.jobs.pop(job.id, None)

    def get(self, identifier):
        with self.guard:
            job = self.jobs.get(identifier)
            if not job or job.cancelled.is_set():
                raise HTTPException(404, "Desktop session is unavailable")
            job.touched = time.monotonic()
            return job

    def release(self, identifier):
        with self.guard:
            job = self.jobs.get(identifier)
            if not job:
                return
            job.cancelled.set()
            if self.native:
                if self.native.release(identifier) is False:
                    return False  # Retain ownership/output until native teardown finishes.
            job.mode_selected.set()
            job.ready.set()
            if job.done.is_set():
                try:
                    self._remove_output(job)
                except OSError:
                    return
                self.jobs.pop(identifier, None)

    def playlist(self, identifier, wait_seconds=90):
        job = self.get(identifier)
        if not job.ready.wait(wait_seconds):
            raise HTTPException(504, "Desktop media preparation timed out")
        if job.failed or job.cancelled.is_set():
            raise HTTPException(503, "Desktop media preparation failed")
        try:
            text = (job.directory / "index.m3u8").read_text(encoding="utf-8")
        except OSError:
            raise HTTPException(503, "Desktop playlist is not ready")
        # Encoder close can emit ENDLIST even during unwinding. Never expose it
        # until the worker has successfully committed its completion marker.
        complete = job.done.is_set() and not job.failed and (job.directory / "complete.marker").is_file()
        if not complete:
            text = text.replace("#EXT-X-ENDLIST", "")
        # Prefix fragments because the route itself has a file path component.
        # Only fixed local basenames are emitted; tokens are attached in headers.
        for line in text.splitlines():
            if line and not line.startswith("#") and not re.fullmatch(r"seg[0-9]{6}\.m4s", line):
                raise HTTPException(500, "Invalid desktop playlist")
            if line.startswith("#EXT-X-MAP:") and line != '#EXT-X-MAP:URI="init.mp4"':
                raise HTTPException(500, "Invalid desktop init fragment")
        return text

    def playable_range(self, job):
        """Disk-ready media coverage, independent of WebView's bounded buffer."""
        duration, origin = job.duration, job.window_origin
        if (job.failed or job.cancelled.is_set() or duration is None or origin is None
                or not math.isfinite(duration) or duration <= 0):
            return [0, 0]
        if job.video_mode == "native":
            if isinstance(job.source, ProgressiveSource):
                value = self.native.snapshot(job.id)
                return [max(0, value.get("bufferStart", 0)), min(duration, value.get("bufferEnd", 0))]
            return [0, duration]
        if job.start_seconds and job.source and self.full_cache_ready:
            try:
                if self.full_cache_ready(job.source):
                    return [0, duration]
            except (OSError, ValueError):
                pass  # Optional disk cache must not interrupt status/playback.
        try:
            init = job.directory / "init.mp4"
            if not init.is_file() or init.is_symlink() or init.stat().st_size == 0:
                return [0, 0]
            lines = (job.directory / "index.m3u8").read_text(encoding="utf-8").splitlines()
            available, pending, count, incomplete = 0.0, None, 0, False
            for line in lines:
                if line.startswith("#EXTINF:"):
                    if pending is not None:
                        incomplete = True
                        break
                    pending = float(line[8:].split(",", 1)[0])
                    if not math.isfinite(pending) or pending <= 0:
                        return [0, 0]
                elif line and not line.startswith("#"):
                    if pending is None or not re.fullmatch(r"seg[0-9]{6}\.m4s", line):
                        return [0, 0]
                    fragment = job.directory / line
                    if not fragment.is_file() or fragment.is_symlink() or fragment.stat().st_size == 0:
                        incomplete = True
                        break
                    available += pending
                    pending = None
                    count += 1
            if not count:
                return [0, 0]
            end = min(duration, origin + available)
            if (job.done.is_set() and not incomplete and pending is None
                    and "#EXT-X-ENDLIST" in lines
                    and (job.directory / "complete.marker").is_file()):
                end = duration  # Include final audio/video duration rounding.
            if job.cancelled.is_set() or job.failed:
                return [0, 0]
            return [origin, end]
        except (OSError, ValueError):
            return [0, 0]  # A partial playlist write is not ready media.


DESKTOP_ORIGINS = ["http://tauri.localhost", "tauri://localhost", "http://localhost:1420", "http://127.0.0.1:1420"]


def make_router(jobs, valid_key):
    def authorize(request: Request):
        if not valid_key(request.headers.get("x-api-key", "")):
            raise HTTPException(401, "Desktop session credential required")
        origin = request.headers.get("origin")
        if origin is not None and origin not in DESKTOP_ORIGINS:
            raise HTTPException(403, "Desktop origin required")
    router = APIRouter(prefix="/desktop/hls", dependencies=[Depends(authorize)])
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}

    @router.get("/capabilities")
    def capabilities():
        return {"service": "guoban-desktop-hls", "version": 1,
                "seekWindow": True, "windowVersion": 1, "maxStartSeconds": 86400,
                "codecNegotiation": 1, "nativePlayback": 1 if jobs.native and jobs.native.available else 0}

    @router.post("")
    def prepare(request: Request, series_id: str, ep: int, start_seconds: float = 0):
        names = [name for name, _ in request.query_params.multi_items()]
        if (any(name not in {"series_id", "ep", "start_seconds"} for name in names)
                or len(set(names)) != len(names)):
            raise HTTPException(400, "Invalid desktop request parameters")
        negotiation = request.headers.get("x-desktop-codec-negotiation", "")
        if negotiation not in ("", "1"):
            raise HTTPException(400, "Invalid codec negotiation")
        job = jobs.create(series_id, ep, start_seconds=start_seconds, negotiate_codec=negotiation == "1")
        address, port = request.scope["server"]
        if address not in ("127.0.0.1", "localhost"):
            jobs.release(job.id)
            raise HTTPException(403, "Owned loopback listener required")
        job.stream_url = f"http://127.0.0.1:{port}/desktop/hls/{job.id}/source.mp4"
        job.stream_key = request.headers["x-api-key"]
        return {"id": job.id}

    @router.api_route("/{identifier}/source.mp4", methods=["GET", "HEAD"])
    def media_source(identifier: str, request: Request):
        job = jobs.get(identifier)
        if not isinstance(job.source, ProgressiveSource) or job.failed:
            raise HTTPException(404, "Progressive source unavailable")
        source = job.source
        total = source.size
        if not total:
            raise HTTPException(409, "Source metadata unavailable")
        start, end, code = 0, total - 1, 200
        value = request.headers.get("range")
        if value:
            match = re.fullmatch(r"bytes=([0-9]*)-([0-9]*)", value)
            if not match or not any(match.groups()):
                raise HTTPException(416, "Invalid media range", headers={"Content-Range": f"bytes */{total}"})
            if match[1]:
                start = int(match[1]); end = min(end, int(match[2])) if match[2] else end
            else:
                start = max(0, total - int(match[2]))
            if not 0 <= start <= end < total:
                raise HTTPException(416, "Media range unavailable", headers={"Content-Range": f"bytes */{total}"})
            code = 206
        response_headers = {**headers, "Accept-Ranges": "bytes", "Content-Length": str(end - start + 1)}
        if code == 206:
            response_headers["Content-Range"] = f"bytes {start}-{end}/{total}"
        if request.method == "HEAD":
            return Response(status_code=code, headers=response_headers, media_type="video/mp4")

        # Chunked framing permits clean cancellation without an intentionally
        # incomplete Content-Length response. Content-Range retains total size.
        response_headers.pop("Content-Length", None)
        def chunks():
            try:
                with source.reader(job.cancelled.is_set) as reader:
                    reader.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        data = reader.read(min(remaining, source.block_size))
                        if not data:
                            source.network_failed.set()
                            raise SourceReadError("Progressive source ended early")
                        remaining -= len(data)
                        yield data
            except (InterruptedError, SourceReadError):
                # The native owner observes network_failed separately. No URL,
                # key or expected cancellation is written to the server log.
                return
        return StreamingResponse(chunks(), status_code=code, headers=response_headers, media_type="video/mp4")

    @router.post("/{identifier}/mode")
    async def select_mode(identifier: str, request: Request):
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "Invalid video mode")
        if not isinstance(body, dict) or set(body) != {"mode"} or body["mode"] not in ("copy", "h264", "native"):
            raise HTTPException(400, "Invalid video mode")
        with jobs.guard:
            job = jobs.get(identifier)
            if not job.negotiate_codec or job.source_description is None:
                raise HTTPException(409, "Video source not ready for negotiation")
            if job.mode_selected.is_set():
                if body["mode"] != job.video_mode:
                    raise HTTPException(409, "Video mode already committed")
            else:
                if body["mode"] == "native" and (not jobs.native or not jobs.native.available
                        or not job.source_description.get("video", {}).get("contentType", "").startswith('video/mp4; codecs="hvc1.')):
                    raise HTTPException(400, "Native HEVC playback unavailable")
                if body["mode"] == "copy" and (job.start_seconds or not job.source_description.get("copyEligible")):
                    raise HTTPException(400, "Packet copy unavailable for this source window")
                job.video_mode = body["mode"]
                job.mode_selected.set()
            return {"mode": job.video_mode}

    @router.get("/{identifier}/status")
    def status(identifier: str):
        with jobs.guard:
            job = jobs.get(identifier)
            result = {"state": "failed" if job.failed else "complete" if job.done.is_set() else "preparing",
                    "duration": job.duration, "failureCode": job.failure_code,
                    "playlistReady": job.ready.is_set() and not job.failed and not job.cancelled.is_set(),
                    "startSeconds": job.start_seconds, "windowOrigin": job.window_origin}
            if job.negotiate_codec:
                result.update(source=job.source_description,
                              videoMode=job.video_mode if job.mode_selected.is_set() else None)
        result["playableRange"] = jobs.playable_range(job)
        if job.source is not None:
            result["sourceProgress"] = source_progress(job.source)
        if job.video_mode == "native" and jobs.native:
            result["playlistReady"] = False
            result["native"] = jobs.native.snapshot(identifier) if job.ready.is_set() else {"state": "preparing"}
        return result

    @router.post("/{identifier}/control")
    async def control(identifier: str, request: Request):
        job = jobs.get(identifier)
        if job.video_mode != "native" or not jobs.native or job.failed:
            raise HTTPException(409, "Native session unavailable")
        try:
            body = await request.json()
            revision = jobs.native.control(identifier, body)
        except (ValueError, TypeError, OverflowError):
            raise HTTPException(400, "Invalid native control")
        except queue.Full:
            raise HTTPException(429, "Native control queue is busy")
        return {"revision": revision}

    @router.delete("/{identifier}")
    def release(identifier: str):
        if jobs.release(identifier) is False:
            return JSONResponse({"released": False}, status_code=202, headers=headers)
        return Response(status_code=204)

    @router.get("/{identifier}/index.m3u8")
    def playlist(identifier: str):
        return Response(jobs.playlist(identifier), media_type="application/vnd.apple.mpegurl", headers=headers)

    @router.api_route("/{identifier}/{filename}", methods=["GET", "HEAD"])
    def fragment(identifier: str, filename: str):
        if filename != "init.mp4" and not re.fullmatch(r"seg[0-9]{6}\.m4s", filename):
            raise HTTPException(404, "Unknown desktop fragment")
        job = jobs.get(identifier)
        if job.failed:
            raise HTTPException(503, "Desktop encoding failed")
        path = job.directory / filename
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404, "Desktop fragment is not ready")
        return FileResponse(path, media_type="video/mp4", headers=headers)

    return router
