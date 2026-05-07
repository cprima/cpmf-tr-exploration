"""Media — library, items, playlists, resolutions, and per-zone queues."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cprima_raumtube.model.ids import MediaItemId, QueueId, ZoneId

QueueOrigin = Literal["ad_hoc", "playlist", "radio", "autoplay"]
QueueEndBehavior = Literal["stop", "clear", "idle"]


class QueueItemState(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    PLAYING = "playing"
    PLAYED = "played"
    FAILED = "failed"


class InsertMode(StrEnum):
    APPEND = "append"            # add after last item
    PLAY_NEXT = "play_next"      # insert immediately after current index
    REPLACE_REMAINING = "replace_remaining"  # discard items after current, then append


class ReconciliationState(StrEnum):
    CLEAN = "clean"
    DIRTY = "dirty"
    RECONCILING = "reconciling"
    DIVERGED = "diverged"


@dataclass(slots=True)
class LibrarySource:
    """A browsable/resolvable audio origin."""

    id: str
    kind: Literal["youtube", "http", "radio", "local_file", "dlna", "raumfeld_media_server"]
    name: str
    root_uri: str | None = None


@dataclass(frozen=True, slots=True)
class MediaItem:
    """A single playable item with stable identity and optional ephemeral resolution.

    Identity fields
    ---------------
    canonical_id    Stable opaque key: ``"youtube:mAKxcNQpiSg"``,
                    ``"radio:somafm:groovesalad"``, ``"file:/path/to.mp3"``
    source_locator  Stable user-facing URL or path (never expires).

    Ephemeral resolution (stream URI) lives in MediaResolution only --
    not here.  Two sources of truth is the bug, not the fix.
    """

    id: MediaItemId
    source_id: str
    title: str
    canonical_id: str  # e.g. "youtube:mAKxcNQpiSg"
    source_locator: str  # stable user-visible URL or path
    media_type: Literal["track", "broadcast", "livestream", "playlist", "album"]
    duration_seconds: int | None = None
    thumbnail_uri: str | None = None
    seekable: bool = True
    content_type: str | None = None
    uploader: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("MediaItem.id must not be empty")
        if not self.title:
            raise ValueError("MediaItem.title must not be empty")
        if not self.canonical_id:
            raise ValueError("MediaItem.canonical_id must not be empty")
        if not self.source_locator:
            raise ValueError("MediaItem.source_locator must not be empty")


@dataclass(slots=True)
class MediaResolution:
    """Authoritative, time-bounded resolution of a MediaItem to a stream URI.

    Separate from MediaItem because resolved URIs are ephemeral (YouTube
    direct URLs expire in hours) and must be refreshed independently.
    """

    id: str
    media_item_id: MediaItemId
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


@dataclass(slots=True)
class Library:
    """Browsable media universe — a named collection of sources and cached items."""

    id: str
    name: str
    sources: list[LibrarySource] = field(default_factory=list)
    items: dict[MediaItemId, MediaItem] = field(default_factory=dict)

    def add_source(self, source: LibrarySource) -> None:
        self.sources.append(source)

    def add_item(self, item: MediaItem) -> None:
        self.items[item.id] = item

    def find_by_canonical(self, canonical_id: str) -> MediaItem | None:
        for item in self.items.values():
            if item.canonical_id == canonical_id:
                return item
        return None


@dataclass(frozen=True, slots=True)
class MediaItemRef:
    """Ordered reference to a MediaItem within a playlist."""

    item_id: str
    position: int


@dataclass(slots=True)
class Playlist:
    """Ordered, saved collection of media item references."""

    id: str
    name: str
    items: list[MediaItemRef] = field(default_factory=list)
    source_id: str | None = None


@dataclass(slots=True)
class QueueItem:
    """One slot in the active playback queue for a zone.

    References the MediaItem by ID to avoid embedding a mutable object graph.
    Resolve via LibraryAggregate.find_item() or System.library.
    """

    id: str
    media_item_id: MediaItemId  # resolve through library — not embedded
    resolved_stream_id: str | None = None
    state: QueueItemState = QueueItemState.PENDING


@dataclass(slots=True)
class AppQueue:
    """Active playback list owned by the application for a zone.

    Distinct from DeviceQueueSnapshot: this is what *we* want to play,
    not necessarily what the device currently has loaded.

    Mode flags
    ----------
    repeat_mode   off | one | all
    shuffle_mode  randomise playback order
    consume_mode  remove item from queue after it finishes (radio-style)
    crossfade     request gapless transition (requires SetNextAVTransportURI)
    origin        how this queue was created
    """

    id: QueueId
    zone_id: ZoneId
    _items: list[QueueItem] = field(default_factory=list, init=False, repr=False)
    current_index: int | None = None
    repeat_mode: Literal["off", "one", "all"] = "off"
    shuffle_mode: bool = False
    consume_mode: bool = False
    crossfade: bool = False
    origin: QueueOrigin = "ad_hoc"
    queue_end_behavior: QueueEndBehavior = "stop"
    version: int = 0

    def __post_init__(self) -> None:
        if self.current_index is not None and self.current_index >= 0:
            pass
        elif self.current_index is not None and self.current_index < 0:
            raise ValueError(f"current_index must be >= 0, got {self.current_index}")

    @property
    def items(self) -> tuple[QueueItem, ...]:
        return tuple(self._items)

    @property
    def current_item(self) -> QueueItem | None:
        if self.current_index is None or not self._items:
            return None
        return self._items[self.current_index]

    @property
    def has_next(self) -> bool:
        if not self._items or self.current_index is None:
            return False
        if self.repeat_mode == "all":
            return True
        return self.current_index < len(self._items) - 1

    def enqueue(self, item: QueueItem, mode: InsertMode = InsertMode.APPEND) -> None:
        """Insert item into queue per mode, set current_index if queue was empty, increment version."""
        if mode == InsertMode.PLAY_NEXT:
            insert_at = (self.current_index + 1) if self.current_index is not None else 0
            self._items.insert(insert_at, item)
        elif mode == InsertMode.REPLACE_REMAINING:
            cut = (self.current_index + 1) if self.current_index is not None else 0
            del self._items[cut:]
            self._items.append(item)
        else:  # APPEND
            self._items.append(item)
        if self.current_index is None and self._items:
            self.current_index = 0
        self.version += 1

    def append(self, item: QueueItem) -> None:
        """Backward-compat alias for enqueue with APPEND mode."""
        self.enqueue(item)

    def advance(self) -> QueueItem | None:
        """Advance to the next item per repeat_mode. Returns new current item, or None at queue end."""
        if not self._items or self.current_index is None:
            return None
        if self.repeat_mode == "one":
            return self.current_item
        if self.current_index < len(self._items) - 1:
            self.current_index += 1
            self.version += 1
            return self.current_item
        if self.repeat_mode == "all":
            self.current_index = 0
            self.version += 1
            return self.current_item
        return None

    def rewind(self) -> QueueItem | None:
        """Move to previous item. Returns new current item, or None if already at start."""
        if not self._items or self.current_index is None or self.current_index == 0:
            return None
        self.current_index -= 1
        self.version += 1
        return self.current_item

    def seek_to(self, idx: int) -> QueueItem:
        """Jump to item at idx (0-based). Raises IndexError if out of range."""
        if idx < 0 or idx >= len(self._items):
            raise IndexError(f"Queue index {idx} out of range (len={len(self._items)})")
        self.current_index = idx
        self.version += 1
        return self._items[idx]

    def update_item_state(self, item_id: str, state: QueueItemState) -> None:
        """Update the state of an item by id. Raises KeyError if not found."""
        for item in self._items:
            if item.id == item_id:
                item.state = state
                self.version += 1
                return
        raise KeyError(f"QueueItem {item_id!r} not found in queue")

    def mark_played(self, item_id: str) -> None:
        self.update_item_state(item_id, QueueItemState.PLAYED)

    def mark_failed(self, item_id: str) -> None:
        self.update_item_state(item_id, QueueItemState.FAILED)

    def clear(self) -> None:
        self._items.clear()
        self.current_index = None
        self.version += 1

    def replace_all(self, items: Iterable[QueueItem]) -> None:
        """Replace all items; resets current_index to 0 if items non-empty, else None."""
        self._items = list(items)
        self.current_index = 0 if self._items else None
        self.version += 1

    def remove_at(self, idx: int) -> QueueItem:
        """Remove item at idx; adjusts current_index. Raises IndexError if out of range."""
        if idx < 0 or idx >= len(self._items):
            raise IndexError(f"Queue index {idx} out of range (len={len(self._items)})")
        removed = self._items.pop(idx)
        if self.current_index is not None:
            if self.current_index > idx:
                self.current_index -= 1
            elif self.current_index == idx:
                self.current_index = idx if idx < len(self._items) else None
        if not self._items:
            self.current_index = None
        self.version += 1
        return removed


@dataclass(slots=True)
class DeviceQueueSnapshot:
    """Point-in-time snapshot of what the device currently has loaded/queued.

    Read from the device via AVTransport GetMediaInfo or ContentDirectory queries.
    Not necessarily in sync with AppQueue — compare via QueueSyncState.
    id is referenced by QueueSyncState.last_device_snapshot_id.
    """

    id: str
    zone_id: ZoneId
    uris: list[str] = field(default_factory=list)
    current_uri: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class QueueSyncState:
    """Sync status between the application AppQueue and the device's loaded content.

    pending_push        AppQueue items not yet sent to the device
    failed_push         consecutive push failures (reset on success)
    device_differs      True when the device's loaded URIs don't match AppQueue
    last_device_snapshot_id  ID of the DeviceQueueSnapshot used in last comparison
    reconciliation      current reconciliation lifecycle state
    """

    zone_id: ZoneId
    in_sync: bool = False
    last_synced_at: datetime | None = None
    pending_push: int = 0
    failed_push: int = 0
    device_differs: bool = False
    last_device_snapshot_id: str | None = None
    reconciliation: ReconciliationState = ReconciliationState.CLEAN
