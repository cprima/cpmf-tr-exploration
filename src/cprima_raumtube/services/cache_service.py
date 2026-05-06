"""Persistent cache index — MediaItem and CacheEntry serialization.

MediaResolution is intentionally excluded (ephemeral; expires within hours).
CacheEntry.path is validated on load; entries for missing files are dropped.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cprima_raumtube.model.aggregates import LibraryAggregate  # noqa: F401 (type only)
from cprima_raumtube.model.media import Library, MediaItem
from cprima_raumtube.model.streaming import CacheEntry

_log = logging.getLogger(__name__)

_INDEX_VERSION = 1
_DEFAULT_LIB_ID = "default"
_DEFAULT_LIB_NAME = "Default Library"


def _index_path(cache_dir: Path) -> Path:
    return cache_dir / "index.json"


def save_index(library: LibraryAggregate, cache_dir: Path) -> None:
    """Serialize MediaItems and CacheEntries to cache_dir/index.json."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for lib in library.libraries.values():
        for item in lib.items.values():
            items.append(
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
            )
    entries = []
    for entry in library.cache_entries.values():
        entries.append(
            {
                "id": entry.id,
                "media_item_id": entry.media_item_id,
                "path": str(entry.path),
                "content_type": entry.content_type,
                "size_bytes": entry.size_bytes,
                "duration_seconds": entry.duration_seconds,
            }
        )
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
