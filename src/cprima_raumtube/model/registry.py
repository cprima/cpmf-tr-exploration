"""Top-level registry — Installation, NetworkProfile, RaumtubeRegistry.

Hierarchy
---------
RaumtubeRegistry
└── Installation          one Raumfeld installation on one physical LAN
    ├── NetworkProfile    network coordinates (IP, CIDR, port)
    └── System            topology + library + playback aggregates

IDs are installation-scoped: a zone_id or renderer_udn is only unique
within its Installation.  Cross-installation references must carry the
installation_id as a prefix.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cprima_raumtube.model.aggregates import System


@dataclass
class NetworkProfile:
    """Network coordinates for one Raumfeld installation.

    local_ip     IP of *this* machine on the LAN — used as the HTTP
                 streaming server address exposed to the renderer.
    source_ip    IP bound for SSDP multicast.  Defaults to local_ip
                 when omitted; required on Windows for correct multicast binding.
    cidr         Subnet in CIDR notation, e.g. ``"10.38.20.0/24"``.
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
        """SSDP bind address — source_ip if set, otherwise local_ip."""
        return self.source_ip or self.local_ip


@dataclass
class Installation:
    """One Raumfeld installation on one physical LAN.

    ``system`` is populated lazily — empty until discovery runs.
    IDs within system are only meaningful relative to this installation.
    """

    id: str
    name: str  # "Home", "Office", "Cabin"
    network: NetworkProfile
    system: System = field(default_factory=System)


@dataclass
class RaumtubeRegistry:
    """All known installations.  Entry point for multi-site operation.

    Usage
    -----
    >>> reg = RaumtubeRegistry()
    >>> reg.add(Installation("home", "Home", NetworkProfile("net-home", "Home")))
    >>> reg.use("home")
    >>> inst = reg.active
    """

    installations: dict[str, Installation] = field(default_factory=dict)
    active_installation_id: str | None = None

    @property
    def active(self) -> Installation | None:
        if self.active_installation_id is None:
            return None
        return self.installations.get(self.active_installation_id)

    def add(self, installation: Installation) -> None:
        self.installations[installation.id] = installation

    def use(self, installation_id: str) -> None:
        if installation_id not in self.installations:
            available = list(self.installations.keys())
            raise KeyError(f"Installation {installation_id!r} not found. Available: {available}")
        self.active_installation_id = installation_id

    def get(self, installation_id: str) -> Installation:
        try:
            return self.installations[installation_id]
        except KeyError:
            available = list(self.installations.keys())
            raise KeyError(
                f"Installation {installation_id!r} not found. Available: {available}"
            ) from None
