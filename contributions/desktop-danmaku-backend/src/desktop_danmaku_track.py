"""One owned ASS track; ordinary position polls never replace it."""
import time
from desktop_danmaku import DEFAULT_SETTINGS, validate_danmaku, validate_settings, ass_document, active_danmaku

class DanmakuTrack:
    def __init__(self, *, assets=None, clock=time.monotonic):
        self.assets = assets or {}
        self.clock = clock
        self.items = []
        self.settings = dict(DEFAULT_SETTINGS)
        self.track_id = None
        self.document = ''
        self.dirty = False
        self.failed = False
        self.loads = 0
        self.saved = None
        self.promoted = False
        self.pending_removals = set()
        self.retry_at = 0

    def update(self, command):
        items = validate_danmaku(command['danmaku']) if 'danmaku' in command else self.items
        settings = validate_settings(command['danmakuSettings']) if 'danmakuSettings' in command else self.settings
        if items != self.items or settings != self.settings or self.failed:
            self.items, self.settings = items, settings
            self.dirty = True

    def source_reloaded(self):
        # Old IDs belong to the discarded file, never remove them in the new one.
        self.track_id, self.document, self.dirty = None, '', True
        self.saved = None
        self.promoted = False
        self.pending_removals.clear()
        self.retry_at = 0

    @staticmethod
    def selected(value):
        return str(value or '').isdigit() and int(value) > 0

    def preserve_captions(self, player):
        if self.saved is not None:
            return
        primary = player.get('sid') or 'no'
        secondary = player.get('secondary-sid') or 'no'
        if self.selected(primary) and self.selected(secondary):
            # mpv has two subtitle slots. Leave both user caption tracks intact.
            raise RuntimeError('Both subtitle slots are in use')
        self.saved = (primary, secondary, player.get('secondary-sub-ass-override') or 'strip')

    def show_captions(self, player):
        if self.saved is None or not self.selected(self.saved[0]):
            return
        primary = self.saved[0]
        secondary = player.get('secondary-sid') or 'no'
        if self.selected(secondary) and str(secondary) != str(primary):
            raise RuntimeError('Secondary subtitle slot changed')
        # mpv refuses the same track in both slots. Select the overlay first,
        # then move the saved caption; assigning it before sub-add loses it.
        self.promoted = True
        player.command('set', 'secondary-sub-ass-override', player.get('sub-ass-override') or 'scale')
        player.command('set', 'secondary-sid', primary)

    def restore_captions(self, player):
        if self.saved is None:
            return
        primary, secondary, override = self.saved
        if self.promoted and str(player.get('secondary-sid')) in (str(primary),str(secondary)):
            player.command('set', 'secondary-sid', secondary)
            player.command('set', 'secondary-sub-ass-override', override)
        if str(player.get('sid')) == str(self.track_id):
            player.command('set', 'sid', primary)

    def remove_pending(self, player):
        for identifier in tuple(self.pending_removals):
            player.command('sub-remove', identifier)
            self.pending_removals.remove(identifier)

    def apply(self, player):
        if not self.dirty or self.clock() < self.retry_at:
            return
        self.dirty = False
        try:
            self.remove_pending(player)
            document = ass_document(self.items, self.settings, assets=self.assets) if self.items else ''
            if document == self.document:
                if document: self.show_captions(player)
                self.failed = False
                return
            previous = self.track_id
            if document:
                self.preserve_captions(player)
                player.command('sub-add', 'memory://' + document, 'select', 'Hongguo danmaku')
                selected = str(player.get('sid') or '')
                if not selected.isdigit():
                    raise RuntimeError('Native danmaku track unavailable')
                self.track_id = selected
                self.loads += 1
                self.document = document
                if previous and previous != self.track_id:
                    self.pending_removals.add(previous)
                self.show_captions(player)
                if self.pending_removals:
                    self.remove_pending(player)
            else:
                self.restore_captions(player)
                # Keep the ID until removal succeeds, including transient errors.
                if previous:
                    player.command('sub-remove', previous)
                self.track_id, self.document, self.saved = None, '', None
                self.promoted = False
            self.failed = False
        except (RuntimeError, ValueError, TypeError, KeyError):
            # Retry on the video owner thread at most once a second; never stop A/V.
            self.failed = True
            self.dirty = True
            self.retry_at = self.clock() + 1

    def snapshot(self, seconds):
        return {'danmakuVisible': bool(self.track_id) and not self.failed and bool(active_danmaku(self.items, seconds, self.settings)),
                'danmakuFailed': self.failed, 'danmakuRenderer': 'ass-timeline',
                'danmakuLoads': self.loads, 'danmakuSettings': dict(self.settings)}
