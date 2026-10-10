"""Complete local HLS artifacts, isolated from source downloads and sessions."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import threading
import uuid

from desktop_hls import EncodingCancelled


OWNER = "desktop-playable-cache-v1"


def plain(path):
    try:
        return not (path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except AttributeError:
        return not path.is_symlink()
    except FileNotFoundError:
        return True


class PlayableEpisodeCache:
    def __init__(self, root, *, encoder, quota_bytes=2 * 1024 ** 3, profile_files=None):
        root = Path(root)
        self.available = True
        try:
            root.mkdir(parents=True, exist_ok=True)
            if not plain(root):
                raise ValueError("Playable cache root cannot be a reparse point")
            self.root = root.resolve()
        except OSError:
            self.available = False
            self.root = root.absolute()  # Do not probe an inaccessible optional path again.
        self.encoder = encoder
        self.quota_bytes = quota_bytes
        self.guard = threading.RLock()
        module = Path(__file__).parent
        # Explicit files permit portable tests without distributing host modules.
        # Production default fingerprints the real encoder AND budget policy.
        profile_files = tuple(profile_files) if profile_files is not None else (
            module / name for name in ("desktop_hls.py", "desktop_hls_budget.py", "desktop_codec.py")
            if name != "desktop_codec.py" or (module / name).is_file())
        self.profile = hashlib.sha256(b"playable-hls-full-v1" + b"".join(
            Path(path).read_bytes() for path in profile_files
        )).hexdigest()

    def _identity(self, source, video_mode="h264", cancelled=lambda: False):
        if cancelled():
            raise EncodingCancelled()
        if video_mode not in ("h264", "copy"):
            raise ValueError("Unknown desktop video mode")
        identity = getattr(source, "cache_identity", None)
        if callable(identity):
            value = {**identity(), "profile": self.profile}
        else:
            source = Path(source)
            info = source.stat()
            value = {"name": source.name, "size": info.st_size,
                     "mtimeNs": info.st_mtime_ns, "profile": self.profile,
                     "sha256": self._digest(source, cancelled)}
        if video_mode != "h264":
            value["videoMode"] = video_mode
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest(), value

    @staticmethod
    def _digest(path, cancelled=lambda: False):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while True:
                if cancelled():
                    raise EncodingCancelled()
                block = stream.read(1024 * 1024)
                if cancelled():
                    raise EncodingCancelled()
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _media_files(directory):
        if not plain(directory) or not directory.is_dir():
            raise ValueError("Invalid artifact directory")
        marker = directory / "complete.marker"
        index = directory / "index.m3u8"
        if not plain(marker) or not plain(index) or marker.read_text(encoding="ascii") != "desktop-hls-v1\n":
            raise ValueError("Artifact completion is unavailable")
        text = index.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines or lines[0] != "#EXTM3U":
            raise ValueError("Artifact playlist header is invalid")
        parameters = {}
        for tag, minimum in (("TARGETDURATION", 1), ("VERSION", 6)):
            prefix = "#EXT-X-" + tag + ":"
            values = [line[len(prefix):] for line in lines if line.startswith(prefix)]
            if (len(values) != 1 or not re.fullmatch(r"[0-9]{1,20}", values[0])
                    or int(values[0]) < minimum):
                raise ValueError("Invalid artifact HLS " + tag)
            parameters[tag] = int(values[0])
        if "#EXT-X-ENDLIST" not in lines:
            raise ValueError("Artifact playlist is incomplete")
        mapped, ended, segments, pending = False, False, [], None
        for line in lines:
            if line == "#EXT-X-GAP" or line.startswith(("#EXT-X-KEY:", "#EXT-X-SESSION-KEY:", "#EXT-X-BYTERANGE:")):
                raise ValueError("Unsupported local artifact HLS tag")
            if line.startswith("#EXT-X-MAP:"):
                if line != '#EXT-X-MAP:URI="init.mp4"':
                    raise ValueError("Invalid artifact initialization map")
                mapped = True
            elif line == "#EXT-X-ENDLIST":
                if ended:
                    raise ValueError("Invalid artifact ending")
                ended = True
            elif line.startswith("#EXTINF:"):
                token, comma, _ = line[8:].partition(",")
                if (pending is not None or not comma
                        or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", token)):
                    raise ValueError("Invalid artifact segment duration")
                pending = float(token)
                if (not math.isfinite(pending) or pending <= 0
                        or math.floor(pending + 0.5) > parameters["TARGETDURATION"]):
                    raise ValueError("Artifact duration exceeds its HLS target")
            elif line and not line.startswith("#"):
                if not mapped or pending is None:
                    raise ValueError("Artifact media is outside its HLS tag scope")
                segments.append(line)
                pending = None
        if pending is not None or not segments or len(set(segments)) != len(segments) or any(
                not re.fullmatch(r"seg[0-9]{6}\.m4s", name) for name in segments):
            raise ValueError("Invalid artifact segment names")
        # The marker is the commit signal, including when restoring a session.
        names = ["index.m3u8", "init.mp4", *segments, "complete.marker"]
        for name in names:
            path = directory / name
            if not plain(path) or not path.is_file() or path.stat().st_size == 0:
                raise ValueError("Artifact fragment is unavailable")
        return names

    def _validated(self, source, video_mode="h264", cancelled=lambda: False):
        if not self.available:
            return None
        try:
            key, identity = self._identity(source, video_mode, cancelled)
            directory = self.root / key
            manifest_path = directory / "cache.json"
            if not plain(directory) or not plain(manifest_path):
                return None
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (not isinstance(manifest, dict) or manifest.get("owner") != OWNER
                    or manifest.get("source") != identity):
                return None
            names = self._media_files(directory)
            if set(manifest["files"]) != set(names):
                return None
            for name in names:
                if cancelled():
                    raise EncodingCancelled()
                item = directory / name
                if manifest["files"][name] != {"bytes": item.stat().st_size, "sha256": self._digest(item, cancelled)}:
                    return None
            return directory, names
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def contains(self, source, video_mode="h264", *, cancelled=lambda: False):
        with self.guard:
            return self._validated(source, video_mode, cancelled) is not None

    def restore(self, source, directory, cancelled=lambda: False, *, video_mode="h264"):
        with self.guard:
            artifact = self._validated(source, video_mode, cancelled)
            if artifact is None:
                return False
            cached, names = artifact
            directory = Path(directory)
            directory.mkdir(parents=False, exist_ok=False)
            created = []
            try:
                for name in names:
                    if cancelled():
                        raise EncodingCancelled()
                    destination = directory / name
                    # copyfile may create a partial destination before raising.
                    created.append(destination)
                    shutil.copyfile(cached / name, destination)
                try:
                    os.utime(cached / "cache.json", None)
                except OSError:
                    pass  # Read-only metadata must not destroy an otherwise valid hit.
                return True
            except BaseException:
                for path in created:
                    path.unlink(missing_ok=True)
                directory.rmdir()
                raise

    def _owned_children(self, directory):
        if (directory.parent != self.root or not plain(directory)
                or not re.fullmatch(r"(?:[0-9a-f]{64}|stage-[0-9a-f]{32})", directory.name)):
            raise ValueError("Unsafe playable cache cleanup")
        children = list(directory.iterdir())
        if any(not plain(path) or not path.is_file() for path in children):
            raise ValueError("Unknown content in playable cache")
        owner = directory / "owner.marker"
        if not owner.is_file() or owner.read_text(encoding="ascii") != OWNER:
            raise ValueError("Unowned playable cache directory")
        return children

    def _remove_owned(self, directory):
        children = self._owned_children(directory)
        for path in children:
            path.unlink()
        directory.rmdir()

    def _reserve(self, needed, *, replacing=None):
        if not self.available:
            raise OSError("Playable cache is unavailable")
        if not 0 <= needed <= self.quota_bytes:
            raise OSError("Playable cache reservation cannot fit")
        if replacing is not None:
            self._owned_children(replacing)
        entries = []
        total = 0
        for directory in self.root.iterdir():
            if not re.fullmatch(r"(?:[0-9a-f]{64}|stage-[0-9a-f]{32})", directory.name) or not plain(directory) or not directory.is_dir():
                continue
            # Unknown nested content still occupies disk, but is never evicted.
            # Fail closed on unreadable content or links rather than count it as zero.
            def size_of(path):
                if not plain(path):
                    raise OSError("Cannot account for a linked cache entry")
                if path.is_dir():
                    return sum(size_of(child) for child in path.iterdir())
                if not path.is_file():
                    raise OSError("Cannot account for an unknown cache entry")
                return path.stat().st_size
            children = list(directory.iterdir())
            size = sum(size_of(p) for p in children)
            if directory == replacing:
                continue  # Its validated bytes leave at commit, before replacement.
            total += size
            try:
                if any(not p.is_file() for p in children):
                    continue
                if (re.fullmatch(r"[0-9a-f]{64}", directory.name)
                        and (directory / "owner.marker").read_text(encoding="ascii") == OWNER):
                    try:
                        modified = (directory / "cache.json").stat().st_mtime_ns
                    except FileNotFoundError:
                        modified = directory.stat().st_mtime_ns
                    entries.append((modified, directory, size))
            except (OSError, UnicodeError):
                continue
        if total + needed - sum(size for _, _, size in entries) > self.quota_bytes:
            raise OSError("Playable cache reservation cannot fit")
        for _, directory, size in sorted(entries):
            if total + needed <= self.quota_bytes:
                return
            self._remove_owned(directory)
            total -= size
        if total + needed > self.quota_bytes:
            raise OSError("Playable cache budget is exhausted")

    def store(self, source, directory, cancelled=lambda: False, *, video_mode="h264"):
        if cancelled():
            raise EncodingCancelled()
        if not self.available:
            return None
        with self.guard:
            key, identity = self._identity(source, video_mode, cancelled)
            names = self._media_files(Path(directory))
            directory = Path(directory)
            adopt = (directory.parent == self.root
                     and re.fullmatch(r"stage-[0-9a-f]{32}", directory.name)
                     and plain(directory)
                     and (directory / "owner.marker").read_text(encoding="ascii") == OWNER)
            if cancelled():
                raise EncodingCancelled()
            stage = directory if adopt else self.root / ("stage-" + uuid.uuid4().hex)
            if not adopt:
                stage.mkdir()
                (stage / "owner.marker").write_text(OWNER, encoding="ascii")
            try:
                files = {}
                for name in names:
                    if cancelled():
                        raise EncodingCancelled()
                    target = stage / name
                    if not adopt:
                        shutil.copyfile(directory / name, target)
                    files[name] = {"bytes": target.stat().st_size, "sha256": self._digest(target, cancelled)}
                if cancelled():
                    raise EncodingCancelled()
                manifest = {"owner": OWNER, "source": identity, "files": files}
                (stage / "cache.json").write_text(json.dumps(manifest), encoding="utf-8")
                if cancelled():
                    raise EncodingCancelled()
                target = self.root / key
                if target.exists():
                    self._owned_children(target)  # Protect unrelated LRU before reservation.
                # Stage bytes are already counted. Evict only at commit, after
                # all cancellable copying/hashing and manifest construction.
                metadata_bytes = sum((stage / name).stat().st_size for name in ("owner.marker", "cache.json"))
                self._reserve(max(0, 65536 - metadata_bytes), replacing=target if target.exists() else None)
                if target.exists():
                    self._remove_owned(target)
                os.replace(stage, target)
                return target
            finally:
                if stage.exists():
                    self._remove_owned(stage)

    def encode(self, source, directory, on_ready=lambda: None, *, cancelled=lambda: False,
               start_seconds=0, on_window=lambda origin, duration: None, video_mode="h264"):
        if not start_seconds:
            try:
                if self.restore(source, directory, cancelled, video_mode=video_mode):
                    on_ready()
                    return
            except OSError:
                pass
        if start_seconds:
            extra = {"video_mode": "copy"} if video_mode == "copy" else {}
            self.encoder(source, directory, on_ready, cancelled=cancelled,
                         start_seconds=start_seconds, on_window=on_window, **extra)
        else:
            extra = {"video_mode": "copy"} if video_mode == "copy" else {}
            self.encoder(source, directory, on_ready, cancelled=cancelled, **extra)
            try:
                self.store(source, directory, cancelled, video_mode=video_mode)
            except (OSError, ValueError, TypeError):
                pass
