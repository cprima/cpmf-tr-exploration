"""Aggregate roots -- bounded contexts within one Installation.

DeviceInventory    slow-moving: physical devices, renderers, protocol snapshots
TopologyState      volatile: zones, groups, coordinator membership
LibraryAggregate   media items, playlists, resolutions, cache entries
RuntimeAggregate   per-zone queues, sessions, device state, event log
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from cprima_raumtube.model.media import AppQueue
from cprima_raumtube.model.playback import PlaybackSession, ZoneRuntimeState

if TYPE_CHECKING:
    from cprima_raumtube.model.events import AnyEvent
    from cprima_raumtube.model.ids import (
        GroupId,
        PhysicalDeviceUdn,
        QueueId,
        RendererUdn,
        RoomId,
        ServiceType,
        StreamSessionId,
        ZoneId,
    )
    from cprima_raumtube.model.media import (
        DeviceQueueSnapshot,
        Library,
        MediaItem,
        MediaResolution,
        Playlist,
    )
    from cprima_raumtube.model.protocol import ProtocolSnapshot
    from cprima_raumtube.model.streaming import CacheEntry, StreamSession
    from cprima_raumtube.model.topology import Group, PhysicalDevice, Room, Zone, ZoneRenderer


def new_id() -> str:
    """Generate a random short ID for model entity IDs."""
    return uuid.uuid4().hex[:12]


class CommandStatus(StrEnum):
    """Lifecycle states for a CommandRecord.

    StrEnum so values compare equal to plain strings (backward compatible)
    while giving enum safety for mypy and IDE autocomplete.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class SubscriptionRenewalState(StrEnum):
    ACTIVE = "active"
    RENEWING = "renewing"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass(slots=True)
class SubscriptionState:
    """Active GENA event subscription for one service on one renderer.

    Operational runtime state — not raw protocol description.

    sid             subscription ID returned by the device in SUBSCRIBE response
    callback_url    local HTTP endpoint the device posts events to
    expires_at      when the subscription lapses if not renewed
    renewal_state   tracks in-flight renewal attempts
    last_renewed_at when the last successful SUBSCRIBE/re-SUBSCRIBE completed
    """

    sid: str
    renderer_udn: RendererUdn
    service_type: ServiceType
    callback_url: str
    expires_at: datetime | None = None
    renewal_state: SubscriptionRenewalState = SubscriptionRenewalState.ACTIVE
    last_renewed_at: datetime | None = None


@dataclass(slots=True)
class DiscoverySnapshot:
    """Point-in-time record of one discovery pass across the network.

    Captures which UDNs were visible and what topology XML was retrieved,
    providing a reproducible baseline for debugging and capability replay.
    """

    id: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    device_udns: list[str] = field(default_factory=list)
    topology_xml: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class CommandRecord:
    """Audit log entry for one SOAP action sent to a renderer.

    status lifecycle: pending → running → succeeded | failed | timed_out
    soap_fault_* populated on UPnP protocol errors.
    network_error populated on connection/timeout failures before SOAP response.
    """

    id: str
    action: str
    target_udn: RendererUdn
    zone_id: ZoneId | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    status: CommandStatus = CommandStatus.PENDING
    soap_fault_code: str | None = None
    soap_fault_description: str | None = None
    network_error: str | None = None
    details: dict[str, str] = field(default_factory=dict)


# -- Device Inventory ---------------------------------------------------------


@dataclass(slots=True)
class DeviceInventory:
    """Slow-moving discovered hardware, renderers, services, and protocol evidence.

    Changes only when devices are added, removed, or re-probed -- not during
    normal zone/group topology changes.
    """

    physical_devices: dict[PhysicalDeviceUdn, PhysicalDevice] = field(default_factory=dict)
    rooms: dict[RoomId, Room] = field(default_factory=dict)
    zone_renderers: dict[RendererUdn, ZoneRenderer] = field(default_factory=dict)
    protocol_snapshots: list[ProtocolSnapshot] = field(default_factory=list)
    discovery_snapshots: list[DiscoverySnapshot] = field(default_factory=list)

    def register_device(self, device: PhysicalDevice) -> None:
        self.physical_devices[device.udn] = device

    def register_zone_renderer(self, renderer: ZoneRenderer) -> None:
        self.zone_renderers[renderer.udn] = renderer

    def add_snapshot(self, snapshot: ProtocolSnapshot) -> None:
        self.protocol_snapshots.append(snapshot)

    def get_renderer(self, udn: RendererUdn) -> ZoneRenderer:
        try:
            return self.zone_renderers[udn]
        except KeyError:
            raise KeyError(f"No ZoneRenderer with UDN {udn!r}") from None


# -- Topology State -----------------------------------------------------------


@dataclass(slots=True)
class TopologyState:
    """Volatile zone and group membership -- may change at runtime.

    A zone can gain or lose members; groups form and dissolve.
    Distinct from DeviceInventory which tracks the underlying hardware.
    """

    zones: dict[ZoneId, Zone] = field(default_factory=dict)
    groups: dict[GroupId, Group] = field(default_factory=dict)
    topology_epoch: int = 0

    def add_zone(self, zone: Zone) -> None:
        self.zones[zone.id] = zone
        self.topology_epoch += 1

    def add_group(self, group: Group) -> None:
        self.groups[group.id] = group
        self.topology_epoch += 1

    def get_zone(self, zone_id: ZoneId) -> Zone:
        try:
            return self.zones[zone_id]
        except KeyError:
            raise KeyError(f"Zone {zone_id!r} not found") from None

    def find_zone_by_name(self, name: str) -> Zone | None:
        for z in self.zones.values():
            if z.name.lower() == name.lower():
                return z
        for z in self.zones.values():
            if name.lower() in z.name.lower():
                return z
        return None


# -- Library ------------------------------------------------------------------


@dataclass(slots=True)
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


# -- Runtime ------------------------------------------------------------------


@dataclass(slots=True)
class RuntimeAggregate:
    """Per-zone runtime state -- device state, queues, sessions, and event log."""

    zone_states: dict[ZoneId, ZoneRuntimeState] = field(default_factory=dict)
    queues: dict[QueueId, AppQueue] = field(default_factory=dict)
    device_queue_snapshots: dict[str, DeviceQueueSnapshot] = field(default_factory=dict)
    stream_sessions: dict[StreamSessionId, StreamSession] = field(default_factory=dict)
    playback_sessions: dict[str, PlaybackSession] = field(default_factory=dict)
    event_log: list[AnyEvent] = field(default_factory=list)
    command_log: list[CommandRecord] = field(default_factory=list)
    subscriptions: dict[str, SubscriptionState] = field(default_factory=dict)

    def get_or_create_zone_state(self, zone_id: ZoneId) -> ZoneRuntimeState:
        if zone_id not in self.zone_states:
            self.zone_states[zone_id] = ZoneRuntimeState(zone_id=zone_id)
        return self.zone_states[zone_id]

    def get_or_create_queue(self, zone_id: ZoneId) -> AppQueue:
        for q in self.queues.values():
            if q.zone_id == zone_id:
                return q
        q = AppQueue(id=new_id(), zone_id=zone_id)
        self.queues[q.id] = q
        return q

    def get_playback_session(self, zone_id: ZoneId) -> PlaybackSession | None:
        for ps in self.playback_sessions.values():
            if ps.zone_id == zone_id:
                return ps
        return None

    def get_or_create_playback_session(self, zone_id: ZoneId) -> PlaybackSession:
        ps = self.get_playback_session(zone_id)
        if ps is None:
            ps = PlaybackSession(id=new_id(), zone_id=zone_id)
            self.playback_sessions[ps.id] = ps
        return ps

    def emit(self, event: AnyEvent) -> None:
        self.event_log.append(event)

    def events_for_zone(self, zone_id: ZoneId) -> list[AnyEvent]:
        return [
            e
            for e in self.event_log
            if hasattr(e, "zone_id") and e.zone_id == zone_id  # type: ignore[union-attr]
        ]
