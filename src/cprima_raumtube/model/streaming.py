"""Streaming data models — session descriptors and cache entries.

These are *data* classes describing stream state.
The HTTP server implementation lives in cprima_raumtube.streaming.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class TranscodeProfile:
    """Audio transcode settings.  Not yet implemented — stub only."""

    id: str
    codec: str  # e.g. "mp3", "aac", "opus"
    bitrate_kbps: int
    container: str  # e.g. "mp3", "ogg", "m4a"
    sample_rate_hz: int | None = None
    channels: int | None = None

    def __post_init__(self) -> None:
        raise NotImplementedError("TranscodeProfile is not yet implemented")


@dataclass
class StreamSession:
    """Descriptor for an active or completed stream delivery.

    mode:
      cached_file  — static MP3 served with Range support (seekable)
      live_pipe    — ffmpeg stdout piped to HTTP (no seeking)
      direct_url   — renderer fetches the source URL directly

    state lifecycle:
      starting → active → draining → closed
                                   → failed  (from any state)
    """

    id: str
    media_item_id: str
    mode: Literal["cached_file", "live_pipe", "direct_url"]
    public_url: str
    content_type: str
    seekable: bool
    range_supported: bool
    state: Literal["starting", "active", "draining", "closed", "failed"] = "starting"
    local_path: str | None = None

    @property
    def is_alive(self) -> bool:
        return self.state in {"starting", "active", "draining"}


@dataclass
class CacheEntry:
    """A fully downloaded and transcoded file on local disk."""

    id: str
    media_item_id: str
    path: str
    content_type: str
    size_bytes: int
    duration_seconds: int | None = None
