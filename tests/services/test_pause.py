"""Pause zone — vertical slice tests.

All tests use Installation.ephemeral() and FakeRenderer — no network, no device.
"""

from __future__ import annotations

import pytest

from cprima_raumtube.model.aggregates import CommandStatus
from cprima_raumtube.model.ids import RendererUdn, ZoneId
from cprima_raumtube.model.playback import PlaybackFailureKind, PlaybackSessionState
from cprima_raumtube.model.protocol import Service
from cprima_raumtube.model.registry import Installation
from cprima_raumtube.model.topology import (
    Capability,
    CapabilityConfidence,
    CapabilitySource,
    PlaybackSupport,
    RendererProfile,
    ZoneRenderer,
)
from cprima_raumtube.services.playback_manager import PlaybackManager
from cprima_raumtube.soap import SoapFault
from emulator.renderer import FakeRenderer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ZONE = ZoneId("zone-test-1")


def _make_pm(fake: FakeRenderer, installation: Installation) -> PlaybackManager:
    return PlaybackManager(
        installation=installation,
        renderer=fake,  # type: ignore[arg-type]
        queue_manager=None,  # type: ignore[arg-type]
        stream_manager=None,  # type: ignore[arg-type]
    )


def _start_playing(installation: Installation, zone_id: ZoneId) -> None:
    ps = installation.state.get_or_create_playback_session(zone_id)
    ps.start()
    ps.mark_playing()


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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pause_succeeds() -> None:
    installation = Installation.ephemeral()
    _start_playing(installation, _ZONE)

    fake = FakeRenderer()
    pm = _make_pm(fake, installation)
    pm.pause(_ZONE)

    ps = installation.state.get_playback_session(_ZONE)
    assert ps is not None
    assert ps.state == PlaybackSessionState.PAUSED

    assert fake.pause_call_count == 1

    assert len(installation.state.command_log) == 1
    record = installation.state.command_log[0]
    assert record.status == CommandStatus.SUCCEEDED
    assert record.finished_at is not None

    events = installation.state.events_for_zone(_ZONE)
    assert len(events) == 1
    event = events[0]
    assert event.new_state == "PAUSED_PLAYBACK"  # type: ignore[union-attr]

    zone_state = installation.state.zone_states.get(_ZONE)
    assert zone_state is not None
    assert zone_state.desired is not None
    assert zone_state.desired.target_state == "PAUSED_PLAYBACK"
    assert zone_state.updated_at is not None


def test_pause_rejected_by_model() -> None:
    """Session not in PLAYING state — pause must raise before touching the device."""
    installation = Installation.ephemeral()
    # Session remains IDLE (never started)

    fake = FakeRenderer()
    pm = _make_pm(fake, installation)

    with pytest.raises(ValueError, match="pause requires PLAYING session"):
        pm.pause(_ZONE)

    assert fake.pause_call_count == 0
    assert len(installation.state.command_log) == 0


def test_pause_soap_fault() -> None:
    """SOAP fault from the renderer → session → ERROR / DEVICE_REJECTED, command FAILED."""
    installation = Installation.ephemeral()
    _start_playing(installation, _ZONE)

    fake = FakeRenderer(pause_raises=SoapFault("Action failed", code=500))
    pm = _make_pm(fake, installation)
    pm.pause(_ZONE)

    ps = installation.state.get_playback_session(_ZONE)
    assert ps is not None
    assert ps.state == PlaybackSessionState.ERROR
    assert ps.failure_kind == PlaybackFailureKind.DEVICE_REJECTED

    assert fake.pause_call_count == 1

    assert len(installation.state.command_log) == 1
    record = installation.state.command_log[0]
    assert record.status == CommandStatus.FAILED
    assert record.finished_at is not None


def test_pause_timeout() -> None:
    """Network timeout → session → ERROR / TIMEOUT, command TIMED_OUT."""
    installation = Installation.ephemeral()
    _start_playing(installation, _ZONE)

    fake = FakeRenderer(pause_raises=TimeoutError("timed out"))
    pm = _make_pm(fake, installation)
    pm.pause(_ZONE)

    ps = installation.state.get_playback_session(_ZONE)
    assert ps is not None
    assert ps.state == PlaybackSessionState.ERROR
    assert ps.failure_kind == PlaybackFailureKind.TIMEOUT

    assert fake.pause_call_count == 1

    assert len(installation.state.command_log) == 1
    record = installation.state.command_log[0]
    assert record.status == CommandStatus.TIMED_OUT
    assert record.finished_at is not None
    assert record.network_error == "timed out"


def test_pause_unsupported_capability() -> None:
    """Renderer profile declares pause not supported (CERTAIN) → raise before touching device."""
    installation = Installation.ephemeral()
    _start_playing(installation, _ZONE)

    fake = FakeRenderer()
    profile = RendererProfile(
        playback=PlaybackSupport(
            pause=Capability(
                name="pause",
                supported=False,
                source=CapabilitySource.SCPD,
                confidence=CapabilityConfidence.CERTAIN,
            )
        )
    )
    zr = _fake_zone_renderer(fake.udn, profile=profile)
    installation.inventory.register_zone_renderer(zr)

    pm = _make_pm(fake, installation)

    with pytest.raises(ValueError, match="does not support pause"):
        pm.pause(_ZONE)

    assert fake.pause_call_count == 0
    assert len(installation.state.command_log) == 0
