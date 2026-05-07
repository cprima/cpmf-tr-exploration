"""Tests for aggregate and registry invariants."""

import pytest

from cprima_raumtube.model.aggregates import CommandRecord, CommandStatus, RuntimeAggregate, new_id
from cprima_raumtube.model.registry import Installation
from cprima_raumtube.model.topology import DeviceLifecycle, PhysicalDevice


class TestInstallation:
    def test_ephemeral_factory(self):
        inst = Installation.ephemeral()
        assert inst.id == "ephemeral"
        assert inst.inventory is not None
        assert inst.topology is not None
        assert inst.library is not None
        assert inst.state is not None

    def test_get_or_create_queue_idempotent(self):
        inst = Installation.ephemeral()
        q1 = inst.state.get_or_create_queue("zone-1")
        q2 = inst.state.get_or_create_queue("zone-1")
        assert q1 is q2

    def test_get_or_create_queue_different_zones(self):
        inst = Installation.ephemeral()
        q1 = inst.state.get_or_create_queue("zone-1")
        q2 = inst.state.get_or_create_queue("zone-2")
        assert q1 is not q2
        assert q1.zone_id == "zone-1"
        assert q2.zone_id == "zone-2"


class TestRuntimeAggregate:
    def test_starts_empty(self):
        rt = RuntimeAggregate()
        assert rt.command_log == []
        assert rt.subscriptions == {}
        assert rt.device_queue_snapshots == {}

    def test_emit_appends_to_log(self):
        from cprima_raumtube.model.events import VolumeEvent

        rt = RuntimeAggregate()
        ev = VolumeEvent(zone_id="z1", new_volume=50)
        rt.emit(ev)
        assert len(rt.event_log) == 1
        assert rt.event_log[0] is ev

    def test_events_for_zone_filters(self):
        from cprima_raumtube.model.events import VolumeEvent

        rt = RuntimeAggregate()
        rt.emit(VolumeEvent(zone_id="z1", new_volume=50))
        rt.emit(VolumeEvent(zone_id="z2", new_volume=30))
        assert len(rt.events_for_zone("z1")) == 1
        assert len(rt.events_for_zone("z2")) == 1

    def test_slots_prevent_unknown_attributes(self):
        rt = RuntimeAggregate()
        with pytest.raises(AttributeError):
            rt.typo_field = 42  # type: ignore[attr-defined]


class TestCommandStatus:
    def test_is_str_enum(self):
        assert CommandStatus.PENDING == "pending"
        assert CommandStatus.SUCCEEDED == "succeeded"

    def test_command_record_default_status(self):
        cr = CommandRecord(id=new_id(), action="Play", target_udn="udn-1")
        assert cr.status == CommandStatus.PENDING
        assert cr.status == "pending"


class TestDeviceLifecycle:
    def test_is_str_enum(self):
        assert DeviceLifecycle.DISCOVERED == "discovered"
        assert DeviceLifecycle.OFFLINE == "offline"

    def test_physical_device_default_lifecycle(self):
        d = PhysicalDevice(
            udn="uuid:test",
            ip="10.0.0.1",
            friendly_name="Test Speaker",
            model="TestModel",
            role="speaker",
        )
        assert d.lifecycle == DeviceLifecycle.DISCOVERED
        assert d.lifecycle == "discovered"
        d.lifecycle = DeviceLifecycle.STALE
        assert d.lifecycle == "stale"
