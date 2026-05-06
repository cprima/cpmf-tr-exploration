"""Domain events emitted by the system.

Events are value objects — immutable snapshots of what happened.
They are not dispatched here; callers append them to an event log or
pass them to a handler.  UPnP eventing (SUBSCRIBE/NOTIFY) will eventually
be the source of most transport and volume events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


def _now() -> datetime:

    return datetime.now(UTC)


@dataclass(frozen=True)
class TransportEvent:
    """AVTransport state changed on a zone."""

    zone_id: str
    new_state: str  # PLAYING | STOPPED | PAUSED_PLAYBACK | TRANSITIONING | NO_MEDIA_PRESENT
    old_state: str | None = None
    timestamp: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class VolumeEvent:
    """RenderingControl volume changed on a zone."""

    zone_id: str
    new_volume: int
    old_volume: int | None = None
    channel: str = "Master"  # Master | LF | RF
    timestamp: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class QueueEvent:
    """A zone's playback queue was modified."""

    zone_id: str
    queue_id: str
    kind: Literal["item_added", "item_removed", "cleared", "index_changed", "mode_changed"]
    timestamp: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class GroupTopologyEvent:
    """Zone grouping changed — a zone joined or left a group."""

    kind: Literal["zone_added", "zone_removed", "group_created", "group_dissolved"]
    timestamp: datetime = field(default_factory=_now)
    zone_id: str | None = None
    group_id: str | None = None


# Union type for typed event logs
AnyEvent = TransportEvent | VolumeEvent | QueueEvent | GroupTopologyEvent
