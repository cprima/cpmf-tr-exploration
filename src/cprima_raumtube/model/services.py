"""Domain service interfaces — structural Protocols for model-layer orchestration.

These Protocols decouple orchestration logic from infrastructure:
  RendererPort      contract for UPnP AVTransport + RenderingControl adapters
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
class RendererPort(Protocol):
    """Contract for UPnP AVTransport + RenderingControl adapters.

    Both the real Renderer (upnp/transport.py) and FakeRenderer (emulator/)
    must satisfy this interface. get_state() returns a transport state string;
    a future revision may narrow the return type to TransportStateName.
    """

    udn: RendererUdn

    def pause(self) -> None: ...
    def play(self, speed: str = "1") -> None: ...
    def stop(self) -> None: ...
    def set_uri(self, uri: str, metadata: str) -> None: ...
    def get_state(self) -> str: ...
    def get_volume(self) -> int: ...
    def set_volume(self, level: int) -> None: ...


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
