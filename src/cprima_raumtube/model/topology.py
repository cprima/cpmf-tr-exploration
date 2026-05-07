"""Topology — physical hardware, rooms, zones, renderers, coordinators, and groups."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from cprima_raumtube.model.ids import GroupId, PhysicalDeviceUdn, RendererUdn, RoomId, ZoneId
    from cprima_raumtube.model.protocol import ProtocolInfo, Service


class DeviceLifecycle(StrEnum):
    """Reachability lifecycle for a discovered physical device.

    StrEnum so values compare equal to plain strings (backward compatible)
    while giving enum safety for mypy and IDE autocomplete.
    """

    DISCOVERED = "discovered"
    REACHABLE = "reachable"
    STALE = "stale"
    OFFLINE = "offline"
    REMOVED = "removed"


@dataclass(slots=True)
class PhysicalDevice:
    """A real piece of hardware on the network."""

    udn: PhysicalDeviceUdn
    ip: str
    friendly_name: str
    model: str
    role: Literal["hub", "speaker", "soundbar", "unknown"]
    services: list[Service] = field(default_factory=list)
    room_id: RoomId | None = None
    location_url: str | None = None
    lifecycle: DeviceLifecycle = DeviceLifecycle.DISCOVERED
    last_seen: datetime | None = None
    station_buttons: list[StationButton] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.udn:
            raise ValueError("PhysicalDevice.udn must not be empty")
        if not self.ip:
            raise ValueError("PhysicalDevice.ip must not be empty")
        if not self.friendly_name:
            raise ValueError("PhysicalDevice.friendly_name must not be empty")


@dataclass(slots=True)
class Room:
    """User-facing physical location (e.g. 'HomeOffice')."""

    id: RoomId
    name: str
    physical_device_udns: list[PhysicalDeviceUdn] = field(default_factory=list)


@dataclass(slots=True)
class Coordinator:
    """One coordinator role within a zone or group.

    Multiroom systems split three concerns that may live on different UDNs:
      transport    — owns SetAVTransportURI / Play / Stop
      clock_master — drives synchronised audio clock across the group
      group_master — decides which renderers belong to the group
    """

    renderer_udn: RendererUdn
    physical_device_udn: PhysicalDeviceUdn | None = None
    role: Literal["transport", "clock_master", "group_master"] = "transport"


@dataclass(slots=True)
class Zone:
    """A controllable playback target — may span one or several rooms."""

    id: ZoneId
    name: str
    room_ids: list[RoomId]
    renderer_udn: RendererUdn
    coordinators: tuple[Coordinator, ...] = ()
    kind: Literal["single_room", "group", "virtual"] = "single_room"
    version: int = 0

    @property
    def transport_coordinator(self) -> Coordinator | None:
        """Return the coordinator that owns transport control, if declared."""
        for c in self.coordinators:
            if c.role == "transport":
                return c
        return None

    def add_coordinator(self, coordinator: Coordinator) -> None:
        # Replace any existing coordinator with the same role, then add
        self.coordinators = (
            *(c for c in self.coordinators if c.role != coordinator.role),
            coordinator,
        )
        self.version += 1

    def remove_coordinator(self, role: Literal["transport", "clock_master", "group_master"]) -> None:
        self.coordinators = tuple(c for c in self.coordinators if c.role != role)
        self.version += 1

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Zone.id must not be empty")
        if not self.name:
            raise ValueError("Zone.name must not be empty")
        if not self.renderer_udn:
            raise ValueError("Zone.renderer_udn must not be empty")


# ---------------------------------------------------------------------------
# Capability evidence — rich model replacing bare booleans
# ---------------------------------------------------------------------------


class CapabilitySource(StrEnum):
    SCPD = "scpd"
    CONNECTION_MANAGER = "connection_manager"
    OBSERVED = "observed"
    ASSUMED = "assumed"


class CapabilityConfidence(StrEnum):
    CERTAIN = "certain"
    PROBABLE = "probable"
    UNTESTED = "untested"


@dataclass(frozen=True, slots=True)
class Capability:
    """One renderer capability with provenance and confidence.

    source:
      scpd               — declared in the service's SCPD action list
      connection_manager — inferred from GetProtocolInfo sink/source
      observed           — confirmed by a live SOAP call (see CapabilityObservation)
      assumed            — default; not yet probed

    confidence:
      certain    — multiple sources agree or observed success
      probable   — single source, plausible
      untested   — default until any probe runs
    """

    name: str
    supported: bool
    source: CapabilitySource
    confidence: CapabilityConfidence
    notes: str | None = None
    constraint: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Capability.name must not be empty")


def _unprobed(name: str) -> Capability:
    """Return a default Capability marked assumed / untested / unsupported."""
    return Capability(
        name=name,
        supported=False,
        source=CapabilitySource.ASSUMED,
        confidence=CapabilityConfidence.UNTESTED,
    )


@dataclass(slots=True)
class CapabilityObservation:
    """Result of a live SOAP probe — distinguishes declared vs actually working.

    Append to RendererProfile.observations after any test call so that the
    profile can be updated to source="observed", confidence="certain".
    """

    renderer_udn: str
    action: str
    result: Literal["success", "soap_fault", "timeout", "unsupported"]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: str | None = None


@dataclass(frozen=True, slots=True)
class RendererQuirk:
    """A known deviation from spec or unexpected behaviour for a renderer.

    Real DLNA/Raumfeld integrations always accumulate quirks; model them
    explicitly rather than scattering workaround comments through service code.
    """

    key: str
    description: str
    workaround: str | None = None


# ---------------------------------------------------------------------------
# Renderer profile — sub-groups by service
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PlaybackSupport:
    """AVTransport actions supported by this renderer."""

    seek: Capability = field(default_factory=lambda: _unprobed("seek"))
    pause: Capability = field(default_factory=lambda: _unprobed("pause"))
    next_previous: Capability = field(default_factory=lambda: _unprobed("next_previous"))
    set_next_uri: Capability = field(default_factory=lambda: _unprobed("set_next_uri"))
    sleep_timer: Capability = field(default_factory=lambda: _unprobed("sleep_timer"))
    standby: Capability = field(default_factory=lambda: _unprobed("standby"))
    play_mode: Capability = field(default_factory=lambda: _unprobed("play_mode"))
    spotify_presets: Capability = field(default_factory=lambda: _unprobed("spotify_presets"))
    stream_properties: Capability = field(default_factory=lambda: _unprobed("stream_properties"))
    like_unlike: Capability = field(default_factory=lambda: _unprobed("like_unlike"))
    hot_swap_stream: Capability = field(default_factory=lambda: _unprobed("hot_swap_stream"))


@dataclass(slots=True)
class AudioSupport:
    """RenderingControl actions supported by this renderer."""

    volume: Capability = field(default_factory=lambda: _unprobed("volume"))
    mute: Capability = field(default_factory=lambda: _unprobed("mute"))
    volume_db: Capability = field(default_factory=lambda: _unprobed("volume_db"))
    eq_3band: Capability = field(default_factory=lambda: _unprobed("eq_3band"))
    stereo_widening: Capability = field(default_factory=lambda: _unprobed("stereo_widening"))
    stereo_balance: Capability = field(default_factory=lambda: _unprobed("stereo_balance"))
    line_in: Capability = field(default_factory=lambda: _unprobed("line_in"))
    device_settings: Capability = field(default_factory=lambda: _unprobed("device_settings"))
    room_volume: Capability = field(default_factory=lambda: _unprobed("room_volume"))


@dataclass(slots=True)
class StreamingSupport:
    """Stream delivery modes and supported formats from GetProtocolInfo."""

    cached_file: Capability = field(default_factory=lambda: _unprobed("cached_file"))
    live_pipe: Capability = field(default_factory=lambda: _unprobed("live_pipe"))
    direct_url: Capability = field(default_factory=lambda: _unprobed("direct_url"))
    sink_protocols: list[ProtocolInfo] = field(default_factory=list)
    source_protocols: list[ProtocolInfo] = field(default_factory=list)

    @property
    def mime_types(self) -> list[str]:
        """Convenience: unique content_format strings from sink_protocols."""
        seen: list[str] = []
        for p in self.sink_protocols:
            if p.content_format and p.content_format not in seen:
                seen.append(p.content_format)
        return seen


@dataclass(slots=True)
class ContentSupport:
    """ContentDirectory service features."""

    station_buttons: Capability = field(default_factory=lambda: _unprobed("station_buttons"))
    queue_management: Capability = field(default_factory=lambda: _unprobed("queue_management"))


@dataclass(slots=True)
class DeviceSupport:
    """SetupService and ConfigService features."""

    firmware_info: Capability = field(default_factory=lambda: _unprobed("firmware_info"))
    network_info: Capability = field(default_factory=lambda: _unprobed("network_info"))
    device_mode: Capability = field(default_factory=lambda: _unprobed("device_mode"))
    ota_update: Capability = field(default_factory=lambda: _unprobed("ota_update"))
    config_preferences: Capability = field(default_factory=lambda: _unprobed("config_preferences"))


@dataclass(slots=True)
class RendererProfile:
    """Describes what a renderer supports — populated after SCPD probing.

    All sub-groups default to fully unprobed until evidence is recorded.
    Use RendererProfile.unknown() as a pre-probe placeholder.

    Convenience boolean properties (can_*) are derived from the richer
    Capability objects; prefer the Capability fields when provenance matters.
    """

    playback: PlaybackSupport = field(default_factory=PlaybackSupport)
    audio: AudioSupport = field(default_factory=AudioSupport)
    streaming: StreamingSupport = field(default_factory=StreamingSupport)
    content: ContentSupport = field(default_factory=ContentSupport)
    device: DeviceSupport = field(default_factory=DeviceSupport)
    observations: list[CapabilityObservation] = field(default_factory=list)
    quirks: list[RendererQuirk] = field(default_factory=list)

    # ── convenience booleans ─────────────────────────────────────────────────

    @property
    def can_seek(self) -> bool:
        return self.playback.seek.supported

    @property
    def can_pause(self) -> bool:
        return self.playback.pause.supported

    @property
    def can_set_next_uri(self) -> bool:
        return self.playback.set_next_uri.supported

    @property
    def has_volume(self) -> bool:
        return self.audio.volume.supported

    @property
    def has_eq(self) -> bool:
        return self.audio.eq_3band.supported

    @classmethod
    def unknown(cls) -> RendererProfile:
        """Placeholder used before any SCPD probe has run."""
        return cls()


@dataclass(slots=True)
class StationButton:
    """One preset/favourite button slot on a physical Raumfeld device.

    Populated from ContentDirectory or SetupService button queries.
    button_number is 1-based (matches device UI labelling).
    source tracks where the assignment was read from, not set by.
    """

    button_number: int
    renderer_udn: RendererUdn
    uri: str
    metadata: str | None = None
    source: Literal["device", "app", "unknown"] = "unknown"
    last_seen: datetime | None = None


@dataclass(slots=True)
class ZoneRenderer:
    """UPnP renderer endpoint for a zone (virtual device hosted on the Expand hub)."""

    udn: RendererUdn
    name: str
    location_url: str
    avtransport: Service
    rendering_control: Service
    connection_manager: Service | None = None
    profile: RendererProfile | None = None

    def __post_init__(self) -> None:
        if not self.udn:
            raise ValueError("ZoneRenderer.udn must not be empty")
        if not self.name:
            raise ValueError("ZoneRenderer.name must not be empty")
        if not self.location_url:
            raise ValueError("ZoneRenderer.location_url must not be empty")

    @property
    def avt_control_url(self) -> str:
        return self.avtransport.control_url

    @property
    def rc_control_url(self) -> str:
        return self.rendering_control.control_url

    @property
    def probed(self) -> bool:
        return self.profile is not None


class SyncQuality(StrEnum):
    GOOD = "good"
    DEGRADED = "degraded"
    LOST = "lost"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class SyncState:
    """Audio clock synchronisation state across a multiroom group.

    follower_drift_ms   per-follower drift keyed by renderer UDN (ms, signed)
    follower_offset_ms  per-follower clock offset keyed by renderer UDN (ms)
    sync_quality        overall group quality; degraded when any follower drifts > threshold
    last_updated        UTC timestamp of the most recent measurement
    """

    clock_master_udn: RendererUdn
    follower_udns: list[RendererUdn] = field(default_factory=list)
    sync_quality: SyncQuality = SyncQuality.UNKNOWN
    follower_drift_ms: dict[RendererUdn, float] = field(default_factory=dict)
    follower_offset_ms: dict[RendererUdn, float] = field(default_factory=dict)
    last_updated: datetime | None = None


@dataclass(slots=True)
class Group:
    """Dynamic multiroom aggregate — a coordinator zone plus member zones."""

    id: GroupId
    name: str
    member_zone_ids: tuple[ZoneId, ...]
    coordinator_zone_id: ZoneId
    sync_state: SyncState | None = None
    version: int = 0

    def add_member(self, zone_id: ZoneId) -> None:
        if zone_id not in self.member_zone_ids:
            self.member_zone_ids = (*self.member_zone_ids, zone_id)
            self.version += 1

    def remove_member(self, zone_id: ZoneId) -> None:
        if zone_id == self.coordinator_zone_id:
            raise ValueError(f"Cannot remove coordinator zone {zone_id!r} from group")
        self.member_zone_ids = tuple(z for z in self.member_zone_ids if z != zone_id)
        self.version += 1

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Group.id must not be empty")
        if not self.name:
            raise ValueError("Group.name must not be empty")
        if not self.coordinator_zone_id:
            raise ValueError("Group.coordinator_zone_id must not be empty")
        if self.coordinator_zone_id not in self.member_zone_ids:
            raise ValueError(
                f"coordinator_zone_id {self.coordinator_zone_id!r} must be in member_zone_ids"
            )
