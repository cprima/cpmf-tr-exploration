"""Playback — runtime session state, position, and intent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


@dataclass
class TransportState:
    """Snapshot of UPnP AVTransport state for one instance."""

    state: Literal[
        "STOPPED",
        "PLAYING",
        "PAUSED_PLAYBACK",
        "TRANSITIONING",
        "NO_MEDIA_PRESENT",
    ]
    status: str  # CurrentTransportStatus, e.g. "OK"
    rel_time: str | None = None  # HH:MM:SS
    track_duration: str | None = None  # HH:MM:SS or "NOT_IMPLEMENTED"
    current_uri: str | None = None

    @property
    def is_playing(self) -> bool:
        return self.state == "PLAYING"

    @property
    def is_stopped(self) -> bool:
        return self.state in {"STOPPED", "NO_MEDIA_PRESENT"}


@dataclass
class PlaybackPosition:
    """Precise playback position at a known wall-clock instant.

    rel_seconds   position within the current track
    abs_seconds   position within the full album/stream (if known)
    updated_at    UTC timestamp when this position was last confirmed

    Used for seeking, reconnect recovery, sync, and scrubbing display.
    """

    rel_seconds: float
    abs_seconds: float | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def age_seconds(self, now: datetime | None = None) -> float:
        """Seconds elapsed since this position was last confirmed."""
        t = now or datetime.now(UTC)
        return (t - self.updated_at).total_seconds()

    def estimated_rel_seconds(self, now: datetime | None = None) -> float:
        """Best-effort current position extrapolated from age (assumes no pausing)."""
        return self.rel_seconds + self.age_seconds(now)


@dataclass
class PlaybackIntent:
    """What the caller wants to happen — resolved into a PlaybackSession."""

    target_zone_id: str
    source_uri: str
    mode: Literal["auto", "live", "cached"]
    enqueue: bool = False
    replace_queue: bool = True
    title: str | None = None
    thumbnail_uri: str | None = None


@dataclass
class PlaybackSession:
    """Runtime playback state for one zone.

    Ties together: zone ↔ queue ↔ current item ↔ stream session.
    """

    id: str
    zone_id: str
    queue_id: str | None = None
    current_item_id: str | None = None
    stream_session_id: str | None = None
    state: Literal["idle", "starting", "transitioning", "playing", "paused", "stopped", "error"] = (
        "idle"
    )
    transport_state: TransportState | None = None
    position: PlaybackPosition | None = None
    error_message: str | None = None

    @property
    def is_active(self) -> bool:
        return self.state in {"starting", "transitioning", "playing", "paused"}
