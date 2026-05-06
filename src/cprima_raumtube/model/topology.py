"""Topology — physical hardware, rooms, zones, renderers, coordinators, and groups."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from cprima_raumtube.model.protocol import Service


@dataclass
class PhysicalDevice:
    """A real piece of hardware on the network."""

    udn: str
    ip: str
    friendly_name: str
    model: str
    role: Literal["hub", "speaker", "soundbar", "unknown"]
    services: list[Service] = field(default_factory=list)
    room_id: str | None = None
    location_url: str | None = None


@dataclass
class Room:
    """User-facing physical location (e.g. 'HomeOffice')."""

    id: str
    name: str
    physical_device_udns: list[str] = field(default_factory=list)


@dataclass
class Coordinator:
    """One coordinator role within a zone or group.

    Multiroom systems split three concerns that may live on different UDNs:
      transport  — owns SetAVTransportURI / Play / Stop
      clock_master — drives synchronised audio clock across the group
      group_master — decides which renderers belong to the group
    """

    renderer_udn: str
    physical_device_udn: str | None = None
    role: Literal["transport", "clock_master", "group_master"] = "transport"


@dataclass
class Zone:
    """A controllable playback target — may span one or several rooms."""

    id: str
    name: str
    room_ids: list[str]
    renderer_udn: str
    coordinators: list[Coordinator] = field(default_factory=list)
    kind: Literal["single_room", "group", "virtual"] = "single_room"

    @property
    def transport_coordinator(self) -> Coordinator | None:
        """Return the coordinator that owns transport control, if declared."""
        for c in self.coordinators:
            if c.role == "transport":
                return c
        return None


@dataclass
class RendererCapabilities:
    """What this renderer actually supports, derived from GetProtocolInfo + SCPD.

    Populated after capability negotiation; default-False until probed.
    """

    seek: bool = False
    pause: bool = False
    next_previous: bool = False
    set_next_uri: bool = False  # SetNextAVTransportURI
    volume_control: bool = False
    mime_types: list[str] = field(default_factory=list)
    protocols: list[str] = field(default_factory=list)

    @classmethod
    def unknown(cls) -> RendererCapabilities:
        """Placeholder used before any capability probe has run."""
        return cls()


@dataclass
class ZoneRenderer:
    """UPnP renderer endpoint for a zone (virtual device hosted on the Expand hub)."""

    udn: str
    name: str
    location_url: str
    avtransport: Service
    rendering_control: Service
    connection_manager: Service | None = None
    capabilities: RendererCapabilities | None = None

    @property
    def avt_control_url(self) -> str:
        return self.avtransport.control_url

    @property
    def rc_control_url(self) -> str:
        return self.rendering_control.control_url

    @property
    def probed(self) -> bool:
        return self.capabilities is not None


@dataclass
class Group:
    """Dynamic multiroom aggregate — a coordinator zone plus member zones."""

    id: str
    name: str
    member_zone_ids: list[str]
    coordinator_zone_id: str
