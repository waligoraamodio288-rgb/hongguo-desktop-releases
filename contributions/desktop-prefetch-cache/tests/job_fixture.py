"""Minimal test consumer of the prefetch job contract."""
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

@dataclass
class Job:
    id: str
    directory: Path
    cancelled: Event = field(default_factory=Event)
    ready: Event = field(default_factory=Event)
    failed: bool = False
    start_seconds: float = 0
