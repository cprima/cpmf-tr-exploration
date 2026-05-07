"""Stop zone — vertical slice tests."""

from __future__ import annotations

from cprima_raumtube.model.aggregates import CommandStatus
from cprima_raumtube.model.ids import ZoneId
from cprima_raumtube.model.playback import PlaybackSessionState
from cprima_raumtube.model.registry import Installation
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


def _start_playing(installation: Installation, zone_id: ZoneId) -> None:
    ps = installation.state.get_or_create_playback_session(zone_id)
    ps.start()
    ps.mark_playing()


def test_stop_succeeds() -> None:
    installation = Installation.ephemeral()
    _start_playing(installation, _ZONE)

    fake = FakeRenderer()
    pm = _make_pm(fake, installation)
    pm.stop(_ZONE)

    ps = installation.state.get_playback_session(_ZONE)
    assert ps is not None
    assert ps.state == PlaybackSessionState.STOPPED

    assert fake.stop_call_count == 1

    assert len(installation.state.command_log) == 1
    record = installation.state.command_log[0]
    assert record.action == "Stop"
    assert record.status == CommandStatus.SUCCEEDED
    assert record.finished_at is not None

    events = installation.state.events_for_zone(_ZONE)
    assert len(events) == 1
    assert events[0].new_state == "STOPPED"  # type: ignore[union-attr]

    zone_state = installation.state.zone_states.get(_ZONE)
    assert zone_state is not None
    assert zone_state.desired is not None
    assert zone_state.desired.target_state == "STOPPED"
    assert zone_state.updated_at is not None


def test_stop_no_session() -> None:
    """No active session — SOAP stop still fires, no session error."""
    installation = Installation.ephemeral()

    fake = FakeRenderer()
    pm = _make_pm(fake, installation)
    pm.stop(_ZONE)

    assert fake.stop_call_count == 1

    record = installation.state.command_log[0]
    assert record.status == CommandStatus.SUCCEEDED


def test_stop_soap_fault() -> None:
    """SOAP fault → command FAILED, but local session still transitions to STOPPED."""
    installation = Installation.ephemeral()
    _start_playing(installation, _ZONE)

    fake = FakeRenderer(stop_raises=SoapFault("Action failed", code=500))
    pm = _make_pm(fake, installation)
    pm.stop(_ZONE)

    ps = installation.state.get_playback_session(_ZONE)
    assert ps is not None
    assert ps.state == PlaybackSessionState.STOPPED  # local cleanup still happened

    assert fake.stop_call_count == 1

    record = installation.state.command_log[0]
    assert record.status == CommandStatus.FAILED
    assert record.finished_at is not None

    # No event emitted since device state is unknown
    assert len(installation.state.events_for_zone(_ZONE)) == 0


def test_stop_timeout() -> None:
    """Network timeout → command TIMED_OUT, local session still STOPPED."""
    installation = Installation.ephemeral()
    _start_playing(installation, _ZONE)

    fake = FakeRenderer(stop_raises=TimeoutError("timed out"))
    pm = _make_pm(fake, installation)
    pm.stop(_ZONE)

    ps = installation.state.get_playback_session(_ZONE)
    assert ps is not None
    assert ps.state == PlaybackSessionState.STOPPED

    record = installation.state.command_log[0]
    assert record.status == CommandStatus.TIMED_OUT
    assert record.network_error == "timed out"
    assert len(installation.state.events_for_zone(_ZONE)) == 0
