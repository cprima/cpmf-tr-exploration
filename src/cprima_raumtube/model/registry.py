"""Top-level registry -- Installation, NetworkProfile, RaumtubeRegistry.

Structure
---------
RaumtubeRegistry
  Installation        one Raumfeld installation on one physical LAN
    network           static config (IP, CIDR, port)
    inventory         discovered hardware, renderers, protocol evidence
    topology          volatile zone/group membership
    library           media items, playlists, resolutions, cache
    state             per-zone runtime queues, sessions, device state

IDs are installation-scoped: a zone_id or renderer_udn is only unique
within its Installation.  Cross-installation references must carry the
installation_id as a prefix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cprima_raumtube.model.aggregates import (
    DeviceInventory,
    LibraryAggregate,
    RuntimeAggregate,
    TopologyState,
)

if TYPE_CHECKING:
    from cprima_raumtube.model.events import AnyEvent
    from cprima_raumtube.model.ids import InstallationId, ZoneId
    from cprima_raumtube.model.media import AppQueue
    from cprima_raumtube.model.topology import Zone, ZoneRenderer


@dataclass(slots=True)
class NetworkProfile:
    """Network coordinates for one Raumfeld installation.

    local_ip     IP of *this* machine on the LAN -- used as the HTTP
                 streaming server address exposed to the renderer.
    source_ip    IP bound for SSDP multicast.  Defaults to local_ip
                 when omitted; required on Windows for correct multicast binding.
    cidr         Subnet in CIDR notation, e.g. "10.38.20.0/24".
    stream_port  Port the local HTTP streaming server listens on.
    """

    id: str
    name: str
    local_ip: str | None = None
    source_ip: str | None = None  # falls back to local_ip if None
    cidr: str | None = None
    stream_port: int = 8080
    discovery_timeout: int = 6

    @property
    def effective_source_ip(self) -> str | None:
        """SSDP bind address -- source_ip if set, otherwise local_ip."""
        return self.source_ip or self.local_ip


@dataclass(slots=True)
class Installation:
    """One Raumfeld installation on one physical LAN.

    Four layers make the architecture explicit:
      inventory  discovered hardware and protocol evidence (slow-changing)
      topology   zone and group membership (volatile, changes at runtime)
      library    media items, playlists, resolutions, cache (session-lived)
      state      per-zone queues, sessions, and device state (runtime only)
    """

    id: InstallationId
    name: str  # "Home", "Office", "Cabin"
    network: NetworkProfile
    inventory: DeviceInventory = field(default_factory=DeviceInventory)
    topology: TopologyState = field(default_factory=TopologyState)
    library: LibraryAggregate = field(default_factory=LibraryAggregate)
    state: RuntimeAggregate = field(default_factory=RuntimeAggregate)

    @classmethod
    def ephemeral(cls) -> Installation:
        """Minimal in-memory installation for single-session CLI use."""
        return cls(
            id="ephemeral",
            name="ephemeral",
            network=NetworkProfile(id="net", name="net"),
        )

    # -- Cross-layer helpers --------------------------------------------------

    def get_zone(self, zone_id: ZoneId) -> Zone:
        return self.topology.get_zone(zone_id)

    def get_renderer_for_zone(self, zone_id: ZoneId) -> ZoneRenderer:
        """Cross-layer: zone from topology + renderer from inventory."""
        zone = self.topology.get_zone(zone_id)
        return self.inventory.get_renderer(zone.renderer_udn)

    def get_or_create_queue(self, zone_id: ZoneId) -> AppQueue:
        return self.state.get_or_create_queue(zone_id)

    def emit(self, event: AnyEvent) -> None:
        self.state.emit(event)

    def events_for_zone(self, zone_id: ZoneId) -> list[AnyEvent]:
        return self.state.events_for_zone(zone_id)


@dataclass(slots=True)
class RaumtubeRegistry:
    """All known installations.  Entry point for multi-site operation.

    Usage
    -----
    >>> reg = RaumtubeRegistry()
    >>> reg.add(Installation("home", "Home", NetworkProfile("net-home", "Home")))
    >>> reg.use("home")
    >>> inst = reg.active
    """

    installations: dict[InstallationId, Installation] = field(default_factory=dict)
    active_installation_id: InstallationId | None = None

    @property
    def active(self) -> Installation | None:
        if self.active_installation_id is None:
            return None
        return self.installations.get(self.active_installation_id)

    def add(self, installation: Installation) -> None:
        self.installations[installation.id] = installation

    def use(self, installation_id: InstallationId) -> None:
        if installation_id not in self.installations:
            available = list(self.installations.keys())
            raise KeyError(f"Installation {installation_id!r} not found. Available: {available}")
        self.active_installation_id = installation_id

    def get(self, installation_id: InstallationId) -> Installation:
        try:
            return self.installations[installation_id]
        except KeyError:
            available = list(self.installations.keys())
            raise KeyError(
                f"Installation {installation_id!r} not found. Available: {available}"
            ) from None
