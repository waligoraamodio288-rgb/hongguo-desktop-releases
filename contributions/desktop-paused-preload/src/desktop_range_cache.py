"""Session-owned original blocks; enforce disk limits before any payload write."""
import threading


class RangeDiskCache:
    def __init__(self, path, budget, total):
        if type(budget) is not int or budget <= 0:
            raise ValueError("Invalid range cache budget")
        self.guard = threading.Lock()
        self.budget, self.total = budget, total
        self.entries = {}
        self.bytes = 0
        self.limited = False
        self.closed = False
        self.failed = False
        # The caller supplies its generated job directory, never a media path.
        self.file = path.open('xb+')

    def read(self, index):
        with self.guard:
            if self.closed or index not in self.entries:
                return None
            offset, length = self.entries[index]
            try:
                self.file.seek(offset)
                value = self.file.read(length)
                if len(value) != length:
                    raise OSError("Incomplete range cache block")
                return value
            except OSError:
                self.failed = True
                self.entries.clear()
                return None

    def can_store(self, index, length):
        with self.guard:
            if self.closed or self.failed:
                return False
            if index in self.entries:
                return True
            if self.bytes + length > self.budget:
                self.limited = True
                return False
            return True

    def store(self, index, value, cancelled):
        with self.guard:
            if self.closed or self.failed or cancelled() or index in self.entries:
                return
            if self.bytes + len(value) > self.budget:
                self.limited = True
                return
            offset = self.bytes
            try:
                self.file.seek(offset)
                if self.file.write(value) != len(value):
                    raise OSError("Incomplete range cache write")
                self.file.flush()
                self.entries[index] = (offset, len(value))
                self.bytes += len(value)
            except OSError:
                self.failed = True
                self.entries.clear()
                # The attempted write itself was already bounded by budget.
                # Keep the file for the owning job's cleanup; foreground reads
                # simply fall back to the original validated source.

    def snapshot(self):
        with self.guard:
            return {'cacheFileBytes': self.bytes,
                    'cacheComplete': bool(self.total and not self.closed and not self.failed and self.bytes == self.total),
                    'preloadLimited': self.limited or self.failed,
                    'cacheKind': 'original-range-blocks'}

    def close(self):
        with self.guard:
            if not self.closed:
                self.closed = True
                self.file.close()
                self.entries.clear()


def preload(source, cache, stopped):
    """Sequential background fill shares the source's bounded request cache."""
    try:
        with source.reader(stopped, cache=cache) as reader:
            while reader.tell() < source.size and not stopped():
                index = reader.tell() // source.block_size
                length = min(source.block_size, source.size - reader.tell())
                if not cache.can_store(index, length):
                    return
                if not reader.read(length):
                    return
    except (OSError, InterruptedError):
        # Network failures remain source-read failures. Optional local cache
        # failure is reported separately and must not trigger H.264 fallback.
        return
