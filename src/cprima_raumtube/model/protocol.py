"""UPnP protocol descriptors — Service, Action, StateVariable, ProtocolSnapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class StateVariable:
    name: str
    data_type: str
    allowed_values: list[str] | None = None
    default_value: str | None = None


@dataclass
class ActionArgument:
    name: str
    related_state_variable: str
    direction: str  # "in" | "out"


@dataclass
class Action:
    name: str
    in_args: list[ActionArgument] = field(default_factory=list)
    out_args: list[ActionArgument] = field(default_factory=list)


@dataclass
class Service:
    service_type: str
    control_url: str
    scpd_url: str
    event_sub_url: str
    actions: dict[str, Action] = field(default_factory=dict)
    state_variables: dict[str, StateVariable] = field(default_factory=dict)

    @property
    def short_name(self) -> str:
        """e.g. 'AVTransport' from the full URN."""
        return self.service_type.split(":")[-2]


@dataclass
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
