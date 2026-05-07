"""cprima_raumtube.model -- multiroom media system data model.

MODEL_VERSION = "v0.0.1"

Four-layer structure
--------------------
Raw protocol
  ProtocolSnapshot, Service, Action, StateVariable, ProtocolInfo

Discovered inventory  (slow-changing, set during SSDP/SCPD probing)
  PhysicalDevice (DeviceLifecycle, StationButton), ZoneRenderer, Room -- in DeviceInventory
  RendererProfile, *Support, Capability, CapabilityObservation, RendererQuirk
  DiscoverySnapshot

Volatile topology  (changes at runtime: zone splits, group joins)
  Zone, Group (SyncState), Coordinator -- in TopologyState

Runtime state  (per-zone, changes every few seconds)
  AppQueue, DeviceQueueSnapshot, PlaybackSession, ZoneRuntimeState (CurrentItemMetadata)
  StreamSession, CommandRecord (CommandStatus), SubscriptionState -- in RuntimeAggregate

Registry
  RaumtubeRegistry -> Installation (holds all four layers + NetworkProfile)
"""

from __future__ import annotations

from cprima_raumtube.model.aggregates import (
    CommandRecord,
    CommandStatus,
    DeviceInventory,
    DiscoverySnapshot,
    LibraryAggregate,
    RuntimeAggregate,
    SubscriptionRenewalState,
    SubscriptionState,
    TopologyState,
    new_id,
)
from cprima_raumtube.model.events import (
    AnyEvent,
    GroupTopologyEvent,
    QueueEvent,
    TransportEvent,
    VolumeEvent,
)
from cprima_raumtube.model.ids import (
    GroupId,
    InstallationId,
    MediaItemId,
    PhysicalDeviceUdn,
    QueueId,
    RendererUdn,
    RoomId,
    ServiceType,
    StreamSessionId,
    ZoneId,
)
from cprima_raumtube.model.media import (
    AppQueue,
    DeviceQueueSnapshot,
    InsertMode,
    Library,
    LibrarySource,
    MediaItem,
    MediaItemRef,
    MediaResolution,
    Playlist,
    QueueEndBehavior,
    QueueItem,
    QueueItemState,
    QueueOrigin,
    QueueSyncState,
    ReconciliationState,
)
from cprima_raumtube.model.playback import (
    CurrentItemMetadata,
    DesiredTransportState,
    PlaybackFailureKind,
    PlaybackIntent,
    PlaybackPosition,
    PlaybackSession,
    PlaybackSessionState,
    RenderingState,
    TransportState,
    TransportStateName,
    ZoneRuntimeState,
)
from cprima_raumtube.model.protocol import (
    Action,
    ActionArgument,
    ProtocolInfo,
    ProtocolSnapshot,
    Service,
    StateVariable,
)
from cprima_raumtube.model.registry import Installation, NetworkProfile, RaumtubeRegistry
from cprima_raumtube.model.services import (
    CapabilityProbe,
    DriftEstimator,
    QueueReconciler,
)
from cprima_raumtube.model.streaming import (
    CacheEntry,
    StreamSession,
    StreamSessionState,
    TranscodeProfile,
)
from cprima_raumtube.model.topology import (
    AudioSupport,
    Capability,
    CapabilityConfidence,
    CapabilityObservation,
    CapabilitySource,
    ContentSupport,
    Coordinator,
    DeviceLifecycle,
    DeviceSupport,
    Group,
    PhysicalDevice,
    PlaybackSupport,
    RendererProfile,
    RendererQuirk,
    Room,
    StationButton,
    StreamingSupport,
    SyncQuality,
    SyncState,
    Zone,
    ZoneRenderer,
)

MODEL_VERSION = "v0.0.1"

__all__ = [
    # schema version
    "MODEL_VERSION",
    # registry / installation
    "RaumtubeRegistry",
    "Installation",
    "NetworkProfile",
    # aggregates (four layers)
    "DeviceInventory",
    "TopologyState",
    "LibraryAggregate",
    "RuntimeAggregate",
    "DiscoverySnapshot",
    "CommandRecord",
    "CommandStatus",
    "SubscriptionState",
    "SubscriptionRenewalState",
    "new_id",
    # protocol -- raw layer
    "Service",
    "Action",
    "ActionArgument",
    "StateVariable",
    "ProtocolInfo",
    "ProtocolSnapshot",
    # topology -- discovered inventory
    "DeviceLifecycle",
    "PhysicalDevice",
    "Room",
    "Zone",
    "Coordinator",
    "ZoneRenderer",
    "StationButton",
    "Group",
    "SyncState",
    "SyncQuality",
    # renderer profile -- normalised capabilities
    "RendererProfile",
    "PlaybackSupport",
    "AudioSupport",
    "StreamingSupport",
    "ContentSupport",
    "DeviceSupport",
    "Capability",
    "CapabilitySource",
    "CapabilityConfidence",
    "CapabilityObservation",
    "RendererQuirk",
    # media
    "Library",
    "LibrarySource",
    "MediaItem",
    "MediaResolution",
    "MediaItemRef",
    "Playlist",
    "AppQueue",
    "InsertMode",
    "ReconciliationState",
    "QueueEndBehavior",
    "QueueItem",
    "QueueItemState",
    "QueueOrigin",
    "DeviceQueueSnapshot",
    "QueueSyncState",
    # streaming
    "StreamSession",
    "StreamSessionState",
    "CacheEntry",
    "TranscodeProfile",
    # playback -- runtime state
    "PlaybackSession",
    "PlaybackSessionState",
    "PlaybackFailureKind",
    "PlaybackPosition",
    "TransportState",
    "TransportStateName",
    "PlaybackIntent",
    "RenderingState",
    "ZoneRuntimeState",
    "CurrentItemMetadata",
    "DesiredTransportState",
    # domain service protocols
    "QueueReconciler",
    "CapabilityProbe",
    "DriftEstimator",
    # events
    "TransportEvent",
    "VolumeEvent",
    "QueueEvent",
    "GroupTopologyEvent",
    "AnyEvent",
    # typed IDs
    "ZoneId",
    "RendererUdn",
    "MediaItemId",
    "QueueId",
    "StreamSessionId",
    "InstallationId",
    "GroupId",
    "PhysicalDeviceUdn",
    "RoomId",
    "ServiceType",
]
