"""Playback — runtime session state, position, intent, and zone device state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from cprima_raumtube.model.ids import MediaItemId, QueueId, StreamSessionId, ZoneId


class TransportStateName(StrEnum):
    """UPnP AVTransport transport state values.

    StrEnum so values compare equal to plain strings (backward compatible)
    while giving enum safety for mypy and IDE autocomplete.
    """

    STOPPED = "STOPPED"
    PLAYING = "PLAYING"
    PAUSED_PLAYBACK = "PAUSED_PLAYBACK"
    TRANSITIONING = "TRANSITIONING"
    NO_MEDIA_PRESENT = "NO_MEDIA_PRESENT"


class PlaybackSessionState(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    TRANSITIONING = "transitioning"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class PlaybackFailureKind(StrEnum):
    """Taxonomy of playback failures — guides retry policy and error reporting."""

    NETWORK = "network"
    RESOLUTION = "resolution"
    DEVICE_REJECTED = "device_rejected"
    UNSUPPORTED_FORMAT = "unsupported_format"
    DRM = "drm"
    TIMEOUT = "timeout"


@dataclass(slots=True)
class TransportState:
    """Snapshot of UPnP AVTransport state for one instance."""

    state: TransportStateName
    status: str  # CurrentTransportStatus, e.g. "OK"
    rel_time: str | None = None  # HH:MM:SS
    track_duration: str | None = None  # HH:MM:SS or "NOT_IMPLEMENTED"
    current_uri: str | None = None

    @property
    def is_playing(self) -> bool:
        return self.state == TransportStateName.PLAYING

    @property
    def is_stopped(self) -> bool:
        return self.state in {TransportStateName.STOPPED, TransportStateName.NO_MEDIA_PRESENT}


@dataclass(slots=True)
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

    def __post_init__(self) -> None:
        if self.rel_seconds < 0:
            raise ValueError(f"rel_seconds must be >= 0, got {self.rel_seconds}")

    def age_seconds(self, now: datetime | None = None) -> float:
        """Seconds elapsed since this position was last confirmed."""
        t = now or datetime.now(UTC)
        return (t - self.updated_at).total_seconds()

    def estimated_rel_seconds(self, playing: bool = True, now: datetime | None = None) -> float:
        """Best-effort current position, only extrapolated when actively playing."""
        return self.rel_seconds + self.age_seconds(now) if playing else self.rel_seconds


@dataclass(slots=True)
class RenderingState:
    """Current volume and mute snapshot for a zone.

    Keyed by channel name (e.g. 'Master', 'LF', 'RF').
    Populated from RenderingControl polling or GENA events.
    """

    volume: dict[str, int] = field(default_factory=dict)     # channel -> 0-100
    mute: dict[str, bool] = field(default_factory=dict)      # channel -> muted
    volume_db: dict[str, int] = field(default_factory=dict)  # channel -> mDB


@dataclass(slots=True)
class CurrentItemMetadata:
    """Human-readable metadata for the item currently playing on the device.

    Populated from AVTransport GetPositionInfo/GetMediaInfo DIDL-Lite responses
    or from GENA LastChange events. Stored separately from MediaItem so it can
    be updated without touching the library when the device reports new data.
    """

    title: str | None = None
    artist: str | None = None
    album: str | None = None
    item_class: str | None = None       # DIDL-Lite upnp:class
    album_art_uri: str | None = None
    current_uri: str | None = None
    raw_didl: str | None = None


@dataclass(slots=True)
class DesiredTransportState:
    """What the application intends the transport to be doing.

    Separate from ZoneRuntimeState.transport (observed) — enables retry,
    reconciliation, and eventual consistency without polluting observed state.

    requested_at  when this intent was set (for timeout/staleness checks)
    """

    target_state: TransportStateName
    desired_item_id: MediaItemId | None = None
    desired_position_seconds: float | None = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ZoneRuntimeState:
    """Current device state for one zone — transport, rendering, and position.

    Populated from polling or GENA events. Separate from PlaybackSession
    (which records one app-initiated playback attempt) and AppQueue
    (which tracks what the app wants to play next).

    Volume/mute live here, not in PlaybackSession, because rendering state
    exists independently of any active playback session.
    """

    zone_id: ZoneId
    transport: TransportState | None = None
    rendering: RenderingState = field(default_factory=RenderingState)
    position: PlaybackPosition | None = None
    current_metadata: CurrentItemMetadata | None = None
    desired: DesiredTransportState | None = None
    updated_at: datetime | None = None
    version: int = 0


@dataclass(frozen=True, slots=True)
class PlaybackIntent:
    """What the caller wants to happen — resolved into a PlaybackSession.

    Targets a MediaItem by ID; URI resolution happens later in the service layer.
    preferred_delivery mirrors StreamSession.mode and StreamingSupport field names.
    """

    target_zone_id: ZoneId
    media_item_id: MediaItemId
    preferred_delivery: Literal["auto", "direct", "cached", "live_pipe"] = "auto"
    enqueue: bool = False
    replace_queue: bool = True
    title: str | None = None
    thumbnail_uri: str | None = None


@dataclass(slots=True)
class PlaybackSession:
    """Record of one app-initiated playback attempt for a zone.

    Ties together: zone -> queue -> current item -> stream session.
    Transport/rendering snapshots live in ZoneRuntimeState, not here.
    """

    id: str
    zone_id: ZoneId
    queue_id: QueueId | None = None
    current_item_id: str | None = None
    stream_session_id: StreamSessionId | None = None
    state: PlaybackSessionState = PlaybackSessionState.IDLE
    error_message: str | None = None
    failure_kind: PlaybackFailureKind | None = None
    version: int = 0

    @property
    def is_active(self) -> bool:
        return self.state in {
            PlaybackSessionState.STARTING,
            PlaybackSessionState.TRANSITIONING,
            PlaybackSessionState.PLAYING,
            PlaybackSessionState.PAUSED,
        }
