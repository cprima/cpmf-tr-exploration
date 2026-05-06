"""Media — library, items, playlists, resolutions, and per-zone queues."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# Playback mode flags for Queue
QueueOrigin = Literal["ad_hoc", "playlist", "radio", "autoplay"]


@dataclass
class LibrarySource:
    """A browsable/resolvable audio origin."""

    id: str
    kind: Literal["youtube", "http", "radio", "local_file", "dlna", "raumfeld_media_server"]
    name: str
    root_uri: str | None = None


@dataclass
class MediaItem:
    """A single playable item with stable identity and optional ephemeral resolution.

    Identity fields
    ---------------
    canonical_id    Stable opaque key: ``"youtube:mAKxcNQpiSg"``,
                    ``"radio:somafm:groovesalad"``, ``"file:/path/to.mp3"``
    source_locator  Stable user-facing URL: ``"https://youtube.com/watch?v=mAKxcNQpiSg"``

    Resolution field
    ----------------
    resolved_uri    Ephemeral direct stream URL.  May be None (not yet resolved)
                    or stale (YouTube URLs expire after a few hours).
                    Always check MediaResolution for authoritative, time-bounded values.
    """

    id: str
    source_id: str
    title: str
    canonical_id: str  # e.g. "youtube:mAKxcNQpiSg"
    source_locator: str  # stable user-visible URL or path
    media_type: Literal["track", "broadcast", "livestream", "playlist", "album"]
    resolved_uri: str | None = None  # ephemeral — may expire
    duration_seconds: int | None = None
    thumbnail_uri: str | None = None
    seekable: bool = True
    content_type: str | None = None
    uploader: str | None = None


@dataclass
class MediaResolution:
    """Authoritative, time-bounded resolution of a MediaItem to a stream URI.

    Separate from MediaItem because resolved URIs are ephemeral (YouTube
    direct URLs expire in hours) and must be refreshed independently.
    """

    id: str
    media_item_id: str
    resolved_uri: str
    resolver: Literal["yt-dlp", "direct", "cache", "radio"]
    expires_at: datetime | None = None
    content_type: str | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        t = now or datetime.now(self.expires_at.tzinfo)
        return t >= self.expires_at

    def is_valid(self, now: datetime | None = None) -> bool:
        return not self.is_expired(now)


@dataclass
class Library:
    """Browsable media universe — a named collection of sources and cached items."""

    id: str
    name: str
    sources: list[LibrarySource] = field(default_factory=list)
    items: dict[str, MediaItem] = field(default_factory=dict)

    def add_source(self, source: LibrarySource) -> None:
        self.sources.append(source)

    def add_item(self, item: MediaItem) -> None:
        self.items[item.id] = item

    def find_by_canonical(self, canonical_id: str) -> MediaItem | None:
        for item in self.items.values():
            if item.canonical_id == canonical_id:
                return item
        return None


@dataclass
class MediaItemRef:
    """Ordered reference to a MediaItem within a playlist."""

    item_id: str
    position: int


@dataclass
class Playlist:
    """Ordered, saved collection of media item references."""

    id: str
    name: str
    items: list[MediaItemRef] = field(default_factory=list)
    source_id: str | None = None


@dataclass
class QueueItem:
    """One slot in the active playback queue for a zone.

    References the MediaItem by ID to avoid embedding a mutable object graph.
    Resolve via LibraryAggregate.find_item() or System.library.
    """

    id: str
    media_item_id: str  # resolve through library — not embedded
    resolved_stream_id: str | None = None
    state: Literal["pending", "resolved", "playing", "played", "failed"] = "pending"


@dataclass
class Queue:
    """Active playback list for a zone.  Mutable during playback.

    Mode flags
    ----------
    repeat_mode   off | one | all
    shuffle_mode  randomise playback order
    consume_mode  remove item from queue after it finishes (radio-style)
    crossfade     request gapless transition (requires SetNextAVTransportURI)
    origin        how this queue was created
    """

    id: str
    zone_id: str
    items: list[QueueItem] = field(default_factory=list)
    current_index: int | None = None
    repeat_mode: Literal["off", "one", "all"] = "off"
    shuffle_mode: bool = False
    consume_mode: bool = False
    crossfade: bool = False
    origin: QueueOrigin = "ad_hoc"

    @property
    def current_item(self) -> QueueItem | None:
        if self.current_index is None or not self.items:
            return None
        return self.items[self.current_index]

    @property
    def has_next(self) -> bool:
        if not self.items or self.current_index is None:
            return False
        if self.repeat_mode == "all":
            return True
        return self.current_index < len(self.items) - 1

    def append(self, item: QueueItem) -> None:
        self.items.append(item)

    def clear(self) -> None:
        self.items.clear()
        self.current_index = None
