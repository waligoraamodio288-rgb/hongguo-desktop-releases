"""Actual disk-ready coverage; consume the host session and verified-cache callback."""
import math
import re


def playable_range(job, full_cache_ready=None):
    """Disk-ready media coverage, independent of WebView's bounded buffer."""
    duration, origin = job.duration, job.window_origin
    if (job.failed or job.cancelled.is_set() or duration is None or origin is None
            or not math.isfinite(duration) or duration <= 0):
        return [0, 0]
    if job.start_seconds and job.source and full_cache_ready:
        try:
            if full_cache_ready(job.source):
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
