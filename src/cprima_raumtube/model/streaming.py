"""Streaming data models — session descriptors and cache entries.

These are *data* classes describing stream state.
The HTTP server implementation lives in cprima_raumtube.streaming.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from cprima_raumtube.model.ids import MediaItemId, StreamSessionId


@dataclass(slots=True)
class TranscodeProfile:
    """Audio transcode settings.

    implemented=False marks this as a stub; service code should check before use.
    """

    id: str
    codec: str  # e.g. "mp3", "aac", "opus"
    bitrate_kbps: int
    container: str  # e.g. "mp3", "ogg", "m4a"
    sample_rate_hz: int | None = None
    channels: int | None = None
    implemented: bool = False


class StreamSessionState(StrEnum):
    STARTING = "starting"
    ACTIVE = "active"
    DRAINING = "draining"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass(slots=True)
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

    id: StreamSessionId
    media_item_id: MediaItemId
    mode: Literal["cached_file", "live_pipe", "direct_url"]
    public_url: str
    content_type: str
    seekable: bool
    range_supported: bool
    state: StreamSessionState = StreamSessionState.STARTING
    local_path: str | None = None

    @property
    def is_alive(self) -> bool:
        return self.state in {
            StreamSessionState.STARTING,
            StreamSessionState.ACTIVE,
            StreamSessionState.DRAINING,
        }


@dataclass(slots=True)
class CacheEntry:
    """A fully downloaded and transcoded file on local disk."""

    id: str
    media_item_id: MediaItemId
    path: str
    content_type: str
    size_bytes: int
    duration_seconds: int | None = None
