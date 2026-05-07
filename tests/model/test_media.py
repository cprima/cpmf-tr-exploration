"""Tests for media model invariants."""

import pytest

from cprima_raumtube.model.media import AppQueue, InsertMode, QueueItem, QueueItemState, QueueSyncState


def _item(n: int) -> QueueItem:
    return QueueItem(id=f"i{n}", media_item_id=f"m{n}")


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
        q.replace_all([_item(1)])
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


class TestQueueSyncState:
    def test_default_values(self):
        s = QueueSyncState(zone_id="z1")
        assert not s.in_sync
        assert s.pending_push == 0
        assert s.failed_push == 0
        assert not s.device_differs
        assert s.last_device_snapshot_id is None
        assert s.last_synced_at is None
