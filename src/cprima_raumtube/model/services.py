"""Domain service interfaces — structural Protocols for model-layer orchestration.

These Protocols decouple orchestration logic from infrastructure:
  QueueReconciler   syncs AppQueue with device-reported state
  CapabilityProbe   probes a ZoneRenderer and returns a filled RendererProfile
  DriftEstimator    measures per-follower clock drift across a multiroom group
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cprima_raumtube.model.ids import RendererUdn
    from cprima_raumtube.model.media import AppQueue, DeviceQueueSnapshot, ReconciliationState
    from cprima_raumtube.model.topology import RendererProfile, SyncState, ZoneRenderer


@runtime_checkable
class QueueReconciler(Protocol):
    """Compare AppQueue with a device snapshot and return the reconciliation outcome."""

    def reconcile(
        self,
        queue: AppQueue,
        device_snapshot: DeviceQueueSnapshot,
    ) -> ReconciliationState: ...


@runtime_checkable
class CapabilityProbe(Protocol):
    """Live-probe a renderer via SOAP and return a populated RendererProfile."""

    def probe(self, renderer: ZoneRenderer) -> RendererProfile: ...


@runtime_checkable
class DriftEstimator(Protocol):
    """Estimate per-follower clock drift from a SyncState measurement."""

    def estimate(self, sync_state: SyncState) -> dict[RendererUdn, float]: ...
