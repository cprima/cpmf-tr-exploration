# Glossary

Precise definitions for all domain terms used in `cprima_raumtube`.
Names match the exact class and field names in `src/cprima_raumtube/model/`.

---

## A

**`AnyEvent`**
Union type alias: `TransportEvent | VolumeEvent | QueueEvent | GroupTopologyEvent`.
Used as the element type of `PlaybackAggregate.event_log`.

**`Action`**
A single UPnP SOAP action defined in an SCPD document.
Has a name and a list of `ActionArgument` objects (in/out direction).

**`ActionArgument`**
One parameter of a UPnP `Action`. Fields: `name`, `direction` (`in`/`out`), `related_state_variable`.

---

## C

**`canonical_id`**
A stable, opaque string that uniquely identifies a piece of media independent of any transport URL.
Format: `"<source>:<id>"` — e.g. `"youtube:mAKxcNQpiSg"`, `"radio:somafm:groovesalad"`, `"file:/path/to.mp3"`.
Never expires. Used for deduplication and cache lookups.
Contrast with `resolved_uri` (ephemeral) and `source_locator` (user-facing).

**`CacheEntry`**
A fully downloaded and transcoded file on local disk.
Fields: `id`, `media_item_id`, `path`, `content_type`, `size_bytes`, `duration_seconds`.

**`Coordinator`**
A role assignment within a `Zone` or `Group`. Multiroom systems split three distinct concerns:

| Role | Responsibility |
|---|---|
| `transport` | Owns `SetAVTransportURI` / `Play` / `Stop` |
| `clock_master` | Drives synchronized audio clock across group members |
| `group_master` | Decides which renderers belong to the group |

Not all three necessarily live on the same UDN. See ADR-005.

---

## G

**`Group`**
A dynamic multiroom aggregate. One `coordinator_zone_id` drives playback for all `member_zone_ids`.
Groups are created and dissolved at runtime; membership is not static.

**`GroupTopologyEvent`**
Immutable event (`frozen=True`) recording a change in group topology.
Kind values: `zone_added`, `zone_removed`, `group_created`, `group_dissolved`.

---

## I

**`Installation`**
One Raumfeld installation on one physical LAN.
Has an `id`, a human `name` (e.g. "Home", "Office"), a `NetworkProfile`, and a lazily-populated `System`.
IDs within `System` are only meaningful relative to this installation.

---

## L

**`Library`**
A named, browsable collection of `LibrarySource` objects and cached `MediaItem` objects.

**`LibraryAggregate`**
Bounded context owning: `libraries`, `playlists`, `resolutions` (MediaResolution), `cache_entries`.
Shared across all zones within one `Installation`.

**`LibrarySource`**
A browsable/resolvable audio origin. `kind` values: `youtube`, `http`, `radio`, `local_file`, `dlna`, `raumfeld_media_server`.

---

## M

**`MediaItem`**
A single playable entity with stable identity.
Key fields:

| Field | Meaning |
|---|---|
| `canonical_id` | Stable opaque key — never expires |
| `source_locator` | Stable user-facing URL (e.g. `https://youtube.com/watch?v=…`) |
| `resolved_uri` | Ephemeral direct stream URL — may be `None` or stale |

Always prefer `MediaResolution` over `MediaItem.resolved_uri` for actual playback. See ADR-003.

**`MediaResolution`**
A time-bounded authoritative resolution of a `MediaItem` to a stream URI.
Has `expires_at`; call `is_valid(now)` before use. Resolver values: `yt-dlp`, `direct`, `cache`, `radio`.

**`MediaItemRef`**
An ordered reference to a `MediaItem` within a `Playlist`. Fields: `item_id`, `position`.

---

## N

**`NetworkProfile`**
Network coordinates for one Raumfeld installation.
Fields: `local_ip`, `source_ip` (SSDP bind; falls back to `local_ip`), `cidr`, `stream_port`, `discovery_timeout`.

---

## P

**`PhysicalDevice`**
Real hardware present on the LAN, discovered via SSDP.
Identified by `udn` and `ip`. `role` values: `hub`, `speaker`, `soundbar`, `unknown`.
Distinct from `ZoneRenderer` — see ADR-001.

**`Playlist`**
An ordered, saved collection of `MediaItemRef` objects. Separate from the runtime `Queue`.

**`PlaybackAggregate`**
Bounded context owning: `queues`, `stream_sessions`, `playback_sessions`, `event_log`.
Per-zone state; one `PlaybackSession` and one `Queue` per zone.

**`PlaybackIntent`**
What the caller wants to happen — resolved into a `PlaybackSession`.
Fields: `target_zone_id`, `source_uri`, `mode` (`auto`/`live`/`cached`), `enqueue`, `replace_queue`.

**`PlaybackPosition`**
Precise playback position at a known wall-clock instant.
`estimated_rel_seconds()` extrapolates forward from `updated_at` (assumes no pausing).

**`PlaybackSession`**
Runtime playback state for one zone. Ties together: zone ↔ queue ↔ current item ↔ stream session.
State values: `idle` → `starting` → `transitioning` → `playing` → `paused` → `stopped` / `error`.

**`ProtocolSnapshot`**
Raw SCPD XML captured from a renderer at discovery time.
Used for offline capability analysis, debugging, and replay testing.

---

## Q

**`Queue`**
The active playback list for a zone. Mutable during playback.
Mode flags: `repeat_mode` (`off`/`one`/`all`), `shuffle_mode`, `consume_mode`, `crossfade`.
`origin` values: `ad_hoc`, `playlist`, `radio`, `autoplay`.

**`QueueEvent`**
Immutable event recording a change to a zone's queue.
Kind values: `item_added`, `item_removed`, `cleared`, `index_changed`, `mode_changed`.

**`QueueItem`**
One slot in the active playback queue. References `MediaItem` by `media_item_id` (not embedded).
Resolve via `LibraryAggregate.find_item()`. State: `pending` → `resolved` → `playing` → `played` / `failed`.

---

## R

**`RaumtubeRegistry`**
Entry point for multi-installation operation. Holds all known `Installation` objects.
`active_installation_id` tracks the currently selected installation.

**`RendererCapabilities`**
Derived from SCPD parsing and `GetProtocolInfo`.
All fields default `False` until probed. Factory: `RendererCapabilities.unknown()`.
Key booleans: `seek`, `pause`, `next_previous`, `set_next_uri`, `volume_control`. See ADR-006.

**`Room`**
A user-facing physical location (e.g. "HomeOffice"). Contains one or more `PhysicalDevice` UDNs.

---

## S

**`Service`**
A UPnP service descriptor parsed from SCPD. `short_name` property strips the URN prefix
(e.g. `"urn:schemas-upnp-org:service:AVTransport:1"` → `"AVTransport"`).

**`source_locator`**
The stable, user-visible URL or path for a `MediaItem`.
Example: `"https://youtube.com/watch?v=mAKxcNQpiSg"`. Never expires. Used for display and sharing.

**`StateVariable`**
A UPnP state variable from an SCPD document. Has `name`, `data_type`, and optional `allowed_values`.

**`StreamSession`**
Descriptor for an active or completed HTTP stream delivery.
`mode` values:

| Mode | Description |
|---|---|
| `cached_file` | Static MP3 served with Range support (seekable) |
| `live_pipe` | ffmpeg stdout piped to HTTP (no seeking) |
| `direct_url` | Renderer fetches source URL directly |

State lifecycle: `starting` → `active` → `draining` → `closed` (or `failed` from any state).

**`System`**
Thin facade holding three aggregate roots for one Installation.
Delegates to `TopologyAggregate`, `LibraryAggregate`, `PlaybackAggregate`.

---

## T

**`TopologyAggregate`**
Bounded context owning: `physical_devices`, `rooms`, `zones`, `zone_renderers`, `groups`, `protocol_snapshots`.

**`TransportState`**
Snapshot of UPnP AVTransport state. `state` values: `STOPPED`, `PLAYING`, `PAUSED_PLAYBACK`, `TRANSITIONING`, `NO_MEDIA_PRESENT`.

**`TransportEvent`**
Immutable event recording a transport state change for a zone.
Fields: `zone_id`, `new_state`, `old_state`, `timestamp`.

---

## V

**`VolumeEvent`**
Immutable event recording a volume change.
Fields: `zone_id`, `new_volume`, `old_volume`, `timestamp`.

---

## Z

**`Zone`**
A named, controllable playback target. Maps to exactly one `ZoneRenderer`.
`kind` values: `single_room`, `group`, `virtual`.
Property `transport_coordinator` returns the `Coordinator` with `role="transport"`.

**`ZoneRenderer`**
A virtual UPnP renderer hosted on the Raumfeld Expand hub.
Endpoint for all SOAP playback control. UDN differs from the physical device UDN.
`capabilities` is `None` until probed; check `renderer.probed` before use. See ADR-001, ADR-006.
