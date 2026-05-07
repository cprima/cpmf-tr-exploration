"""Tests for media model invariants."""

import pytest

from cprima_raumtube.model.media import (
    AppQueue,
    InsertMode,
    QueueItem,
    QueueItemState,
    QueueSyncState,
)


def _item(n: int, state: QueueItemState = QueueItemState.PENDING) -> QueueItem:
    return QueueItem(id=f"i{n}", media_item_id=f"m{n}", state=state)


class TestAppQueue:
    def test_current_item_empty_queue(self):
        q = AppQueue(id="q1", zone_id="z1")
        assert q.current_item is None

    def test_current_item_no_index(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1)])
        q.current_index = None
        assert q.current_item is None  # current_index is None

    def test_current_item_returns_correct_item(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1), _item(2)])
        q.current_index = 1
        assert q.current_item is q.items[1]

    def test_has_next_false_when_empty(self):
        q = AppQueue(id="q1", zone_id="z1")
        assert not q.has_next

    def test_has_next_false_at_last_item(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1), _item(2)])
        q.current_index = 1
        assert not q.has_next

    def test_has_next_true_before_last_item(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1), _item(2)])
        q.current_index = 0
        assert q.has_next

    def test_has_next_repeat_all_always_true(self):
        q = AppQueue(id="q1", zone_id="z1", repeat_mode="all")
        q.replace_all([_item(1)])
        q.current_index = 0
        assert q.has_next

    def test_clear_resets_index(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1)])
        q.current_index = 0
        q.clear()
        assert q.items == ()
        assert q.current_index is None

    def test_append(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.append(_item(1))
        assert len(q.items) == 1

    def test_slots_prevent_unknown_attributes(self):
        q = AppQueue(id="q1", zone_id="z1")
        with pytest.raises(AttributeError):
            q.typo_field = 42  # type: ignore[attr-defined]

    def test_remove_at_adjusts_index(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1), _item(2), _item(3)])
        q.current_index = 1
        removed = q.remove_at(0)
        assert removed.id == "i1"
        assert q.current_index == 0  # shifted down by 1
        assert len(q.items) == 2

    def test_items_property_is_immutable(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.append(_item(1))
        with pytest.raises((AttributeError, TypeError)):
            q.items.append(_item(2))  # type: ignore[union-attr]

    def test_enqueue_append_mode(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.enqueue(_item(1))
        q.enqueue(_item(2))
        assert len(q.items) == 2
        assert q.current_index == 0

    def test_enqueue_play_next(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1), _item(2), _item(3)])
        q.seek_to(0)
        q.enqueue(_item(4), mode=InsertMode.PLAY_NEXT)
        assert q.items[1].id == "i4"

    def test_enqueue_replace_remaining(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1), _item(2), _item(3)])
        q.seek_to(0)
        q.enqueue(_item(4), mode=InsertMode.REPLACE_REMAINING)
        assert len(q.items) == 2
        assert q.items[1].id == "i4"

    def test_advance_moves_forward(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1), _item(2), _item(3)])
        assert q.advance() is not None
        assert q.current_index == 1

    def test_advance_returns_none_at_end(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1)])
        result = q.advance()
        assert result is None

    def test_rewind_moves_back(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1), _item(2)])
        q.seek_to(1)
        result = q.rewind()
        assert result is not None
        assert q.current_index == 0

    def test_seek_to_valid(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1), _item(2), _item(3)])
        item = q.seek_to(2)
        assert item.id == "i3"
        assert q.current_index == 2

    def test_seek_to_out_of_range(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1)])
        with pytest.raises(IndexError):
            q.seek_to(5)

    def test_mark_failed_updates_state(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([_item(1)])  # PENDING → valid for mark_failed
        q.mark_failed("i1")
        assert q.items[0].state == QueueItemState.FAILED

    def test_version_increments_on_mutation(self):
        q = AppQueue(id="q1", zone_id="z1")
        v0 = q.version
        q.enqueue(_item(1))
        assert q.version == v0 + 1
        q.enqueue(_item(2))
        assert q.version == v0 + 2
        q.advance()  # moves from index 0 to 1 — version increments
        assert q.version == v0 + 3
        q.clear()
        assert q.version == v0 + 4


class TestQueueItem:
    """QueueItem state machine invariants."""

    # ── construction / factory methods ───────────────────────────────────────

    def test_default_state_is_pending(self):
        qi = QueueItem(id="i1", media_item_id="m1")
        assert qi.state == QueueItemState.PENDING

    def test_new_pending_factory(self):
        qi = QueueItem.new_pending("i1", "m1")
        assert qi.state == QueueItemState.PENDING
        assert qi.id == "i1"
        assert qi.media_item_id == "m1"

    def test_rehydrate_accepts_any_state(self):
        for state in QueueItemState:
            qi = QueueItem.rehydrate("i1", "m1", state)
            assert qi.state == state

    def test_rehydrate_restores_stream_id(self):
        qi = QueueItem.rehydrate("i1", "m1", QueueItemState.PLAYED, resolved_stream_id="sess-x")
        assert qi.resolved_stream_id == "sess-x"

    # ── mark_resolved ─────────────────────────────────────────────────────────

    def test_mark_resolved_from_pending(self):
        qi = _item(1)
        qi.mark_resolved("sess-1")
        assert qi.state == QueueItemState.RESOLVED
        assert qi.resolved_stream_id == "sess-1"

    def test_mark_resolved_from_resolved_updates_stream_id(self):
        qi = _item(1, QueueItemState.RESOLVED)
        qi.mark_resolved("sess-2")
        assert qi.resolved_stream_id == "sess-2"

    def test_mark_resolved_invalid_from_playing(self):
        qi = _item(1, QueueItemState.RESOLVED)
        qi.mark_playing()
        with pytest.raises(ValueError, match="mark_resolved"):
            qi.mark_resolved("sess-x")

    # ── mark_playing ──────────────────────────────────────────────────────────

    def test_mark_playing_from_resolved(self):
        qi = _item(1, QueueItemState.RESOLVED)
        qi.mark_playing()
        assert qi.state == QueueItemState.PLAYING

    def test_mark_playing_invalid_from_pending(self):
        qi = _item(1)
        with pytest.raises(ValueError, match="mark_playing"):
            qi.mark_playing()

    def test_mark_playing_invalid_from_played(self):
        qi = _item(1, QueueItemState.RESOLVED)
        qi.mark_playing()
        qi.mark_played()
        with pytest.raises(ValueError, match="mark_playing"):
            qi.mark_playing()

    # ── mark_played ───────────────────────────────────────────────────────────

    def test_mark_played_from_playing(self):
        qi = _item(1, QueueItemState.RESOLVED)
        qi.mark_playing()
        qi.mark_played()
        assert qi.state == QueueItemState.PLAYED

    def test_mark_played_invalid_from_resolved(self):
        qi = _item(1, QueueItemState.RESOLVED)
        with pytest.raises(ValueError, match="mark_played"):
            qi.mark_played()

    # ── mark_failed ───────────────────────────────────────────────────────────

    def test_mark_failed_from_pending(self):
        qi = _item(1)
        qi.mark_failed()
        assert qi.state == QueueItemState.FAILED

    def test_mark_failed_from_resolved(self):
        qi = _item(1, QueueItemState.RESOLVED)
        qi.mark_failed()
        assert qi.state == QueueItemState.FAILED

    def test_mark_failed_from_playing(self):
        qi = _item(1, QueueItemState.RESOLVED)
        qi.mark_playing()
        qi.mark_failed()
        assert qi.state == QueueItemState.FAILED

    def test_mark_failed_invalid_from_played(self):
        qi = _item(1, QueueItemState.RESOLVED)
        qi.mark_playing()
        qi.mark_played()
        with pytest.raises(ValueError, match="mark_failed"):
            qi.mark_failed()

    # ── reset ─────────────────────────────────────────────────────────────────

    def test_reset_from_played(self):
        qi = _item(1, QueueItemState.RESOLVED)
        qi.mark_resolved("s1")
        qi.mark_playing()
        qi.mark_played()
        qi.reset()
        assert qi.state == QueueItemState.PENDING
        assert qi.resolved_stream_id is None

    def test_reset_from_failed(self):
        qi = _item(1)
        qi.mark_failed()
        qi.reset()
        assert qi.state == QueueItemState.PENDING

    def test_reset_invalid_from_pending(self):
        qi = _item(1)
        with pytest.raises(ValueError, match="reset"):
            qi.reset()


class TestAppQueueDiscipline:
    """AppQueue current-item wrappers and play_next."""

    def _queue_with_resolved_item(self) -> AppQueue:
        q = AppQueue(id="q1", zone_id="z1")
        q.enqueue(_item(1, QueueItemState.RESOLVED))
        return q

    # ── mark_current_resolved ─────────────────────────────────────────────────

    def test_mark_current_resolved_sets_stream_id(self):
        q = self._queue_with_resolved_item()
        q.mark_current_resolved("sess-abc")
        assert q.current_item is not None
        assert q.current_item.resolved_stream_id == "sess-abc"

    def test_mark_current_resolved_increments_version(self):
        q = self._queue_with_resolved_item()
        v = q.version
        q.mark_current_resolved("sess-x")
        assert q.version == v + 1

    def test_mark_current_resolved_no_current_raises(self):
        q = AppQueue(id="q1", zone_id="z1")
        with pytest.raises(ValueError, match="mark_current_resolved"):
            q.mark_current_resolved("sess-x")

    # ── mark_current_playing ──────────────────────────────────────────────────

    def test_mark_current_playing_transitions_state(self):
        q = self._queue_with_resolved_item()
        q.mark_current_resolved("s1")
        q.mark_current_playing()
        assert q.current_item is not None
        assert q.current_item.state == QueueItemState.PLAYING

    def test_mark_current_playing_increments_version(self):
        q = self._queue_with_resolved_item()
        q.mark_current_resolved("s1")
        v = q.version
        q.mark_current_playing()
        assert q.version == v + 1

    def test_mark_current_playing_from_pending_raises(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.enqueue(_item(1))  # PENDING
        with pytest.raises(ValueError, match="mark_playing"):
            q.mark_current_playing()

    # ── mark_current_played ───────────────────────────────────────────────────

    def test_mark_current_played_transitions_state(self):
        q = self._queue_with_resolved_item()
        q.mark_current_resolved("s1")
        q.mark_current_playing()
        q.mark_current_played()
        assert q.current_item is not None
        assert q.current_item.state == QueueItemState.PLAYED

    def test_mark_current_played_no_current_raises(self):
        q = AppQueue(id="q1", zone_id="z1")
        with pytest.raises(ValueError, match="mark_current_played"):
            q.mark_current_played()

    # ── mark_current_failed ───────────────────────────────────────────────────

    def test_mark_current_failed_from_playing(self):
        q = self._queue_with_resolved_item()
        q.mark_current_resolved("s1")
        q.mark_current_playing()
        q.mark_current_failed()
        assert q.current_item is not None
        assert q.current_item.state == QueueItemState.FAILED

    def test_mark_current_failed_from_pending(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.enqueue(_item(1))  # PENDING
        q.mark_current_failed()
        assert q.current_item is not None
        assert q.current_item.state == QueueItemState.FAILED

    # ── play_next ─────────────────────────────────────────────────────────────

    def test_play_next_marks_played_and_advances(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([
            _item(1, QueueItemState.RESOLVED),
            _item(2, QueueItemState.RESOLVED),
        ])
        q.mark_current_resolved("s1")
        q.mark_current_playing()
        next_item = q.play_next()
        assert next_item is not None
        assert next_item.id == "i2"
        assert q.items[0].state == QueueItemState.PLAYED

    def test_play_next_returns_none_at_end(self):
        q = self._queue_with_resolved_item()
        q.mark_current_resolved("s1")
        q.mark_current_playing()
        result = q.play_next()
        assert result is None
        assert q.items[0].state == QueueItemState.PLAYED

    def test_play_next_skips_mark_played_if_not_playing(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([
            _item(1, QueueItemState.RESOLVED),
            _item(2, QueueItemState.RESOLVED),
        ])
        # current item is RESOLVED, not PLAYING — play_next should still advance
        next_item = q.play_next()
        assert next_item is not None
        assert next_item.id == "i2"
        assert q.items[0].state == QueueItemState.RESOLVED  # not marked played

    def test_play_next_increments_version(self):
        q = AppQueue(id="q1", zone_id="z1")
        q.replace_all([
            _item(1, QueueItemState.RESOLVED),
            _item(2, QueueItemState.RESOLVED),
        ])
        q.mark_current_resolved("s1")
        q.mark_current_playing()
        v = q.version
        q.play_next()
        # version increments: mark_played + advance
        assert q.version > v


class TestQueueSyncState:
    def test_default_values(self):
        s = QueueSyncState(zone_id="z1")
        assert not s.in_sync
        assert s.pending_push == 0
        assert s.failed_push == 0
        assert not s.device_differs
        assert s.last_device_snapshot_id is None
        assert s.last_synced_at is None
