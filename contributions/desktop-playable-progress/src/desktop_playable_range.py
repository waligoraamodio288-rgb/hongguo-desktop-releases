"""Actual disk-ready coverage; consume the host session and verified-cache callback."""
import math
import re


def playable_range(job, full_cache_ready=None, *, native_state=None):
    """Disk-ready media coverage, independent of WebView's bounded buffer."""
    duration, origin = job.duration, job.window_origin
    if (job.failed or job.cancelled.is_set() or duration is None or origin is None
            or not math.isfinite(duration) or duration <= 0
            or not math.isfinite(origin) or not 0 <= origin < duration):
        return [0, 0]
    if getattr(job, "video_mode", None) == "native":
        # The native owner reports retained packets, independent of presentation time.
        state = native_state or {}
        if state.get("state") not in ("ready", "buffering", "ended") or not state.get("outputReady"):
            return [0, 0]
        start, end = state.get("bufferStart"), state.get("bufferEnd")
        if (type(start) not in (int, float) or type(end) not in (int, float)
                or not math.isfinite(start) or not math.isfinite(end)
                or start < 0 or end <= start or start >= duration):
            return [0, 0]
        if job.cancelled.is_set() or job.failed:
            return [0, 0]
        return [start, min(duration, end)]
    if job.source and full_cache_ready:
        try:
            if full_cache_ready(job.source):
                if job.cancelled.is_set() or job.failed:
                    return [0, 0]
                return [0, duration]
        except (OSError, ValueError):
            pass  # Optional disk cache must not interrupt status/playback.
    try:
        init = job.directory / "init.mp4"
        if not init.is_file() or init.is_symlink() or init.stat().st_size == 0:
            return [0, 0]
        lines = (job.directory / "index.m3u8").read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "#EXTM3U":
            return [0, 0]
        # This adapter serves clear local fMP4 only. A fragment cannot prove
        # decryptability, even when an encrypted playlist has ENDLIST.
        if any(line.startswith(("#EXT-X-KEY:", "#EXT-X-SESSION-KEY:")) for line in lines):
            return [0, 0]
        parameters = {}
        for tag, minimum in (("TARGETDURATION", 1), ("VERSION", 6)):
            prefix = "#EXT-X-" + tag + ":"
            values = [line[len(prefix):] for line in lines if line.startswith(prefix)]
            if (len(values) != 1 or not re.fullmatch(r"[0-9]{1,20}", values[0])
                    or int(values[0]) < minimum):
                return [0, 0]
            parameters[tag] = int(values[0])
        available, pending, count, incomplete = 0.0, None, 0, False
        mapped, ended = False, False
        for line in lines:
            if line.startswith("#EXT-X-MAP:"):
                if line != '#EXT-X-MAP:URI="init.mp4"':
                    return [0, 0]
                mapped = True
            elif line.startswith("#EXTINF:"):
                if pending is not None:
                    return [0, 0]
                token, comma, _ = line[8:].partition(",")
                if not comma or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", token):
                    return [0, 0]
                pending = float(token)
                if (not math.isfinite(pending) or pending <= 0
                        or math.floor(pending + 0.5) > parameters["TARGETDURATION"]):
                    return [0, 0]
            elif line == "#EXT-X-ENDLIST":
                if ended:
                    return [0, 0]
                ended = True
            elif line and not line.startswith("#"):
                if not mapped or pending is None or not re.fullmatch(r"seg[0-9]{6}\.m4s", line):
                    return [0, 0]
                fragment = job.directory / line
                if not incomplete:
                    if not fragment.is_file() or fragment.is_symlink() or fragment.stat().st_size == 0:
                        incomplete = True
                    else:
                        available += pending
                        count += 1
                pending = None
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
