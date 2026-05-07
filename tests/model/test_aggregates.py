"""Tests for aggregate and registry invariants."""

from datetime import UTC, datetime, timedelta

import pytest

from cprima_raumtube.model.aggregates import (
    CommandRecord,
    CommandStatus,
    RuntimeAggregate,
    SubscriptionRenewalState,
    SubscriptionState,
    new_id,
)
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


class TestSubscriptionStateTransitions:
    def _sub(self, state: SubscriptionRenewalState = SubscriptionRenewalState.ACTIVE) -> SubscriptionState:
        return SubscriptionState(
            sid="sid-1",
            renderer_udn="udn-1",
            service_type="urn:schemas-upnp-org:service:AVTransport:1",
            callback_url="http://10.0.0.1:8080/notify",
            renewal_state=state,
        )

    # ── mark_renewing ─────────────────────────────────────────────────────────

    def test_mark_renewing_from_active(self):
        sub = self._sub(SubscriptionRenewalState.ACTIVE)
        sub.mark_renewing()
        assert sub.renewal_state == SubscriptionRenewalState.RENEWING

    def test_mark_renewing_from_failed(self):
        sub = self._sub(SubscriptionRenewalState.FAILED)
        sub.mark_renewing()
        assert sub.renewal_state == SubscriptionRenewalState.RENEWING

    def test_mark_renewing_invalid_from_expired(self):
        sub = self._sub(SubscriptionRenewalState.ACTIVE)
        sub.mark_expired()
        with pytest.raises(ValueError, match="mark_renewing"):
            sub.mark_renewing()

    def test_mark_renewing_invalid_from_renewing(self):
        sub = self._sub(SubscriptionRenewalState.ACTIVE)
        sub.mark_renewing()
        with pytest.raises(ValueError, match="mark_renewing"):
            sub.mark_renewing()

    # ── mark_active ───────────────────────────────────────────────────────────

    def test_mark_active_from_renewing(self):
        sub = self._sub()
        sub.mark_renewing()
        t = datetime.now(UTC) + timedelta(seconds=1800)
        sub.mark_active(t)
        assert sub.renewal_state == SubscriptionRenewalState.ACTIVE
        assert sub.expires_at == t
        assert sub.last_renewed_at is not None

    def test_mark_active_clears_failure_reason(self):
        sub = self._sub(SubscriptionRenewalState.FAILED)
        sub.failure_reason = "network timeout"
        sub.mark_renewing()
        sub.mark_active(datetime.now(UTC) + timedelta(seconds=1800))
        assert sub.failure_reason is None

    def test_mark_active_invalid_from_active(self):
        sub = self._sub()
        t = datetime.now(UTC) + timedelta(seconds=1800)
        with pytest.raises(ValueError, match="mark_active"):
            sub.mark_active(t)

    # ── mark_expired ──────────────────────────────────────────────────────────

    def test_mark_expired_from_active(self):
        sub = self._sub()
        sub.mark_expired()
        assert sub.renewal_state == SubscriptionRenewalState.EXPIRED

    def test_mark_expired_from_renewing(self):
        sub = self._sub()
        sub.mark_renewing()
        sub.mark_expired()
        assert sub.renewal_state == SubscriptionRenewalState.EXPIRED

    def test_mark_expired_invalid_from_failed(self):
        sub = self._sub(SubscriptionRenewalState.FAILED)
        with pytest.raises(ValueError, match="mark_expired"):
            sub.mark_expired()

    # ── mark_failed ───────────────────────────────────────────────────────────

    def test_mark_failed_from_renewing(self):
        sub = self._sub()
        sub.mark_renewing()
        sub.mark_failed("connection refused")
        assert sub.renewal_state == SubscriptionRenewalState.FAILED
        assert sub.failure_reason == "connection refused"

    def test_mark_failed_from_active(self):
        sub = self._sub()
        sub.mark_failed("device rejected subscription")
        assert sub.renewal_state == SubscriptionRenewalState.FAILED

    def test_mark_failed_invalid_from_expired(self):
        sub = self._sub()
        sub.mark_expired()
        with pytest.raises(ValueError, match="mark_failed"):
            sub.mark_failed("too late")

    # ── version increment ─────────────────────────────────────────────────────

    def test_each_transition_increments_version(self):
        sub = self._sub()
        assert sub.version == 0
        sub.mark_renewing()
        assert sub.version == 1
        sub.mark_active(datetime.now(UTC) + timedelta(seconds=1800))
        assert sub.version == 2
        sub.mark_renewing()
        assert sub.version == 3
        sub.mark_failed("timeout")
        assert sub.version == 4
        sub.mark_renewing()
        assert sub.version == 5
        sub.mark_expired()
        assert sub.version == 6

    def test_initial_version_is_zero(self):
        sub = self._sub()
        assert sub.version == 0


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
