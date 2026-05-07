"""QueueManager — queue state and item resolution for a single zone.

Owns:
- Enqueue (probe → MediaItem → CacheEntry → QueueItem)
- Queue navigation (skip_next, skip_previous)
- Item resolution (cached path or live URL)
- Queue mode flags (repeat, shuffle)

Does NOT own:
- HTTP session lifecycle (→ StreamManager)
- SOAP control (→ PlaybackManager)
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from cprima_raumtube.model.aggregates import LibraryAggregate, new_id
from cprima_raumtube.model.media import Library, MediaItem, QueueItem, QueueItemState
from cprima_raumtube.model.streaming import CacheEntry

if TYPE_CHECKING:
    from cprima_raumtube.config import Config
    from cprima_raumtube.model.registry import Installation

_log = logging.getLogger(__name__)

_DEFAULT_LIB_ID = "default"
_DEFAULT_LIB_NAME = "Default Library"
_YT_RE = re.compile(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})")


def _canonical_id(url: str) -> str:
    m = _YT_RE.search(url)
    if m:
        return f"youtube:{m.group(1)}"
    h = hashlib.sha1(url.encode()).hexdigest()[:10]
    return f"radio:{h}"


def _is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def _ensure_default_lib(library: LibraryAggregate) -> Library:
    lib = library.libraries.get(_DEFAULT_LIB_ID)
    if lib is None:
        lib = Library(id=_DEFAULT_LIB_ID, name=_DEFAULT_LIB_NAME)
        library.libraries[lib.id] = lib
    return lib


class QueueManager:
    def __init__(self, installation: Installation, config: Config) -> None:
        self._installation = installation
        self._config = config

    # ── Enqueue ───────────────────────────────────────────────────────────────

    def enqueue(
        self,
        zone_id: str,
        source_url: str,
        mode: Literal["auto", "live", "cached"] = "auto",
        replace: bool = False,
    ) -> MediaItem:
        """Probe URL → create/find MediaItem → append QueueItem. Returns MediaItem."""
        canonical = _canonical_id(source_url)
        lib = _ensure_default_lib(self._installation.library)

        # Check if already in library
        item = self._installation.library.find_by_canonical(canonical)

        if item is None:
            item = self._probe_and_create(source_url, canonical, lib, mode)

        # Download to cache for YouTube non-live items
        if _is_youtube(source_url) and mode != "live":
            self._ensure_cached(source_url, item)

        # Build QueueItem
        queue = self._installation.state.get_or_create_queue(zone_id)
        if replace:
            queue.clear()

        qi = QueueItem(id=new_id(), media_item_id=item.id, state=QueueItemState.RESOLVED)
        queue.enqueue(qi)

        _log.info(
            "[queue] enqueued %r (zone=%s index=%s)", item.title, zone_id, queue.current_index
        )
        return item

    def _probe_and_create(
        self,
        source_url: str,
        canonical: str,
        lib: Library,
        mode: Literal["auto", "live", "cached"],
    ) -> MediaItem:
        if _is_youtube(source_url):
            from cprima_raumtube.sources import youtube as yt

            _log.info("[queue] probing %s", source_url)
            info = yt.probe(source_url)
            live = yt.is_live_stream(info) or mode == "live"
            item = MediaItem(
                id=new_id(),
                source_id=_DEFAULT_LIB_ID,
                title=info.get("title", source_url),
                canonical_id=canonical,
                source_locator=source_url,
                media_type="livestream" if live else "track",
                duration_seconds=info.get("duration"),
                content_type="audio/mpeg",
                seekable=not live,
                uploader=info.get("uploader"),
                thumbnail_uri=info.get("thumbnail"),
            )
        else:
            # Radio / generic HTTP stream — no probing needed
            # mode="live" forces ffmpeg proxy (live_pipe); default "auto" tries direct_url first
            item = MediaItem(
                id=new_id(),
                source_id=_DEFAULT_LIB_ID,
                title=source_url,
                canonical_id=canonical,
                source_locator=source_url,
                media_type="livestream" if mode == "live" else "broadcast",
                seekable=False,
                content_type="audio/mpeg",
            )

        lib.add_item(item)
        return item

    def _ensure_cached(self, source_url: str, item: MediaItem) -> None:
        """Download to cache if not already present. Updates library.cache_entries."""
        for entry in self._installation.library.cache_entries.values():
            if entry.media_item_id == item.id and Path(entry.path).exists():
                _log.info("[queue] cache hit: %s", entry.path)
                return

        from cprima_raumtube.services import cache_service
        from cprima_raumtube.sources import youtube as yt

        _log.info("[queue] downloading to cache: %r", item.title)
        info = yt.probe(source_url)
        path = yt.download_to_cache(source_url, info, self._config.cache_dir)
        entry = CacheEntry(
            id=new_id(),
            media_item_id=item.id,
            path=str(path),
            content_type="audio/mpeg",
            size_bytes=path.stat().st_size,
            duration_seconds=info.get("duration"),
        )
        self._installation.library.cache_entries[entry.id] = entry
        cache_service.save_index(self._installation.library, self._config.cache_dir)
        _log.info("[queue] cached: %s (%.1f MB)", path.name, path.stat().st_size / 1_048_576)

    # ── Resolution ────────────────────────────────────────────────────────────

    def resolve_item(
        self, queue_item: QueueItem
    ) -> tuple[Path | str, Literal["cached_file", "live_pipe", "direct_url"]]:
        """Return (stream_source, mode) for a QueueItem.

        cached_file → (Path to MP3 on disk, "cached_file")
        direct_url  → (source URL, "direct_url")   broadcast/radio — renderer fetches directly
        live_pipe   → (source URL, "live_pipe")     livestream — proxied through local ffmpeg
        """
        media_item = self._installation.library.find_item(queue_item.media_item_id)
        if media_item is None:
            raise KeyError(f"MediaItem {queue_item.media_item_id!r} not found in library")

        # Check cache first (always wins regardless of media type)
        for entry in self._installation.library.cache_entries.values():
            if entry.media_item_id == media_item.id:
                p = Path(entry.path)
                if p.exists():
                    return p, "cached_file"

        # Broadcast/radio: renderer can reach the source URL directly
        if media_item.media_type == "broadcast":
            return media_item.source_locator, "direct_url"

        # Livestream and anything else: pipe through local ffmpeg
        return media_item.source_locator, "live_pipe"

    # ── Navigation ────────────────────────────────────────────────────────────

    def skip_next(self, zone_id: str) -> QueueItem | None:
        queue = self._installation.state.get_or_create_queue(zone_id)
        return queue.advance()

    def skip_previous(self, zone_id: str) -> QueueItem | None:
        queue = self._installation.state.get_or_create_queue(zone_id)
        return queue.rewind()

    def clear(self, zone_id: str) -> None:
        queue = self._installation.state.get_or_create_queue(zone_id)
        queue.clear()

    # ── Mode flags ────────────────────────────────────────────────────────────

    def set_repeat(self, zone_id: str, mode: Literal["off", "one", "all"]) -> None:
        self._installation.state.get_or_create_queue(zone_id).repeat_mode = mode

    def set_shuffle(self, zone_id: str, on: bool) -> None:
        self._installation.state.get_or_create_queue(zone_id).shuffle_mode = on
