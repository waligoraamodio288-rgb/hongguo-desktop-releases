"""Actual stream descriptions and packet-copy desktop HLS."""
from pathlib import Path
import math
from desktop_stream import open_media


def video_codec_string(name, extra):
    extra = extra or b""
    if name == "h264" and len(extra) >= 7 and extra[0] == 1:
        return "avc1." + extra[1:4].hex().upper()
    if name == "hevc" and len(extra) >= 23 and extra[0] == 1:
        profile = extra[1]
        space = ("", "A", "B", "C")[profile >> 6]
        compatibility = int(f"{int.from_bytes(extra[2:6], 'big'):032b}"[::-1], 2)
        suffix = "".join(f".{byte:02X}" for byte in extra[6:12].rstrip(b"\0"))
        return f"hvc1.{space}{profile & 31}.{compatibility:X}.{'H' if profile & 32 else 'L'}{extra[12]}{suffix}"
    return None


def aac_lc(context):
    extra = context.extradata or b""
    return (context.name == "aac" and len(extra) >= 2 and extra[0] >> 3 == 2
            and getattr(context, "profile", None) in (None, "LC"))


def describe_streams(media):
    if len(media.streams.video) != 1:
        return {"copyEligible": False}
    stream = media.streams.video[0]
    context = stream.codec_context
    codec = video_codec_string(context.name, context.extradata)
    rate = float(stream.average_rate or 30)
    if not codec or not math.isfinite(rate) or not 0 < rate <= 120:
        return {"copyEligible": False}
    video = {"contentType": f'video/mp4; codecs="{codec}"', "width": context.width,
             "height": context.height, "framerate": rate,
             "bitrate": max(1, context.bit_rate or 2000000)}
    copy_eligible = True
    audio = []
    for track in media.streams.audio:
        c = track.codec_context
        if not aac_lc(c):
            # HLS packet-copy limits must not hide a recognized video codec:
            # native playback decodes the original audio itself.
            copy_eligible = False
            audio.append({"codec": c.name, "profile": getattr(c, "profile", None)})
            continue
        audio.append({"contentType": 'audio/mp4; codecs="mp4a.40.2"',
                      "channels": str(len(c.layout.channels)), "samplerate": c.sample_rate,
                      "bitrate": max(1, c.bit_rate or 128000)})
    return {"copyEligible": copy_eligible, "video": video, "audio": audio}


def copy_hls(source, directory, on_ready=lambda: None, *, cancelled=lambda: False,
             max_output_bytes=512 * 1024 ** 2, start_seconds=0,
             on_window=lambda origin, duration: None):
    if start_seconds:
        raise ValueError("Packet copy requires a full source window")
    import av
    from desktop_hls import EncodingCancelled
    from desktop_hls_budget import EncodingBudgetExceeded

    directory = Path(directory)
    directory.mkdir(parents=False, exist_ok=False)
    ready = False
    with open_media(source, cancelled=cancelled) as reader:
        if not describe_streams(reader)["copyEligible"]:
            raise ValueError("Unsupported packet copy source")
        on_window(0.0, reader.duration / av.time_base if reader.duration else None)
        options = {"hls_time": "2", "hls_list_size": "0", "hls_playlist_type": "event",
                   "hls_segment_type": "fmp4", "hls_fmp4_init_filename": "init.mp4",
                   "hls_segment_filename": (directory / "seg%06d.m4s").as_posix(),
                   "hls_flags": "temp_file+independent_segments"}
        # Preserve B-frame decode preroll and AAC priming instead of shifting
        # every presentation timestamp to make the first DTS non-negative.
        clock = math.lcm(1000, *(s.time_base.denominator for s in reader.streams
                                if s.type in ("video", "audio")))
        if clock > 2147483647:
            raise ValueError("Unsupported desktop movie clock")
        options.update(avoid_negative_ts="disabled",
                       hls_segment_options=f"avoid_negative_ts=disabled:movie_timescale={clock}")
        with av.open((directory / "index.m3u8").as_posix(), "w", format="hls", options=options) as writer:
            streams = {}
            for stream in reader.streams:
                if stream.type not in ("video", "audio"):
                    continue
                target = writer.add_stream_from_template(stream)
                target.codec_context.codec_tag = {"hevc": "hvc1", "h264": "avc1", "aac": "mp4a"}[stream.codec_context.name]
                streams[stream.index] = target
            first_video = True
            for count, packet in enumerate(reader.demux()):
                if cancelled():
                    raise EncodingCancelled()
                if packet.dts is None or packet.stream.index not in streams:
                    continue
                if packet.stream.type == "video" and first_video:
                    if not packet.is_keyframe:
                        raise ValueError("Source has no independent first video frame")
                    first_video = False
                packet.stream = streams[packet.stream.index]
                writer.mux(packet)
                if count % 32 == 0 and sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) > max_output_bytes - len(b"desktop-hls-v1\n"):
                    raise EncodingBudgetExceeded("Desktop packet copy budget exceeded")
                if not ready and (directory / "index.m3u8").is_file():
                    ready = True
                    on_ready()
    if cancelled():
        raise EncodingCancelled()
    playlist = (directory / "index.m3u8").read_text(encoding="utf-8")
    if "#EXT-X-ENDLIST" not in playlist or not (directory / "seg000000.m4s").is_file():
        raise ValueError("Packet copy produced no complete media")
    if sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) > max_output_bytes - len(b"desktop-hls-v1\n"):
        raise EncodingBudgetExceeded("Desktop packet copy budget exceeded")
    (directory / "complete.marker").write_text("desktop-hls-v1\n", encoding="ascii")
    if not ready:
        on_ready()
    return directory / "index.m3u8"
