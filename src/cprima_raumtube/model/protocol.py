"""UPnP protocol descriptors — Service, Action, StateVariable, ProtocolSnapshot, ProtocolInfo."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class StateVariable:
    name: str
    data_type: str
    allowed_values: list[str] | None = None
    default_value: str | None = None


@dataclass(frozen=True, slots=True)
class ActionArgument:
    name: str
    related_state_variable: str
    direction: str  # "in" | "out"


@dataclass(slots=True)
class Action:
    name: str
    in_args: list[ActionArgument] = field(default_factory=list)
    out_args: list[ActionArgument] = field(default_factory=list)


@dataclass(slots=True)
class Service:
    service_type: str
    control_url: str
    scpd_url: str
    event_sub_url: str
    service_id: str | None = None     # e.g. "urn:upnp-org:serviceId:AVTransport"
    version: int | None = None        # numeric suffix from service_type URN
    base_url: str | None = None       # device base URL; URLs may be relative without it
    actions: dict[str, Action] = field(default_factory=dict)
    state_variables: dict[str, StateVariable] = field(default_factory=dict)

    @property
    def short_name(self) -> str:
        """e.g. 'AVTransport' from the full URN."""
        return self.service_type.split(":")[-2]


@dataclass(frozen=True, slots=True)
class ProtocolInfo:
    """One entry from a GetProtocolInfo sink/source response.

    Wire format: ``protocol:network:contentFormat:additionalInfo``
    e.g. ``http-get:*:audio/mpeg:DLNA.ORG_PN=MP3``
    """

    protocol: str            # http-get
    network: str             # *
    content_format: str      # audio/mpeg
    additional_info: dict[str, str]
    raw: str

    @classmethod
    def parse(cls, raw: str) -> ProtocolInfo:
        """Parse a single protocolInfo string from GetProtocolInfo."""
        parts = raw.split(":", 3)
        protocol = parts[0] if len(parts) > 0 else ""
        network = parts[1] if len(parts) > 1 else "*"
        content_format = parts[2] if len(parts) > 2 else ""
        additional_str = parts[3] if len(parts) > 3 else ""
        additional_info: dict[str, str] = {}
        for item in additional_str.split(";"):
            item = item.strip()
            if "=" in item:
                k, _, v = item.partition("=")
                additional_info[k.strip()] = v.strip()
            elif item:
                additional_info[item] = ""
        return cls(
            protocol=protocol,
            network=network,
            content_format=content_format,
            additional_info=additional_info,
            raw=raw,
        )


@dataclass(slots=True)
class ProtocolSnapshot:
    """Raw XML snapshot of a fetched SCPD or event payload.

    Useful for reverse-engineering, debugging, and offline replay/testing.
    Not parsed — store the wire bytes as a string and parse on demand.
    """

    renderer_udn: str
    service_type: str
    raw_xml: str
    source_url: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


