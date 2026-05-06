"""Aggregate roots — bounded contexts within one Installation/System.

TopologyAggregate   physical devices, zones, renderers, protocol snapshots
LibraryAggregate    media items, playlists, resolutions, cache entries
PlaybackAggregate   queues, stream sessions, playback sessions, event log
System              thin facade holding all three aggregates
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cprima_raumtube.model.events import AnyEvent
from cprima_raumtube.model.media import (
    Library,
    MediaItem,
    MediaResolution,
    Playlist,
    Queue,
)
from cprima_raumtube.model.playback import PlaybackSession
from cprima_raumtube.model.protocol import ProtocolSnapshot
from cprima_raumtube.model.streaming import CacheEntry, StreamSession
from cprima_raumtube.model.topology import Group, PhysicalDevice, Room, Zone, ZoneRenderer


def new_id() -> str:
    """Generate a random short ID for model entity IDs."""
    return uuid.uuid4().hex[:12]


# ── Topology ──────────────────────────────────────────────────────────────────


@dataclass
class TopologyAggregate:
    """Physical hardware, logical zones, and raw protocol snapshots."""

    physical_devices: dict[str, PhysicalDevice] = field(default_factory=dict)
    rooms: dict[str, Room] = field(default_factory=dict)
    zones: dict[str, Zone] = field(default_factory=dict)
    zone_renderers: dict[str, ZoneRenderer] = field(default_factory=dict)
    groups: dict[str, Group] = field(default_factory=dict)
    protocol_snapshots: list[ProtocolSnapshot] = field(default_factory=list)

    def register_device(self, device: PhysicalDevice) -> None:
        self.physical_devices[device.udn] = device

    def register_zone_renderer(self, renderer: ZoneRenderer) -> None:
        self.zone_renderers[renderer.udn] = renderer

    def add_snapshot(self, snapshot: ProtocolSnapshot) -> None:
        self.protocol_snapshots.append(snapshot)

    def get_zone(self, zone_id: str) -> Zone:
        try:
            return self.zones[zone_id]
        except KeyError:
            raise KeyError(f"Zone {zone_id!r} not found") from None

    def get_renderer_for_zone(self, zone_id: str) -> ZoneRenderer:
        zone = self.get_zone(zone_id)
        try:
            return self.zone_renderers[zone.renderer_udn]
        except KeyError:
            raise KeyError(
                f"No ZoneRenderer for zone {zone_id!r} (renderer UDN: {zone.renderer_udn!r})"
            ) from None

    def find_zone_by_name(self, name: str) -> Zone | None:
        for z in self.zones.values():
            if z.name.lower() == name.lower():
                return z
        for z in self.zones.values():
            if name.lower() in z.name.lower():
                return z
        return None


# ── Library ───────────────────────────────────────────────────────────────────


@dataclass
class LibraryAggregate:
    """Media items, playlists, resolutions, and local cache."""

    libraries: dict[str, Library] = field(default_factory=dict)
    playlists: dict[str, Playlist] = field(default_factory=dict)
    resolutions: dict[str, MediaResolution] = field(default_factory=dict)
    cache_entries: dict[str, CacheEntry] = field(default_factory=dict)

    def find_item(self, item_id: str) -> MediaItem | None:
        for lib in self.libraries.values():
            item = lib.items.get(item_id)
            if item is not None:
                return item
        return None

    def find_by_canonical(self, canonical_id: str) -> MediaItem | None:
        for lib in self.libraries.values():
            item = lib.find_by_canonical(canonical_id)
            if item is not None:
                return item
        return None

    def get_fresh_resolution(
        self,
        media_item_id: str,
        now: datetime | None = None,
    ) -> MediaResolution | None:
        t = now or datetime.now(UTC)
        for r in self.resolutions.values():
            if r.media_item_id == media_item_id and r.is_valid(t):
                return r
        return None

    def add_resolution(self, resolution: MediaResolution) -> None:
        self.resolutions[resolution.id] = resolution


# ── Playback ──────────────────────────────────────────────────────────────────


@dataclass
class PlaybackAggregate:
    """Per-zone queues, stream sessions, playback sessions, and event log."""

    queues: dict[str, Queue] = field(default_factory=dict)
    stream_sessions: dict[str, StreamSession] = field(default_factory=dict)
    playback_sessions: dict[str, PlaybackSession] = field(default_factory=dict)
    event_log: list[AnyEvent] = field(default_factory=list)

    def get_or_create_queue(self, zone_id: str) -> Queue:
        for q in self.queues.values():
            if q.zone_id == zone_id:
                return q
        q = Queue(id=new_id(), zone_id=zone_id)
        self.queues[q.id] = q
        return q

    def get_playback_session(self, zone_id: str) -> PlaybackSession | None:
        for ps in self.playback_sessions.values():
            if ps.zone_id == zone_id:
                return ps
        return None

    def get_or_create_playback_session(self, zone_id: str) -> PlaybackSession:
        ps = self.get_playback_session(zone_id)
        if ps is None:
            ps = PlaybackSession(id=new_id(), zone_id=zone_id)
            self.playback_sessions[ps.id] = ps
        return ps

    def emit(self, event: AnyEvent) -> None:
        self.event_log.append(event)

    def events_for_zone(self, zone_id: str) -> list[AnyEvent]:
        return [
            e
            for e in self.event_log
            if hasattr(e, "zone_id") and e.zone_id == zone_id  # type: ignore[union-attr]
        ]


# ── System (thin facade) ─────────────────────────────────────────────────────


@dataclass
class System:
    """One Raumfeld installation on one LAN.

    Delegates to three aggregate roots; callers should prefer addressing
    the aggregates directly for non-trivial operations.
    """

    topology: TopologyAggregate = field(default_factory=TopologyAggregate)
    library: LibraryAggregate = field(default_factory=LibraryAggregate)
    playback: PlaybackAggregate = field(default_factory=PlaybackAggregate)

    # ── Topology pass-throughs ────────────────────────────────────────────────

    def register_device(self, device: PhysicalDevice) -> None:
        self.topology.register_device(device)

    def register_zone_renderer(self, renderer: ZoneRenderer) -> None:
        self.topology.register_zone_renderer(renderer)

    def get_zone(self, zone_id: str) -> Zone:
        return self.topology.get_zone(zone_id)

    def get_renderer_for_zone(self, zone_id: str) -> ZoneRenderer:
        return self.topology.get_renderer_for_zone(zone_id)

    # ── Library pass-throughs ─────────────────────────────────────────────────

    def get_fresh_resolution(
        self, media_item_id: str, now: datetime | None = None
    ) -> MediaResolution | None:
        return self.library.get_fresh_resolution(media_item_id, now)

    # ── Playback pass-throughs ────────────────────────────────────────────────

    def get_or_create_queue(self, zone_id: str) -> Queue:
        return self.playback.get_or_create_queue(zone_id)

    def get_or_create_playback_session(self, zone_id: str) -> PlaybackSession:
        return self.playback.get_or_create_playback_session(zone_id)

    def emit(self, event: AnyEvent) -> None:
        self.playback.emit(event)

    def events_for_zone(self, zone_id: str) -> list[AnyEvent]:
        return self.playback.events_for_zone(zone_id)
