"""One owned external ASS track; ordinary position polls never replace it."""
from desktop_danmaku import DEFAULT_SETTINGS, validate_danmaku, validate_settings, ass_document, active_danmaku

class DanmakuTrack:
    def __init__(self, *, assets=None):
        self.assets = assets or {}
        self.items = []
        self.settings = dict(DEFAULT_SETTINGS)
        self.track_id = None
        self.document = ''
        self.dirty = False
        self.failed = False
        self.loads = 0

    def update(self, command):
        # Validate atomically: a bad field must not partially replace the schedule.
        items = validate_danmaku(command['danmaku']) if 'danmaku' in command else self.items
        settings = validate_settings(command['danmakuSettings']) if 'danmakuSettings' in command else self.settings
        if items != self.items or settings != self.settings:
            self.items, self.settings = items, settings
            self.dirty = True

    def source_reloaded(self):
        self.track_id, self.document, self.dirty = None, '', True

    def apply(self, player):
        if not self.dirty:
            return
        self.dirty = False
        try:
            document = ass_document(self.items, self.settings, assets=self.assets) if self.items else ''
            if document == self.document:
                return
            previous = self.track_id
            if document:
                player.command('sub-add', 'memory://' + document, 'select', 'Hongguo danmaku')
                selected = str(player.get('sid') or '')
                if not selected.isdigit():
                    raise RuntimeError('Native danmaku track unavailable')
                self.track_id = selected
                self.loads += 1
            else:
                self.track_id = None
            if previous and previous != self.track_id:
                player.command('sub-remove', previous)
            self.document, self.failed = document, False
        except (RuntimeError, ValueError, TypeError, KeyError):
            # Social rendering failure must not interrupt video or audio.
            self.failed = True

    def snapshot(self, seconds):
        return {'danmakuVisible': bool(self.track_id) and not self.failed and bool(active_danmaku(self.items, seconds, self.settings)),
                'danmakuFailed': self.failed, 'danmakuRenderer': 'ass-timeline',
                'danmakuLoads': self.loads, 'danmakuSettings': dict(self.settings)}
