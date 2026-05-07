"""Set volume — vertical slice tests."""

from __future__ import annotations

import pytest

from cprima_raumtube.model.aggregates import CommandStatus
from cprima_raumtube.model.ids import RendererUdn, ZoneId
from cprima_raumtube.model.protocol import Service
from cprima_raumtube.model.registry import Installation
from cprima_raumtube.model.topology import (
    AudioSupport,
    Capability,
    CapabilityConfidence,
    CapabilitySource,
    RendererProfile,
    ZoneRenderer,
)
from cprima_raumtube.services.playback_manager import PlaybackManager
from cprima_raumtube.soap import SoapFault
from emulator.renderer import FakeRenderer

_ZONE = ZoneId("zone-test-1")


def _make_pm(fake: FakeRenderer, installation: Installation) -> PlaybackManager:
    return PlaybackManager(
        installation=installation,
        renderer=fake,  # type: ignore[arg-type]
        queue_manager=None,  # type: ignore[arg-type]
        stream_manager=None,  # type: ignore[arg-type]
    )


def _fake_zone_renderer(udn: RendererUdn, profile: RendererProfile | None = None) -> ZoneRenderer:
    avt = Service(
        service_type="urn:schemas-upnp-org:service:AVTransport:1",
        control_url="/avt/control",
        scpd_url="/avt/scpd",
        event_sub_url="/avt/event",
    )
    rc = Service(
        service_type="urn:schemas-upnp-org:service:RenderingControl:1",
        control_url="/rc/control",
        scpd_url="/rc/scpd",
        event_sub_url="/rc/event",
    )
    return ZoneRenderer(
        udn=udn,
        name="Fake Renderer",
        location_url="http://10.0.0.1:49200",
        avtransport=avt,
        rendering_control=rc,
        profile=profile,
    )


def test_set_volume_succeeds() -> None:
    installation = Installation.ephemeral()

    fake = FakeRenderer()
    pm = _make_pm(fake, installation)
    pm.set_volume(_ZONE, 75)

    assert fake.set_volume_call_count == 1
    assert fake._volume == 75

    record = installation.state.command_log[0]
    assert record.action == "SetVolume"
    assert record.status == CommandStatus.SUCCEEDED
    assert record.finished_at is not None
    assert record.details == {"level": "75"}

    events = installation.state.events_for_zone(_ZONE)
    assert len(events) == 1
    event = events[0]
    assert event.new_volume == 75  # type: ignore[union-attr]
    assert event.old_volume is None  # no prior observed state

    zone_state = installation.state.zone_states.get(_ZONE)
    assert zone_state is not None
    assert zone_state.rendering.volume["Master"] == 75
    assert zone_state.updated_at is not None


def test_set_volume_updates_from_known_prior() -> None:
    """old_volume is populated when rendering state was already observed."""
    installation = Installation.ephemeral()
    zone_state = installation.state.get_or_create_zone_state(_ZONE)
    zone_state.rendering.volume["Master"] = 40

    fake = FakeRenderer()
    pm = _make_pm(fake, installation)
    pm.set_volume(_ZONE, 60)

    event = installation.state.events_for_zone(_ZONE)[0]
    assert event.old_volume == 40  # type: ignore[union-attr]
    assert event.new_volume == 60  # type: ignore[union-attr]


def test_set_volume_out_of_range() -> None:
    """Volume outside 0-100 raises before touching the device."""
    installation = Installation.ephemeral()
    fake = FakeRenderer()
    pm = _make_pm(fake, installation)

    with pytest.raises(ValueError, match="Volume must be 0-100"):
        pm.set_volume(_ZONE, 101)

    assert fake.set_volume_call_count == 0
    assert len(installation.state.command_log) == 0


def test_set_volume_soap_fault() -> None:
    """SOAP fault → command FAILED, rendering state NOT updated."""
    installation = Installation.ephemeral()

    fake = FakeRenderer(set_volume_raises=SoapFault("Action failed", code=500))
    pm = _make_pm(fake, installation)
    pm.set_volume(_ZONE, 80)

    assert fake.set_volume_call_count == 1

    record = installation.state.command_log[0]
    assert record.status == CommandStatus.FAILED
    assert record.finished_at is not None

    zone_state = installation.state.zone_states.get(_ZONE)
    assert zone_state is not None
    assert zone_state.rendering.volume.get("Master") is None  # not updated


def test_set_volume_unsupported_capability() -> None:
    """Renderer profile declares volume not supported (CERTAIN) → raise before device."""
    installation = Installation.ephemeral()

    fake = FakeRenderer()
    profile = RendererProfile(
        audio=AudioSupport(
            volume=Capability(
                name="volume",
                supported=False,
                source=CapabilitySource.SCPD,
                confidence=CapabilityConfidence.CERTAIN,
            )
        )
    )
    zr = _fake_zone_renderer(fake.udn, profile=profile)
    installation.inventory.register_zone_renderer(zr)

    pm = _make_pm(fake, installation)

    with pytest.raises(ValueError, match="does not support volume control"):
        pm.set_volume(_ZONE, 50)

    assert fake.set_volume_call_count == 0
    assert len(installation.state.command_log) == 0
