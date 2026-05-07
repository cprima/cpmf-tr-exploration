"""Property-based tests using hypothesis."""
from __future__ import annotations

from hypothesis import given, strategies as st

from cprima_raumtube.model.media import AppQueue, QueueItem
from cprima_raumtube.model.playback import PlaybackPosition
from cprima_raumtube.model.protocol import ProtocolInfo


class TestProtocolInfoProperties:
    @given(st.text(min_size=1), st.text(), st.text(), st.text())
    def test_parse_raw_always_preserved(self, proto: str, net: str, fmt: str, extra: str) -> None:
        raw = f"{proto}:{net}:{fmt}:{extra}"
        pi = ProtocolInfo.parse(raw)
        assert pi.raw == raw

    @given(st.text(alphabet=st.characters(blacklist_characters=":"), min_size=1))
    def test_parse_single_field(self, proto: str) -> None:
        pi = ProtocolInfo.parse(proto)
        assert pi.protocol == proto
        assert pi.network == "*"
        assert pi.content_format == ""


class TestPlaybackPositionProperties:
    @given(st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False))
    def test_non_negative_rel_seconds_accepted(self, secs: float) -> None:
        pos = PlaybackPosition(rel_seconds=secs)
        assert pos.rel_seconds == secs

    @given(st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False))
    def test_negative_rel_seconds_rejected(self, secs: float) -> None:
        import pytest
        with pytest.raises(ValueError, match="rel_seconds"):
            PlaybackPosition(rel_seconds=secs)


class TestAppQueueProperties:
    @given(st.integers(min_value=0, max_value=9))
    def test_has_next_consistent_with_index(self, n_items: int) -> None:
        q = AppQueue(id="q1", zone_id="z1")
        for i in range(n_items):
            q.append(QueueItem(id=f"i{i}", media_item_id=f"m{i}"))
        if n_items == 0:
            assert not q.has_next
        else:
            q.current_index = 0
            # has_next is True iff there are more items after current
            assert q.has_next == (n_items > 1)

    @given(st.integers(min_value=0, max_value=9))
    def test_current_item_matches_index(self, idx: int) -> None:
        q = AppQueue(id="q1", zone_id="z1")
        for i in range(idx + 1):
            q.append(QueueItem(id=f"i{i}", media_item_id=f"m{i}"))
        q.current_index = idx
        assert q.current_item is not None
        assert q.current_item.id == f"i{idx}"
