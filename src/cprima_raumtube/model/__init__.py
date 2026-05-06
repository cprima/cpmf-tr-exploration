"""cprima_raumtube.model — multiroom media system data model.

Hierarchy
---------
RaumtubeRegistry
└── Installation          one Raumfeld installation on one physical LAN
    ├── NetworkProfile    network coordinates (IP, CIDR, port)
    └── System            thin facade over three aggregate roots
        ├── TopologyAggregate   devices, zones, renderers, protocol snapshots
        ├── LibraryAggregate    items, playlists, resolutions, cache
        └── PlaybackAggregate   queues, streams, sessions, event log
"""

from __future__ import annotations

from cprima_raumtube.model.aggregates import (
    LibraryAggregate,
    PlaybackAggregate,
    System,
    TopologyAggregate,
    new_id,
)
from cprima_raumtube.model.events import (
    AnyEvent,
    GroupTopologyEvent,
    QueueEvent,
    TransportEvent,
    VolumeEvent,
)
from cprima_raumtube.model.media import (
    Library,
    LibrarySource,
    MediaItem,
    MediaItemRef,
    MediaResolution,
    Playlist,
    Queue,
    QueueItem,
    QueueOrigin,
)
from cprima_raumtube.model.playback import (
    PlaybackIntent,
    PlaybackPosition,
    PlaybackSession,
    TransportState,
)
from cprima_raumtube.model.protocol import (
    Action,
    ActionArgument,
    ProtocolSnapshot,
    Service,
    StateVariable,
)
from cprima_raumtube.model.registry import Installation, NetworkProfile, RaumtubeRegistry
from cprima_raumtube.model.streaming import CacheEntry, StreamSession, TranscodeProfile
from cprima_raumtube.model.topology import (
    Coordinator,
    Group,
    PhysicalDevice,
    RendererCapabilities,
    Room,
    Zone,
    ZoneRenderer,
)

__all__ = [
    # registry / installation
    "RaumtubeRegistry",
    "Installation",
    "NetworkProfile",
    # aggregates + facade
    "System",
    "TopologyAggregate",
    "LibraryAggregate",
    "PlaybackAggregate",
    "new_id",
    # protocol
    "Service",
    "Action",
    "ActionArgument",
    "StateVariable",
    "ProtocolSnapshot",
    # topology
    "PhysicalDevice",
    "Room",
    "Zone",
    "Coordinator",
    "RendererCapabilities",
    "ZoneRenderer",
    "Group",
    # media
    "Library",
    "LibrarySource",
    "MediaItem",
    "MediaResolution",
    "MediaItemRef",
    "Playlist",
    "Queue",
    "QueueItem",
    "QueueOrigin",
    # streaming
    "StreamSession",
    "CacheEntry",
    "TranscodeProfile",
    # playback
    "PlaybackSession",
    "PlaybackPosition",
    "TransportState",
    "PlaybackIntent",
    # events
    "TransportEvent",
    "VolumeEvent",
    "QueueEvent",
    "GroupTopologyEvent",
    "AnyEvent",
]
