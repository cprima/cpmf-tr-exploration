"""Tests for playback model invariants."""

from datetime import UTC, datetime, timedelta

import pytest

from cprima_raumtube.model.playback import (
    PlaybackPosition,
    PlaybackSession,
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
