"""Local HEVC player owned by the desktop session, with bounded recovery.

Only the authenticated HLS adapter supplies source paths. The client cannot
choose a process, HWND, device, file, mpv option or command string.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import threading
import time
from desktop_stream import ProgressiveSource, SourceReadError

DLL_SHA256 = "34780746a0273a4fcae42dfe262a28984a426a238939474afd3a1561b450bbef"


def validate_control(body):
    if not isinstance(body, dict) or not body or set(body) - {
            "paused", "rate", "volume", "muted", "seek", "rect", "visible"}:
        raise ValueError("Invalid native control")
    for name in ("paused", "muted", "visible"):
        if name in body and type(body[name]) is not bool:
            raise ValueError("Invalid native flag")
    for name, low, high in (("rate", .25, 4), ("volume", 0, 1), ("seek", 0, 86400)):
        if name in body:
            value = body[name]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError("Invalid native number")
    if "rect" in body:
        rect = body["rect"]
        if (not isinstance(rect, list) or len(rect) != 4
                or any(type(v) is not int or not 0 <= v <= 32768 for v in rect)
                or rect[2] < 1 or rect[3] < 1):
            raise ValueError("Invalid native rectangle")
    return dict(body)


class Event(C.Structure):
    _fields_ = [("id", C.c_int), ("error", C.c_int), ("reply", C.c_uint64), ("data", C.c_void_p)]


class Mpv:
    def __init__(self, dll):
        self.dll = dll
        self.handle = dll.mpv_create()
        if not self.handle:
            raise RuntimeError("Native player unavailable")

    @staticmethod
    def check(result):
        if result < 0:
            raise RuntimeError("Native player operation failed")

    def option(self, name, value):
        self.check(self.dll.mpv_set_option_string(self.handle, name.encode(), str(value).encode()))

    def command(self, *args):
        encoded = [str(value).encode("utf-8") for value in args]
        self.check(self.dll.mpv_command(self.handle, (C.c_char_p * (len(args) + 1))(*encoded, None)))

    def get(self, name):
        pointer = self.dll.mpv_get_property_string(self.handle, name.encode())
        if not pointer:
            return None
        try:
            return C.string_at(pointer).decode("utf-8", errors="replace")
        finally:
            self.dll.mpv_free(pointer)

    def number(self, name, default=0):
        try:
            value = float(self.get(name))
            return value if math.isfinite(value) else default
        except (TypeError, ValueError):
            return default

    def close(self):
        if self.handle:
            self.dll.mpv_terminate_destroy(self.handle)
            self.handle = None


class NativeHost:
    def __init__(self, *, parent_pid=None, dll_path=None, hardware=True):
        self.hardware = hardware
        self.parent_pid = os.getppid() if parent_pid is None else parent_pid
        self.sessions = {}
        self.guard = threading.RLock()
        self.available = False
        if os.name != "nt":
            return
        path = Path(dll_path) if dll_path else Path(__file__).parent / "native/libmpv-2.dll"
        try:
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != DLL_SHA256:
                return
            self.dll = C.CDLL(str(path.resolve()))
            definitions = {
                "mpv_create": ([], C.c_void_p),
                "mpv_set_option_string": ([C.c_void_p, C.c_char_p, C.c_char_p], C.c_int),
                "mpv_initialize": ([C.c_void_p], C.c_int),
                "mpv_command": ([C.c_void_p, C.POINTER(C.c_char_p)], C.c_int),
                "mpv_wait_event": ([C.c_void_p, C.c_double], C.POINTER(Event)),
                "mpv_get_property_string": ([C.c_void_p, C.c_char_p], C.c_void_p),
                "mpv_free": ([C.c_void_p], None),
                "mpv_terminate_destroy": ([C.c_void_p], None),
            }
            for name, (args, result) in definitions.items():
                function = getattr(self.dll, name)
                function.argtypes, function.restype = args, result
            self.user = C.WinDLL("user32", use_last_error=True)
            self.enum_callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
            self.window_callback = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
            definitions = {
                "EnumWindows": ([self.enum_callback, W.LPARAM], W.BOOL),
                "EnumChildWindows": ([W.HWND, self.enum_callback, W.LPARAM], W.BOOL),
                "GetClassNameW": ([W.HWND, W.LPWSTR, C.c_int], C.c_int),
                "SetWindowLongPtrW": ([W.HWND, C.c_int, C.c_void_p], C.c_void_p),
                "CallWindowProcW": ([C.c_void_p, W.HWND, W.UINT, W.WPARAM, W.LPARAM], C.c_ssize_t),
                "PostMessageW": ([W.HWND, W.UINT, W.WPARAM, W.LPARAM], W.BOOL),
                "MapWindowPoints": ([W.HWND, W.HWND, C.POINTER(W.POINT), W.UINT], C.c_int),
                "GetWindowThreadProcessId": ([W.HWND, C.POINTER(W.DWORD)], W.DWORD),
                "GetWindow": ([W.HWND, W.UINT], W.HWND),
                "IsWindow": ([W.HWND], W.BOOL),
                "IsWindowVisible": ([W.HWND], W.BOOL),
                "GetClientRect": ([W.HWND, C.POINTER(W.RECT)], W.BOOL),
                "SetProcessDpiAwarenessContext": ([C.c_void_p], W.BOOL),
                "SetThreadDpiAwarenessContext": ([C.c_void_p], C.c_void_p),
                "CreateWindowExW": ([W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int,
                    C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p], W.HWND),
                "SetWindowPos": ([W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT], W.BOOL),
                "ShowWindow": ([W.HWND, C.c_int], W.BOOL),
                "DestroyWindow": ([W.HWND], W.BOOL),
                "PeekMessageW": ([C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT], W.BOOL),
                "TranslateMessage": ([C.POINTER(W.MSG)], W.BOOL),
                "DispatchMessageW": ([C.POINTER(W.MSG)], C.c_ssize_t),
            }
            for name, (args, result) in definitions.items():
                function = getattr(self.user, name)
                function.argtypes, function.restype = args, result
            self.user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
            self.available = True
        except (OSError, AttributeError):
            self.available = False

    def parent_window(self):
        windows = []
        @self.enum_callback
        def collect(hwnd, _):
            pid = W.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, C.byref(pid))
            if pid.value == self.parent_pid and not self.user.GetWindow(hwnd, 4):
                rect = W.RECT()
                if self.user.GetClientRect(hwnd, C.byref(rect)) and rect.right > 100 and rect.bottom > 100:
                    windows.append((bool(self.user.IsWindowVisible(hwnd)), rect.right * rect.bottom, hwnd))
            return True
        self.user.EnumWindows(collect, 0)
        if not windows:
            raise RuntimeError("Desktop parent window unavailable")
        return max(windows, key=lambda item: item[:2])[2]

    def prepare(self, job):
        if not self.available or job.cancelled.is_set():
            raise RuntimeError("Native player unavailable")
        with self.guard:
            if job.cancelled.is_set():
                raise RuntimeError("Native job cancelled")
            for previous in list(self.sessions.values()):
                previous.close()
            self.sessions.clear()
            session = NativeSession(self, job, self.parent_window())
            self.sessions[job.id] = session
            try:
                session.thread.start()
                if job.cancelled.is_set():
                    raise RuntimeError("Native job cancelled")
            except BaseException:
                self.sessions.pop(job.id, None)
                session.close()
                raise

    def snapshot(self, identifier):
        with self.guard:
            session = self.sessions.get(identifier)
            return session.snapshot() if session else {"state": "failed", "failureCode": "native-unavailable"}

    def control(self, identifier, body):
        body = validate_control(body)
        with self.guard:
            session = self.sessions.get(identifier)
            if not session or session.stop.is_set():
                raise ValueError("Native session unavailable")
            return session.submit(body)

    def release(self, identifier):
        with self.guard:
            session = self.sessions.pop(identifier, None)
        if session:
            session.close()


class NativeSession:
    def __init__(self, host, job, parent):
        self.host, self.job, self.parent = host, job, parent
        self.stop = threading.Event()
        self.commands = queue.Queue(maxsize=64)
        self.guard = threading.Lock()
        self.revision = 0
        self.data = {"state": "preparing", "time": job.start_seconds, "duration": job.duration,
                     "paused": True, "rate": 1, "volume": 1, "muted": False, "seeking": False,
                     "width": 0, "height": 0, "decoder": "probing", "revision": 0,
                     "hardwareAttempted": host.hardware, "softwareRetried": False}
        self.thread = threading.Thread(target=self.run, name="desktop-native-player", daemon=True)
        self.input_hooks = {}

    def forward_input(self, container):
        """Forward native input to the existing WebView, preserving its trusted
        fullscreen/keyboard behavior and avoiding a second control state machine.
        Both targets are discovered exclusively inside the owned desktop root.
        """
        user = self.host.user
        widgets, surfaces = [], []
        @self.host.enum_callback
        def collect(hwnd, _):
            name = C.create_unicode_buffer(256)
            user.GetClassNameW(hwnd, name, 256)
            if name.value == "Chrome_RenderWidgetHostHWND":
                widgets.append(hwnd)
            return True
        user.EnumChildWindows(self.parent, collect, 0)
        @self.host.enum_callback
        def video(hwnd, _):
            surfaces.append(hwnd)
            return True
        user.EnumChildWindows(container, video, 0)
        if not widgets or not surfaces:
            return False
        widget = widgets[0]
        for surface in surfaces:
            if surface in self.input_hooks:
                continue
            original = [None]
            @self.host.window_callback
            def procedure(hwnd, message, wparam, lparam, target=widget, previous=original):
                if message == 0x0021:  # WM_MOUSEACTIVATE: keep focus in WebView2.
                    return 3  # MA_NOACTIVATE
                if 0x0200 <= message <= 0x020E or message in (0x0100,0x0101,0x0102,0x0104,0x0105,0x0106):
                    if 0x0200 <= message <= 0x0209 or message in (0x020B,0x020C,0x020D):
                        point = W.POINT(C.c_short(lparam & 0xffff).value,
                                        C.c_short((lparam >> 16) & 0xffff).value)
                        user.MapWindowPoints(hwnd, target, C.byref(point), 1)
                        lparam = (point.x & 0xffff) | ((point.y & 0xffff) << 16)
                    user.PostMessageW(target, message, wparam, lparam)
                    return 0
                return user.CallWindowProcW(previous[0], hwnd, message, wparam, lparam)
            previous = user.SetWindowLongPtrW(surface, -4, C.cast(procedure, C.c_void_p))
            if not previous:
                raise RuntimeError("Native input bridge unavailable")
            original[0] = previous
            self.input_hooks[surface] = (previous, procedure)
        return True

    def snapshot(self):
        with self.guard:
            return dict(self.data)

    def submit(self, command):
        with self.guard:
            revision = self.revision + 1
            self.commands.put_nowait((revision, command))
            self.revision = revision
            return revision

    def close(self):
        self.stop.set()
        if self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=3)

    def run(self):
        player = None
        hwnd = None
        user = self.host.user
        initial = time.monotonic()
        grace = initial + 3
        last_progress, last_position, slow_since = initial, None, None
        retried = False
        frame_ready = False
        progressive = isinstance(self.job.source, ProgressiveSource)
        media_uri = str(self.job.source) if not progressive else self.job.stream_url
        # Starting paused allows the frontend to place the surface and apply
        # its remembered speed/volume before either picture or sound advances.
        desired = {"paused": True, "rate": 1, "volume": 1, "muted": False}
        def retry_software():
            nonlocal retried, initial, grace, last_progress, slow_since, frame_ready
            if retried or player.get("hwdec-current") == "no":
                raise RuntimeError("Software decoding failed")
            retried = True
            frame_ready = False
            position = player.number("time-pos", self.job.start_seconds)
            player.command("set", "hwdec", "no")
            player.command("set", "start", position)
            player.command("loadfile", media_uri)
            for key, option in (("paused", "pause"), ("rate", "speed"), ("volume", "volume"), ("muted", "mute")):
                value = desired[key]
                player.command("set", option, "yes" if value is True else "no" if value is False else value * 100 if key == "volume" else value)
            initial = last_progress = time.monotonic()
            grace, slow_since = initial + 3, None
            with self.guard:
                self.data.update(state="preparing", softwareRetried=True)
        try:
            user.SetThreadDpiAwarenessContext(C.c_void_p(-4))
            hwnd = user.CreateWindowExW(0x08000000, "STATIC", "Hongguo native video",
                                       0x40000000 | 0x04000000 | 0x02000000,
                                       0, 0, 1, 1, self.parent, None, None, None)
            if not hwnd:
                raise RuntimeError("Native surface unavailable")
            player = Mpv(self.host.dll)
            options = {"config": "no", "load-scripts": "no", "osc": "no", "terminal": "no",
                       "input-default-bindings": "no", "input-vo-keyboard": "no",
                       "idle": "yes", "keep-open": "yes", "pause": "yes", "start": self.job.start_seconds,
                       "hwdec": "auto-safe" if self.host.hardware else "no", "hwdec-software-fallback": "yes", "vo": "gpu",
                       "gpu-api": "d3d11", "gpu-context": "d3d11", "wid": int(hwnd),
                       "ao": "wasapi", "audio-exclusive": "no", "video-sync": "audio",
                       "audio-pitch-correction": "yes", "priority": "abovenormal",
                       "framedrop": "vo", "vd-lavc-threads": "0"}
            for key, value in options.items():
                player.option(key, value)
            if progressive:
                for key, value in {"cache": "yes", "cache-secs": "12", "demuxer-readahead-secs": "12",
                                   "demuxer-max-bytes": "32MiB", "cache-pause": "yes",
                                   "cache-pause-wait": "1", "demuxer-lavf-format": "mov"}.items():
                    player.option(key, value)
                if self.job.stream_key:
                    player.option("http-header-fields", "x-api-key: " + self.job.stream_key)
                if self.job.source.options():
                    player.option("demuxer-lavf-o", "decryption_key=" + self.job.source.options()["decryption_key"])
            player.check(player.dll.mpv_initialize(player.handle))
            player.command("loadfile", media_uri)
            message = W.MSG()
            while not self.stop.is_set() and not self.job.cancelled.is_set() and user.IsWindow(self.parent):
                while user.PeekMessageW(C.byref(message), None, 0, 0, 1):
                    user.TranslateMessage(C.byref(message))
                    user.DispatchMessageW(C.byref(message))
                for _ in range(64):
                    event = player.dll.mpv_wait_event(player.handle, 0).contents
                    if event.id == 0:
                        break
                    if event.id == 21:  # MPV_EVENT_PLAYBACK_RESTART: first frame has restarted.
                        frame_ready = True
                    if event.id == 7 and event.data:
                        fields = C.cast(event.data, C.POINTER(C.c_int))
                        if fields[0] == 4 or fields[1] < 0:
                            if progressive and self.job.source.network_failed.is_set():
                                raise SourceReadError("Native media input unavailable")
                            retry_software()
                for _ in range(64):
                    try:
                        revision, command = self.commands.get_nowait()
                    except queue.Empty:
                        break
                    if "rect" in command:
                        x, y, width, height = command["rect"]
                        client = W.RECT()
                        if not user.GetClientRect(self.parent, C.byref(client)):
                            raise RuntimeError("Desktop parent unavailable")
                        width, height = min(width, max(1, client.right - x)), min(height, max(1, client.bottom - y))
                        user.SetWindowPos(hwnd, W.HWND(0), x, y, width, height, 0x0010)
                    if "visible" in command:
                        user.ShowWindow(hwnd, 4 if command["visible"] else 0)
                    for key, option in (("paused", "pause"), ("rate", "speed"), ("volume", "volume"), ("muted", "mute")):
                        if key in command:
                            value = command[key]
                            desired[key] = value
                            player.command("set", option, "yes" if value is True else "no" if value is False else value * 100 if key == "volume" else value)
                            grace = time.monotonic() + 3
                    if "seek" in command:
                        target = command["seek"]
                        if self.job.duration and target >= self.job.duration:
                            target = max(0, self.job.duration - .05)
                        player.command("seek", target, "absolute+exact")
                        frame_ready = False
                        initial = time.monotonic()
                        grace = initial + 3
                    with self.guard:
                        self.data["revision"] = revision
                if progressive and self.job.source.network_failed.is_set():
                    raise SourceReadError("Native media input unavailable")
                now = time.monotonic()
                width = int(player.number("video-params/w"))
                height = int(player.number("video-params/h"))
                # A decoded first frame/output is required, not merely a
                # hardware capability string or successful loadfile command.
                hwdec = player.get("hwdec-current")
                position = player.number("time-pos", self.job.start_seconds)
                paused = player.get("pause") == "yes"
                seeking = player.get("seeking") == "yes"
                eof = player.get("eof-reached") == "yes"
                output_ready = frame_ready and width > 0 and height > 0 and player.get("current-vo") == "gpu" and player.get("video-out-params") is not None
                if output_ready and not self.input_hooks:
                    # Native renderer must not cover the existing trusted UI
                    # input surface without restoring click/key forwarding.
                    output_ready = self.forward_input(hwnd)
                if eof and not output_ready:
                    retry_software()
                    continue
                avsync = player.number("avsync")
                buffering = progressive and (player.get("paused-for-cache") == "yes"
                                             or not output_ready and self.job.source.reading.is_set())
                buffer_start, buffer_end = 0.0, self.job.duration or 0.0
                if progressive:
                    buffer_start = position
                    buffer_end = max(position, player.number("demuxer-cache-time", position))
                    try:
                        ranges = json.loads(player.get("demuxer-cache-state") or "{}").get("seekable-ranges", [])
                        selected = next((r for r in ranges if r["start"] - .5 <= position <= r["end"] + .5), None)
                        if selected:
                            buffer_start, buffer_end = max(0, selected["start"]), selected["end"]
                    except (ValueError, TypeError, KeyError):
                        pass
                if last_position is None or abs(position - last_position) > .01 or paused or seeking:
                    last_position, last_progress = position, now
                unstable = not paused and not buffering and not seeking and not eof and now > grace
                if buffering:
                    last_progress = now
                if unstable and abs(avsync) > .2:
                    slow_since = slow_since or now
                else:
                    slow_since = None
                if (unstable and (now - last_progress > 3 or slow_since and now - slow_since > 2)
                        or not output_ready and not buffering and now - initial > 10):
                    if progressive and self.job.source.network_failed.is_set():
                        raise SourceReadError("Native media input timed out")
                    retry_software()
                    continue
                with self.guard:
                    self.data.update(state="ended" if eof and output_ready else "buffering" if buffering else "ready" if output_ready else "preparing",
                                     time=position, duration=player.number("duration", self.job.duration),
                                     paused=paused, rate=player.number("speed", desired["rate"]),
                                     volume=player.number("volume", desired["volume"] * 100) / 100,
                                     muted=player.get("mute") == "yes", seeking=seeking,
                                     width=width, height=height, decoder="software" if hwdec == "no" else "hardware" if hwdec else "probing",
                                     hwdec=hwdec, avsync=avsync, audioDevice=player.get("audio-device"),
                                     buffering=buffering, outputReady=output_ready, bufferStart=buffer_start,
                                     bufferEnd=min(buffer_end, self.job.duration or buffer_end),
                                     audioExclusive=player.get("audio-exclusive"), audioOutput=player.get("current-ao"),
                                     frameDrops=player.number("frame-drop-count"), decoderDrops=player.number("decoder-frame-drop-count"))
                self.stop.wait(.04)
        except SourceReadError:
            with self.guard:
                self.data.update(state="failed", failureCode="source-read")
        except Exception:
            with self.guard:
                self.data.update(state="failed", failureCode="native-decode")
        finally:
            for surface, (previous, callback) in self.input_hooks.items():
                if user.IsWindow(surface):
                    user.SetWindowLongPtrW(surface, -4, previous)
            if player:
                player.close()
            if hwnd and user.IsWindow(hwnd):
                user.DestroyWindow(hwnd)
