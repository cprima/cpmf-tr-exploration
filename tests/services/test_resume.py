"""Resume zone — vertical slice tests."""

from __future__ import annotations

import pytest

from cprima_raumtube.model.aggregates import CommandStatus
from cprima_raumtube.model.ids import ZoneId
from cprima_raumtube.model.playback import PlaybackFailureKind, PlaybackSessionState
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


def _start_paused(installation: Installation, zone_id: ZoneId) -> None:
    ps = installation.state.get_or_create_playback_session(zone_id)
    ps.start()
    ps.mark_playing()
    ps.pause()


def test_resume_succeeds() -> None:
    installation = Installation.ephemeral()
    _start_paused(installation, _ZONE)

    fake = FakeRenderer()
    pm = _make_pm(fake, installation)
    pm.resume(_ZONE)

    ps = installation.state.get_playback_session(_ZONE)
    assert ps is not None
    assert ps.state == PlaybackSessionState.PLAYING

    assert fake.play_call_count == 1

    assert len(installation.state.command_log) == 1
    record = installation.state.command_log[0]
    assert record.action == "Play"
    assert record.status == CommandStatus.SUCCEEDED
    assert record.finished_at is not None

    events = installation.state.events_for_zone(_ZONE)
    assert len(events) == 1
    assert events[0].new_state == "PLAYING"  # type: ignore[union-attr]

    zone_state = installation.state.zone_states.get(_ZONE)
    assert zone_state is not None
    assert zone_state.desired is not None
    assert zone_state.desired.target_state == "PLAYING"
    assert zone_state.updated_at is not None


def test_resume_rejected_by_model() -> None:
    """Session not PAUSED — resume must raise before touching the device."""
    installation = Installation.ephemeral()
    # Session is IDLE (never started)

    fake = FakeRenderer()
    pm = _make_pm(fake, installation)

    with pytest.raises(ValueError, match="resume requires PAUSED session"):
        pm.resume(_ZONE)

    assert fake.play_call_count == 0
    assert len(installation.state.command_log) == 0


def test_resume_soap_fault() -> None:
    """SOAP fault → session ERROR / DEVICE_REJECTED, command FAILED."""
    installation = Installation.ephemeral()
    _start_paused(installation, _ZONE)

    fake = FakeRenderer(play_raises=SoapFault("Action failed", code=500))
    pm = _make_pm(fake, installation)
    pm.resume(_ZONE)

    ps = installation.state.get_playback_session(_ZONE)
    assert ps is not None
    assert ps.state == PlaybackSessionState.ERROR
    assert ps.failure_kind == PlaybackFailureKind.DEVICE_REJECTED

    assert fake.play_call_count == 1

    record = installation.state.command_log[0]
    assert record.status == CommandStatus.FAILED
    assert record.finished_at is not None


def test_resume_timeout() -> None:
    """Network timeout → session ERROR / TIMEOUT, command TIMED_OUT."""
    installation = Installation.ephemeral()
    _start_paused(installation, _ZONE)

    fake = FakeRenderer(play_raises=TimeoutError("timed out"))
    pm = _make_pm(fake, installation)
    pm.resume(_ZONE)

    ps = installation.state.get_playback_session(_ZONE)
    assert ps is not None
    assert ps.state == PlaybackSessionState.ERROR
    assert ps.failure_kind == PlaybackFailureKind.TIMEOUT

    record = installation.state.command_log[0]
    assert record.status == CommandStatus.TIMED_OUT
    assert record.network_error == "timed out"
