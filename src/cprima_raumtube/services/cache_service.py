"""Persistent cache index — MediaItem, CacheEntry, and AppQueue serialization.

MediaResolution is intentionally excluded (ephemeral; expires within hours).
CacheEntry.path is validated on load; entries for missing files are dropped.
AppQueue state (items + current_index) survives across CLI invocations.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from cprima_raumtube.model.media import AppQueue, Library, MediaItem, QueueItem, QueueItemState
from cprima_raumtube.model.streaming import CacheEntry

if TYPE_CHECKING:
    from cprima_raumtube.model.aggregates import LibraryAggregate, RuntimeAggregate

_log = logging.getLogger(__name__)

_INDEX_VERSION = 1
_DEFAULT_LIB_ID = "default"
_DEFAULT_LIB_NAME = "Default Library"


def _index_path(cache_dir: Path) -> Path:
    return cache_dir / "index.json"


def save_index(library: LibraryAggregate, cache_dir: Path) -> None:
    """Serialize MediaItems and CacheEntries to cache_dir/index.json."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    items = [
        {
            "id": item.id,
            "source_id": item.source_id,
            "title": item.title,
            "canonical_id": item.canonical_id,
            "source_locator": item.source_locator,
            "media_type": item.media_type,
            "duration_seconds": item.duration_seconds,
            "content_type": item.content_type,
            "seekable": item.seekable,
            "uploader": item.uploader,
            "thumbnail_uri": item.thumbnail_uri,
        }
        for lib in library.libraries.values()
        for item in lib.items.values()
    ]
    entries = [
        {
            "id": entry.id,
            "media_item_id": entry.media_item_id,
            "path": str(entry.path),
            "content_type": entry.content_type,
            "size_bytes": entry.size_bytes,
            "duration_seconds": entry.duration_seconds,
        }
        for entry in library.cache_entries.values()
    ]
    payload = {"version": _INDEX_VERSION, "media_items": items, "cache_entries": entries}
    path = _index_path(cache_dir)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _log.debug("cache index saved: %d items, %d entries → %s", len(items), len(entries), path)


def load_index(library: LibraryAggregate, cache_dir: Path) -> None:
    """Restore MediaItems and CacheEntries from cache_dir/index.json into library (merge)."""
    path = _index_path(cache_dir)
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _log.warning("could not read cache index %s: %s", path, exc)
        return

    lib = library.libraries.get(_DEFAULT_LIB_ID)
    if lib is None:
        lib = Library(id=_DEFAULT_LIB_ID, name=_DEFAULT_LIB_NAME)
        library.libraries[lib.id] = lib

    loaded_items = 0
    for raw in payload.get("media_items", []):
        try:
            item = MediaItem(
                id=raw["id"],
                source_id=raw.get("source_id", _DEFAULT_LIB_ID),
                title=raw["title"],
                canonical_id=raw["canonical_id"],
                source_locator=raw["source_locator"],
                media_type=raw["media_type"],
                duration_seconds=raw.get("duration_seconds"),
                content_type=raw.get("content_type"),
                seekable=raw.get("seekable", True),
                uploader=raw.get("uploader"),
                thumbnail_uri=raw.get("thumbnail_uri"),
            )
            lib.items[item.id] = item
            loaded_items += 1
        except Exception as exc:
            _log.warning("skipping malformed media_item entry: %s", exc)

    loaded_entries = 0
    for raw in payload.get("cache_entries", []):
        try:
            p = Path(raw["path"])
            if not p.exists():
                _log.debug("dropping cache entry for missing file: %s", p)
                continue
            entry = CacheEntry(
                id=raw["id"],
                media_item_id=raw["media_item_id"],
                path=str(p),
                content_type=raw.get("content_type", "audio/mpeg"),
                size_bytes=raw["size_bytes"],
                duration_seconds=raw.get("duration_seconds"),
            )
            library.cache_entries[entry.id] = entry
            loaded_entries += 1
        except Exception as exc:
            _log.warning("skipping malformed cache_entry: %s", exc)

    _log.debug(
        "cache index loaded: %d items, %d entries from %s", loaded_items, loaded_entries, path
    )


# ── AppQueue persistence ─────────────────────────────────────────────────────────

_QUEUES_FILE = "queues.json"
_QUEUES_VERSION = 1


def _queues_path(cache_dir: Path) -> Path:
    return cache_dir / _QUEUES_FILE


def save_queue(queue: AppQueue, cache_dir: Path) -> None:
    """Persist a single zone queue to cache_dir/queues.json (merge with existing zones)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _queues_path(cache_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        data = {}
    data.setdefault("version", _QUEUES_VERSION)
    data.setdefault("queues", {})
    data["queues"][queue.zone_id] = {
        "id": queue.id,
        "zone_id": queue.zone_id,
        "current_index": queue.current_index,
        "repeat_mode": queue.repeat_mode,
        "shuffle_mode": queue.shuffle_mode,
        "queue_end_behavior": queue.queue_end_behavior,
        "items": [
            {"id": qi.id, "media_item_id": qi.media_item_id, "state": qi.state}
            for qi in queue.items
        ],
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _log.debug("queue saved: zone=%s %d items", queue.zone_id, len(queue.items))


def load_queue(playback: RuntimeAggregate, zone_id: str, cache_dir: Path) -> AppQueue:
    """Load (or create) the persisted queue for zone_id into playback aggregate."""
    path = _queues_path(cache_dir)
    queue = playback.get_or_create_queue(zone_id)
    if not path.exists():
        return queue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("queues", {}).get(zone_id)
        if raw is None:
            return queue
        queue.id = raw.get("id", queue.id)
        queue.current_index = raw.get("current_index")
        queue.repeat_mode = raw.get("repeat_mode", "off")
        queue.shuffle_mode = raw.get("shuffle_mode", False)
        queue.queue_end_behavior = raw.get("queue_end_behavior", "stop")
        queue.replace_all([
            QueueItem.rehydrate(
                id=qi["id"],
                media_item_id=qi["media_item_id"],
                state=QueueItemState(qi.get("state", "pending")),
            )
            for qi in raw.get("items", [])
        ])
        _log.debug("queue loaded: zone=%s %d items", zone_id, len(queue.items))
    except Exception as exc:
        _log.warning("could not read queue for zone %s: %s", zone_id, exc)
    return queue


def clear_queue(zone_id: str, cache_dir: Path) -> None:
    """Remove the persisted queue entry for zone_id."""
    path = _queues_path(cache_dir)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.get("queues", {}).pop(zone_id, None)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        _log.warning("could not clear queue for zone %s: %s", zone_id, exc)
