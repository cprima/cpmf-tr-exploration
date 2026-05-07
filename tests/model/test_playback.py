"""Tests for playback model invariants."""

from datetime import UTC, datetime, timedelta

import pytest

from cprima_raumtube.model.playback import (
    PlaybackFailureKind,
    PlaybackPosition,
    PlaybackSession,
    PlaybackSessionState,
    TransportState,
    TransportStateName,
)


class TestTransportStateName:
    def test_is_str_enum(self):
        assert TransportStateName.PLAYING == "PLAYING"
        assert TransportStateName.STOPPED == "STOPPED"

    def test_membership_with_plain_strings(self):
        assert TransportStateName.STOPPED in {"STOPPED", "NO_MEDIA_PRESENT"}

    def test_all_values_present(self):
        names = {v.value for v in TransportStateName}
        assert names == {"STOPPED", "PLAYING", "PAUSED_PLAYBACK", "TRANSITIONING", "NO_MEDIA_PRESENT"}


class TestTransportState:
    def test_is_playing(self):
        ts = TransportState(state=TransportStateName.PLAYING, status="OK")
        assert ts.is_playing
        assert not ts.is_stopped

    def test_is_stopped(self):
        ts = TransportState(state=TransportStateName.STOPPED, status="OK")
        assert ts.is_stopped
        assert not ts.is_playing

    def test_no_media_present_is_stopped(self):
        ts = TransportState(state=TransportStateName.NO_MEDIA_PRESENT, status="OK")
        assert ts.is_stopped

    def test_transitioning_is_neither(self):
        ts = TransportState(state=TransportStateName.TRANSITIONING, status="OK")
        assert not ts.is_playing
        assert not ts.is_stopped


class TestPlaybackPosition:
    def test_no_extrapolation_when_paused(self):
        pos = PlaybackPosition(rel_seconds=30.0)
        assert pos.estimated_rel_seconds(playing=False) == pytest.approx(30.0)

    def test_extrapolates_when_playing(self):
        t0 = datetime.now(UTC)
        pos = PlaybackPosition(rel_seconds=10.0, updated_at=t0)
        t1 = t0 + timedelta(seconds=5)
        result = pos.estimated_rel_seconds(playing=True, now=t1)
        assert result == pytest.approx(15.0, abs=0.01)

    def test_age_seconds(self):
        t0 = datetime.now(UTC)
        pos = PlaybackPosition(rel_seconds=0.0, updated_at=t0)
        t1 = t0 + timedelta(seconds=10)
        assert pos.age_seconds(now=t1) == pytest.approx(10.0, abs=0.01)

    def test_slots_prevent_unknown_attributes(self):
        pos = PlaybackPosition(rel_seconds=0.0)
        with pytest.raises(AttributeError):
            pos.typo_field = 42  # type: ignore[attr-defined]


class TestPlaybackSession:
    def test_is_active_states(self):
        for state in ("starting", "transitioning", "playing", "paused"):
            ps = PlaybackSession(id="s1", zone_id="z1", state=state)  # type: ignore[arg-type]
            assert ps.is_active

    def test_is_not_active_states(self):
        for state in ("idle", "stopped", "error"):
            ps = PlaybackSession(id="s1", zone_id="z1", state=state)  # type: ignore[arg-type]
            assert not ps.is_active


class TestPlaybackSessionTransitions:
    def _new(self, state: PlaybackSessionState = PlaybackSessionState.IDLE) -> PlaybackSession:
        return PlaybackSession(id="s1", zone_id="z1", state=state)  # type: ignore[arg-type]

    # ── start() ──────────────────────────────────────────────────────────────

    def test_start_from_idle(self):
        ps = self._new(PlaybackSessionState.IDLE)
        ps.start()
        assert ps.state == PlaybackSessionState.STARTING

    def test_start_from_stopped(self):
        ps = self._new(PlaybackSessionState.STOPPED)
        ps.start()
        assert ps.state == PlaybackSessionState.STARTING

    def test_start_from_error(self):
        ps = self._new(PlaybackSessionState.ERROR)
        ps.start()
        assert ps.state == PlaybackSessionState.STARTING

    def test_start_invalid_from_playing(self):
        ps = self._new(PlaybackSessionState.PLAYING)
        with pytest.raises(ValueError, match="start"):
            ps.start()

    # ── mark_playing() ───────────────────────────────────────────────────────

    def test_mark_playing_from_starting(self):
        ps = self._new(PlaybackSessionState.STARTING)
        ps.mark_playing()
        assert ps.state == PlaybackSessionState.PLAYING

    def test_mark_playing_from_transitioning(self):
        ps = self._new(PlaybackSessionState.TRANSITIONING)
        ps.mark_playing()
        assert ps.state == PlaybackSessionState.PLAYING

    def test_mark_playing_invalid_from_idle(self):
        ps = self._new(PlaybackSessionState.IDLE)
        with pytest.raises(ValueError, match="mark_playing"):
            ps.mark_playing()

    # ── mark_transitioning() ─────────────────────────────────────────────────

    def test_mark_transitioning_from_starting(self):
        ps = self._new(PlaybackSessionState.STARTING)
        ps.mark_transitioning()
        assert ps.state == PlaybackSessionState.TRANSITIONING

    def test_mark_transitioning_from_playing(self):
        ps = self._new(PlaybackSessionState.PLAYING)
        ps.mark_transitioning()
        assert ps.state == PlaybackSessionState.TRANSITIONING

    # ── pause() / resume() ───────────────────────────────────────────────────

    def test_pause_from_playing(self):
        ps = self._new(PlaybackSessionState.PLAYING)
        ps.pause()
        assert ps.state == PlaybackSessionState.PAUSED

    def test_resume_from_paused(self):
        ps = self._new(PlaybackSessionState.PAUSED)
        ps.resume()
        assert ps.state == PlaybackSessionState.PLAYING

    def test_pause_invalid_from_paused(self):
        ps = self._new(PlaybackSessionState.PAUSED)
        with pytest.raises(ValueError, match="pause"):
            ps.pause()

    def test_resume_invalid_from_playing(self):
        ps = self._new(PlaybackSessionState.PLAYING)
        with pytest.raises(ValueError, match="resume"):
            ps.resume()

    # ── stop() ───────────────────────────────────────────────────────────────

    def test_stop_from_playing(self):
        ps = self._new(PlaybackSessionState.PLAYING)
        ps.stop()
        assert ps.state == PlaybackSessionState.STOPPED

    def test_stop_from_paused(self):
        ps = self._new(PlaybackSessionState.PAUSED)
        ps.stop()
        assert ps.state == PlaybackSessionState.STOPPED

    def test_stop_from_starting(self):
        ps = self._new(PlaybackSessionState.STARTING)
        ps.stop()
        assert ps.state == PlaybackSessionState.STOPPED

    def test_stop_invalid_from_idle(self):
        ps = self._new(PlaybackSessionState.IDLE)
        with pytest.raises(ValueError, match="stop"):
            ps.stop()

    def test_stop_invalid_from_stopped(self):
        ps = self._new(PlaybackSessionState.STOPPED)
        with pytest.raises(ValueError, match="stop"):
            ps.stop()

    # ── fail() ───────────────────────────────────────────────────────────────

    def test_fail_from_starting(self):
        ps = self._new(PlaybackSessionState.STARTING)
        ps.fail("device rejected", PlaybackFailureKind.DEVICE_REJECTED)
        assert ps.state == PlaybackSessionState.ERROR
        assert ps.error_message == "device rejected"
        assert ps.failure_kind == PlaybackFailureKind.DEVICE_REJECTED

    def test_fail_without_kind(self):
        ps = self._new(PlaybackSessionState.PLAYING)
        ps.fail("network timeout")
        assert ps.state == PlaybackSessionState.ERROR
        assert ps.failure_kind is None

    def test_fail_invalid_from_stopped(self):
        ps = self._new(PlaybackSessionState.STOPPED)
        with pytest.raises(ValueError, match="fail"):
            ps.fail("too late")

    # ── reset() ──────────────────────────────────────────────────────────────

    def test_reset_from_stopped(self):
        ps = self._new(PlaybackSessionState.STOPPED)
        ps.reset()
        assert ps.state == PlaybackSessionState.IDLE

    def test_reset_from_error_clears_fields(self):
        ps = self._new(PlaybackSessionState.ERROR)
        ps.error_message = "boom"
        ps.failure_kind = PlaybackFailureKind.NETWORK
        ps.reset()
        assert ps.state == PlaybackSessionState.IDLE
        assert ps.error_message is None
        assert ps.failure_kind is None

    def test_reset_invalid_from_playing(self):
        ps = self._new(PlaybackSessionState.PLAYING)
        with pytest.raises(ValueError, match="reset"):
            ps.reset()

    # ── version increment ─────────────────────────────────────────────────────

    def test_each_transition_increments_version(self):
        ps = self._new()
        assert ps.version == 0
        ps.start()
        assert ps.version == 1
        ps.mark_playing()
        assert ps.version == 2
        ps.pause()
        assert ps.version == 3
        ps.resume()
        assert ps.version == 4
        ps.stop()
        assert ps.version == 5
        ps.reset()
        assert ps.version == 6
