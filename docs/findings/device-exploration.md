# Device Capability Exploration — Raumfeld Expand + Speakers

Findings from SCPD enumeration, live SOAP probing, GENA subscriptions, HTTP endpoint scanning,
and decompiled Teufel Android app (APK JADX extraction). Conducted 2026-05-07.

---

## Evidence Grading

| Grade | Meaning |
|---|---|
| `[CONFIRMED]` | SOAP action invoked; expected response received |
| `[OBSERVED]` | Seen in GENA event or HTTP response body |
| `[APK]` | From JADX-decompiled Android app source |
| `[INFERRED]` | Logical conclusion from other evidence |
| `[UNTESTED]` | In SCPD but not yet invoked |
| `[HTTP-500]` | Action exists but returned 500 (wrong context/state) |

---

## Topology Discovered (Discovery + Device Descriptions)

### Expand hub (10.38.20.100) — Virtual Zone Renderers

The Expand synthesizes one virtual `MediaRenderer:1` per configured zone, served on separate ports:

| Zone name | UDN | Port | Model desc |
|---|---|---|---|
| 🏠 HomeOffice | uuid:a322ee73-d2f2-466e-a1b1-36e60f577928 | 49935 | Virtual Media Player |
| WoZi | uuid:9a3cd069-82c8-481a-963f-237af22e337f | 52405 | Virtual Media Player |
| Küche | uuid:681d1c05-2270-4a62-b43d-9777f49590ac | 49306 | Virtual Media Player |

Also hosted on Expand:
- **Raumfeld MediaServer** (`uuid:da40e00b-c4c0-46b6-9ffb-e42efcb59fbf`) — port 52186
- **Raumfeld ConfigDevice** (`uuid:9d566d57-53a2-49fe-84c5-010c2c169f08`) — port 51563
- **SetupService device** (`uuid:0d51c514-ed15-449f-aced-dfd1fc0e6951`) — port 50076

Expand metadata: `raumfeld:protocolVersion=16351`, `raumfeld:hardwareType=5`, serial `00:0d:b9:1a:82:00`

### Physical Speakers

| Name | IP | UDN | Model | Hardware type | Open ports |
|---|---|---|---|---|---|
| Speaker 🏠 HomeOffice | 10.38.20.175 | uuid:cebbe132-29a1-40f9-8b23-c5006aa27d6c | One S | — | 8888, 52859, 54129, 55196, 55425, 56390 |
| Speaker Küche | 10.38.20.35 | uuid:3a472670-a62a-4f20-9df4-dbb4e7de35dd | One S | — | 8888, 50480, 52752, 53535, 53753, 56097 |
| Speaker WoZi | 10.38.20.105 | uuid:84d1a7f9-45a7-4e44-88d6-42d7187e37e9 | Cinebar Lux | 27 | 8888, 53351, 53717, 56249, 58305, 58392 |

---

## Proprietary AVTransport Actions (Zone Renderers)

All on zone virtual renderer; control URL `/TransportService/Control`.

| Action | Args | Status | Notes |
|---|---|---|---|
| `BendAVTransportURI` | InstanceID, CurrentURI, CurrentURIMetaData | Unknown | Possibly smooth URL handoff mid-stream |
| `CancelSleepTimer` | InstanceID | Working | Cancels active sleep timer |
| `EnterAutomaticStandby` | InstanceID, Room | Working | Puts room into auto standby |
| `EnterManualStandby` | InstanceID, Room | Working | Manual standby |
| `LeaveStandby` | InstanceID, Room | Working | Wake from standby |
| `FastForward` | InstanceID | → Position:string | Fast-forward with position output |
| `Rewind` | InstanceID | → Position:string | Rewind with position output |
| `GetSleepTimerState` | InstanceID | `Active=0, SecondsUntilSleep=0` | Sleep timer state query |
| `StartSleepTimer` | InstanceID, SecondsUntilSleep, SecondsForVolumeRamp | Working | Auto-off timer |
| `GetSpotifyPreset` | InstanceID, Button:ui4 | HTTP 500 (no active Spotify session) | Spotify preset recall |
| `GetStreamProperties` | — | `CurrentContentType="", CurrentBitrate=0` | Live stream metadata (returns during playback) |
| `GetCurrentTransportActions` | InstanceID | `Play,Previous,Seek,RepeatTrack,Repeat` | Available actions (context-dependent) |
| `LikeCurrentTrack` | — | Unknown | Likes current track on music service |
| `UnlikeCurrentTrack` | — | Unknown | |
| `Next` / `Previous` | InstanceID | Working | Native queue navigation |
| `SetPlayMode` | InstanceID, NewPlayMode | Working | NORMAL, SHUFFLE, REPEAT_ONE, REPEAT_ALL, RANDOM |
| `SetResourceForCurrentStream` | ResourceURI | Unknown | Hot-swap resource URL for current stream |
| `SetNextStartTriggerTime` | InstanceID, TimeService, StartTime | (Cinebar only) | Scheduled playback start |

### SetNextAVTransportURI

Confirmed on Cinebar Lux (`/AVTransport/ctrl`); enables gapless track transitions.
The zone virtual renderer on the Expand also supports this for multi-speaker zones.

---

## Proprietary RenderingControl Actions (Cinebar Lux)

Control URL: `http://10.38.20.105:58305/RenderingControl/ctrl`

| Action | Result | Notes |
|---|---|---|
| `GetFilter` | `LowDB=0, MidDB=0, HighDB=461` | 3-band EQ (values in centidB? 461 = +4.61 dB treble) |
| `SetFilter` | — | 3-band EQ control: LowDB, MidDB, HighDB |
| `GetBalance` | HTTP 500 | Stereo balance (may require Cinebar to be active) |
| `SetBalance` | — | Stereo balance |
| `GetLineInStreamURL` | HTTP 500 | Returns URL + MIME type for line-in stream |
| `QueryFilter` | HTTP 500 | Check if a named filter (e.g. `stereo-widening`) is enabled |
| `ToggleFilter` | — | Enable/disable named filter: `stereo-widening` |
| `GetVolumeDB` / `SetVolumeDB` | — | dB-precision volume, channels: Master, Input |
| `GetDeviceSetting` / `SetDeviceSetting` | HTTP 500 | Generic named settings (names unknown) |
| `PlaySystemSound` | — | Play beep: `Success` or `Failure` |
| `ChangeVolume` | — | Relative volume adjustment (i1 amount) |

Expand zone renderers also expose `GetRoomVolume`/`SetRoomVolume`/`GetRoomMute`/`SetRoomMute` for per-room control within a multi-speaker zone.

---

## Raumfeld-Specific Services

### SetupService (`urn:schemas-raumfeld-com:service:SetupService:1`)

Control URL: `http://10.38.20.100:50076/SetupService/ctrl`

| Action | Result |
|---|---|
| `GetInfo` | `SoftwareVersion=2.17.4` |
| `GetNetworkInfo` | `Address=10.38.20.100, AccessPoint="" (wired), SignalStrength=0` |
| `GetDeviceMode` | `Mode=MASTER` (valid values: WAIT_FOR_SETUP, CLIENT, MASTER) |
| `GetUpdateInfo` | `Version="" (no update), SecondsSinceLastCheck=1217` |
| `CheckForUpdate` | Triggers OTA check |
| `DoUpdate` | Triggers firmware install |
| `SendReport` | Sends support report to Teufel |

### ConfigService (`urn:schemas-raumfeld-com:service:ConfigService:1`)

Control URL: `http://10.38.20.100:51563/ConfigService/Control`

| Action | Result |
|---|---|
| `GetPublicKey` | RSA-1024 public key (base64 PEM) |
| `GetRevision` | `163726` (preference store revision) |
| `GetPreferences(PublicKey)` | `Preferences="" (empty or encrypted), Revision=163726` |
| `SetPreferences` | Versioned key-value store with conflict resolution (ForceOverwrite, Cancel) |
| `GetDevice(meta-server)` | `uuid:da40e00b-c4c0-46b6-9ffb-e42efcb59fbf` (MediaServer UDN) |
| `GetDevice(renderer)` | `""` (no single renderer — Expand has multiple zones) |

Preferences appear to be RSA-encrypted when sent; client uses server public key to encrypt.
Purpose: store user preferences in the hub rather than in the app (survives app reinstall).

---

## ContentDirectory — Full CDS Tree

Root (`0`) has 9 direct children:

| ID | raumfeld:name | Title | Children |
|---|---|---|---|
| `0/RadioTime` | RadioTime | TuneIn | 6 |
| `0/My Music` | My Music | My Music | 9 |
| `0/Favorites` | Favorites | Teufel Favourites | 5 |
| `0/Playlists` | Playlists | Playlists | 2 |
| `0/Spotify` | Spotify | Spotify | 0 (not logged in) |
| `0/Line In` | Line In | Line-in | 2 |
| `0/Zones` | Zones | Zones | 0 |
| `0/Renderers` | Renderers | Renderers | 3 |
| `0/DemoTracks` | DemoTracks | Demo Tracks | 1 |

Database: **2,352 resources**, 309 KB disk usage (max 30 MB).

Notable: `0/CustomStreams`, `0/Scenes`, `0/Bluetooth`, `0/GoogleCast`, `0/Tidal`, `0/SoundCloud`
all appear in the app source but return HTTP 500 — these services are not configured/active.

### Favorites subtree

| ID | Title | Children |
|---|---|---|
| `0/Favorites/MyFavorites` | Favourites | 3 (BR Schlager, Deutschlandfunk, hr1) |
| `0/Favorites/RecentlyPlayed` | Last Played | 39 |
| `0/Favorites/MostPlayed` | My Trends | 8 |
| `0/Favorites/Timers` | Timers | 0 |
| `0/Favorites/Categories` | Categories | 2 |

The 3 favorites are TuneIn stations with `raumfeld:durability=120` (cache TTL in seconds).
TuneIn URLs embed the Expand's MAC address as `serial=00:0d:b9:1a:82:00` for authentication.

### Line In

Two items — one per One S speaker:

| Speaker | URL |
|---|---|
| Speaker Küche (10.38.20.35) | `http://10.38.20.35:8888/stream.flac` |
| Speaker 🏠 HomeOffice (10.38.20.175) | `http://10.38.20.175:8888/stream.flac` |

UPnP class: `object.item.audioItem.audioBroadcast.lineIn`
MIME: `audio/x-flac` — served by `Server: Raumfeld Renderer`, `Transfer-Encoding: chunked`, live stream.
The Cinebar Lux does **not** expose a line-in via this CDS path (has digital inputs only).

**Port 8888** is open on all three physical speakers including the Cinebar. Cinebar's stream
may differ (RaumfeldGenerator service, digital input, or similar).

### ContentDirectory Actions

| Action | Status | Notes |
|---|---|---|
| `Browse` | Working | Standard UPnP browse |
| `Search` | Working | `SearchCaps=dc:title` only |
| `GetSearchCapabilities` | Working | Returns `dc:title` |
| `GetSortCapabilities` | Working | Returns `""` (no sort) |
| `QueryDatabaseState` | Working | Returns resource counts and disk usage |
| `GetIndexerStatus` | Working | Returns `""` (idle) |
| `CreateQueue` | Not tested | Creates a server-side queue |
| `AddItemToQueue` | Not tested | Adds CDS item to queue |
| `AddContainerToQueue` | Not tested | Bulk add |
| `RemoveFromQueue` | Not tested | Remove item by position range |
| `MoveInQueue` | Not tested | Reorder |
| `RenameQueue` | Not tested | |
| `Shuffle` | Not tested | Returns PlaylistID + metadata |
| `AssignStationButton` | **Confirmed working** | See station buttons section |
| `GetStationButtonAssignment` | **Confirmed working** | |
| `GetSourceInfo` | Working | All sources return 0 tracks (no USB/NFS/SMB attached) |
| `RescanSource` | Not tested | |
| `ResetDatabase` | **Do not test** — destructive | Clears media index |

---

## Station Buttons (Preset Buttons) — Complete Protocol

**Naming**: "Preset buttons" in app UI, "station buttons" in code and CDS paths.

**Assignment wire call** (from `AssignStationButtonAction.java`):
```
ContentDirectory.AssignStationButton(
  Renderer   = "uuid:<physical-speaker-udn>",  // NOT the zone UDN
  Button     = "1",                             // slot 1–4
  ObjectID   = "0/RadioTime/Search/s-s44975"   // CDS object ID from music picker
)
```
Returns empty body on success (HTTP 200).

**Reading back**:
```
GetStationButtonAssignment(Renderer, Button)
→ <ObjectID>0/Renderers/{udn}/StationButtons/538</ObjectID>
```
Returns an internal stable reference, not the original ObjectID.

**Unassignment**: `AssignStationButton(Renderer, Button, ObjectID="")` — confirmed.

**CDS storage path**: `0/Renderers/{renderer-udn}/StationButtons/{n}`

Stored item includes `raumfeld:button={slot}`, `refID={original-object-id}`, and a
**resolved playback `res` URL** captured at assignment time:
```xml
<item refID="0/RadioTime/Search/s-s44975">
  <raumfeld:button>1</raumfeld:button>
  <dc:title>BR Schlager</dc:title>
  <raumfeld:ebrowse>http://opml.radiotime.com/Tune.ashx?…&c=ebrowse</raumfeld:ebrowse>
  <res protocolInfo="http-get:*:audio/x-mpegurl:*" bitrate="128">
    http://opml.radiotime.com/Tune.ashx?id=e186948974&sid=s44975&…&serial=00:0d:b9:1a:82:00
  </res>
</item>
```

**What can be stored**: TuneIn stations, local music, playlists, any browsable CDS object with a `res` element.

**Spotify variant**: `AssignSpotifyStationButtonWithMetadataAction` — passes `SpotifyMetadata`
(JSON, Moshi-serialized) in `OptionalMetadata` field.

**What cannot be stored** (explicit app-level blocks): Bluetooth playback, Google Cast playback.

**Raw URL attempt**: Calling with empty `ObjectID` + DIDL in `OptionalMetadata` returns HTTP 200
but creates no `StationButtons` entry server-side.

**Device capability flags** (from APK source): `supportsStationButtonNumbers` (boolean),
`numberOfStationButtons` (integer, typically 4).

---

## Protocol Traces

Annotated wire-level traces for the three most important interaction patterns.

### Trace A: Station Button Assignment [CONFIRMED]

```
# SOAP request — ContentDirectory.AssignStationButton
POST http://10.38.20.100:52186/cd/Control HTTP/1.1
Content-Type: text/xml; charset=utf-8
SOAPAction: "urn:schemas-upnp-org:service:ContentDirectory:1#AssignStationButton"

<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <u:AssignStationButton xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <Renderer>uuid:cebbe132-29a1-40f9-8b23-c5006aa27d6c</Renderer>
      <Button>1</Button>
      <ObjectID>0/RadioTime/Search/s-s44975</ObjectID>
      <OptionalMetadata></OptionalMetadata>
    </u:AssignStationButton>
  </s:Body>
</s:Envelope>

# Response — HTTP 200
<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <u:AssignStationButtonResponse xmlns:u="...ContentDirectory:1"/>
  </s:Body>
</s:Envelope>

# Resulting CDS entry at 0/Renderers/uuid:cebbe132-.../StationButtons/538
<item refID="0/RadioTime/Search/s-s44975">
  <raumfeld:button>1</raumfeld:button>
  <dc:title>BR Schlager</dc:title>
  <raumfeld:ebrowse>http://opml.radiotime.com/Tune.ashx?…&c=ebrowse</raumfeld:ebrowse>
  <res protocolInfo="http-get:*:audio/x-mpegurl:*" bitrate="128">
    http://opml.radiotime.com/Tune.ashx?id=e186948974&sid=s44975&…&serial=00:0d:b9:1a:82:00
  </res>
</item>
```

The hub resolves the TuneIn `ObjectID` to a concrete playback URL at assignment time (snapshot
semantics). The physical button press at runtime uses this stored URL directly — no CDS lookup
occurs at playback time [CONFIRMED].

### Trace B: GENA Subscription + Initial Event (AVTransport) [CONFIRMED]

```
# Subscribe request
SUBSCRIBE http://10.38.20.100:49935/TransportService/Event HTTP/1.1
CALLBACK: <http://10.38.20.29:12345/notify>
NT: upnp:event
TIMEOUT: Second-120

# Subscribe response
HTTP/1.1 200 OK
SID: uuid:4398bdcf-9a38-456a-b487-255138341e20
TIMEOUT: Second-300

# Initial NOTIFY (SEQ: 0) — key fields in LastChange
TransportState:          STOPPED
CurrentTrackURI:         http://10.38.20.29:8080/stream.mp3      ← last-played URI persists
CurrentTransportActions: Play,Previous,Seek,RepeatTrack,Repeat
RoomStates:              uuid:9b109c9c-…=STOPPED                 ← Raumfeld extension
SleepTimerActive:        0                                        ← Raumfeld extension
ContentType:             ""                                       ← Raumfeld extension
Bitrate:                 0                                        ← Raumfeld extension
```

The hub overrides the client-requested timeout (120 s) with its own value (300 s). The initial
NOTIFY fires immediately after subscription and includes the full current state [CONFIRMED].

### Trace C: Line-In Stream Access [CONFIRMED]

```
# HTTP request
GET http://10.38.20.35:8888/stream.flac HTTP/1.1

# Response
HTTP/1.1 200 OK
Content-Type: audio/x-flac
Transfer-Encoding: chunked
Server: Raumfeld Renderer

fLaC…   ← FLAC stream header (libFLAC 1.3.1) followed by live audio data
```

The stream begins immediately with a valid FLAC header. No authentication, no session setup.
The server does not close the connection — the response is an infinite chunked stream of live
audio [CONFIRMED].

---

## GENA Events — Raumfeld Extensions

Subscribed to `http://10.38.20.100:49935/TransportService/Event` and `/RenderingService/Event`.

### AVTransport LastChange (zone renderer)

Beyond standard UPnP state variables, these are present:

| Variable | Example value | Notes |
|---|---|---|
| `RoomStates` | `uuid:9b109c9c-493a-40a6-9951-30561eebf5b0=STOPPED` | Per-room playback state within a zone |
| `SleepTimerActive` | `0` | Sleep timer state |
| `SecondsUntilSleep` | `0` | Countdown |
| `ContentType` | `""` | MIME type of current stream (filled during playback) |
| `Bitrate` | `0` | Current stream bitrate bps (filled during playback) |

### RenderingControl LastChange (zone renderer)

| Variable | Example value | Notes |
|---|---|---|
| `RoomVolumes` | `uuid:9b109c9c-...-30561eebf5b0=28` | Per-room volume within a zone |
| `RoomMutes` | `uuid:9b109c9c-...-30561eebf5b0=0` | Per-room mute state |

The per-room UUIDs (`uuid:9b109c9c-493a-40a6-9951-30561eebf5b0`) represent **rooms** (physical speaker groupings within a zone), separate from the renderer UDNs.

---

## Supported Audio Formats (GetProtocolInfo — Zone Renderer)

```
dlna-playcontainer:*:application/xml:*
http-get:*:audio/alac:*
http-get:*:audio/flac:*
http-get:*:audio/m4a:*  http-get:*:audio/m4b:*
http-get:*:audio/mp3:*  http-get:*:audio/mpeg:*  http-get:*:audio/mpeg3:*  http-get:*:audio/x-mpeg3:*  http-get:*:audio/x-mp3:*  http-get:*:audio/x-mpeg:*
http-get:*:audio/mp4:*
http-get:*:audio/ogg:*  http-get:*:audio/x-ogg:*  http-get:*:audio/vorbis:*  http-get:*:audio/x-vorbis+ogg:*  http-get:*:application/ogg:*  http-get:*:application/x-ogg:*
http-get:*:audio/wav:*  http-get:*:audio/x-wav:*
http-get:*:audio/x-ac3:*
http-get:*:audio/x-flac:*
http-get:*:audio/x-m4b:*
http-get:*:audio/x-mpegurl:*
http-get:*:application/xspf+xml:*
http-get:*:video/mp4:*
```

**Notable**: ALAC, FLAC, AC3, and XSPF playlist format are all supported natively.
`dlna-playcontainer` indicates DLNA play-container (multi-item playlist) support.

---

## App Content Model (from APK — JADX decompilation)

### Raumfeld custom namespace keys (`raumfeld:*`)

| Key | Purpose |
|---|---|
| `raumfeld:button` | Preset button slot number |
| `raumfeld:durability` | Cache TTL in seconds (e.g. 120 for TuneIn stations) |
| `raumfeld:duration` | Content duration (separate from `res@duration`) |
| `raumfeld:ebrowse` | Enhanced browse URL (TuneIn/radio browser link) |
| `raumfeld:likedOnMusicService` | Track liked status on connected service |
| `raumfeld:name` | Programmatic container/item name (locale-independent) |
| `raumfeld:section` | Content section (RadioTime, My Music, Favorites, etc.) |
| `raumfeld:sourceID` | Source identifier |
| `raumfeld:totalPlaytime` | Aggregated play time |
| `raumfeld:waveformURI` | Waveform visualization URL |

### Content sections (`ContentSections.java`)

`Bluetooth`, `CustomStreams`, `DemoTracks`, `DynamicFavorites`, `Favorites`, `GoogleCast`,
`Line In`, `My Music`, `Playlists`, `RadioTime`, `Renderers`, `Scenes`, `SoundCloud`,
`Spotify`, `Tidal`, `Timers`, `Zones`

### UPnP class hierarchy (from `ContentItem` / `ContentContainer` factories)

Items: `object.item.audioItem.musicTrack`, `…audioBroadcast.radio`, `…audioBroadcast.lineIn`,
`…audioBook`, `…podcastEpisode`

Containers: `object.container.album.musicAlbum[.compilation]`, `…person.musicArtist`,
`…person.user`, `…streamContainer`, `…person.musicComposer`, `…genre.musicGenre[.soundCloud]`,
`…albumContainer`, `…favoritesContainer`, `…playlistContainer[.queue][.shuffle[.search]]`,
`…trackContainer[.allTracks]`, `…storageFolder`, `…storageVolume`,
`…location.bookmarkable`, `…mood`

### `ContentObject` — key fields

`assignedStationButton`, `resourceURI`, `eBrowseURL`, `durability`, `expires`, `expirationTime`,
`section`, `sourceID`, `waveformURL` — all populated from DIDL-Lite XML map.

---

## HTTP Endpoint Scan

| Target | Port 80 | Notes |
|---|---|---|
| Expand hub | REFUSED | No web UI on standard port |
| UPnP ports (49935, 51563, 50076, 52186) | HTTP 404 at `/` | Only respond to SOAP/device-description paths |
| Physical speakers (port 8888) | HTTP 200 | Live line-in FLAC stream (chunked transfer) |

No undocumented REST API, web UI, JSON-RPC, or CGI endpoints found on any device.
All functionality is exposed exclusively through UPnP SOAP services.

---

## Behavioral Semantics

**Station button resolution timing.** `AssignStationButton` captures the fully-resolved playback
URL at assignment time — for example, the concrete TuneIn redirect target — not merely the CDS
reference [CONFIRMED]. When the physical button is pressed, the device plays this pre-resolved URL
directly; no CDS lookup occurs at playback time. This means that if the TuneIn URL changes (e.g.,
a new redirect target is issued by the radio service), the stored button becomes stale until the
user reassigns it.

**Zone vs. physical renderer distinction.** All playback control goes to virtual zone renderers
on the Expand hub (ports 49935, 52405, 49306), never directly to a physical speaker IP
[CONFIRMED]. The physical speaker devices (10.38.20.175, 10.38.20.35, 10.38.20.105) accept SOAP
calls for device-local configuration (EQ, standby) but the hub is the authority for transport
state [CONFIRMED]. This separation means a physical speaker can be swapped or reconfigured without
changing any playback application code.

**GENA room UUID vs. renderer UDN.** The `RoomStates` and `RoomVolumes` event properties use
"room UUIDs" (e.g., `uuid:9b109c9c-493a-40a6-9951-30561eebf5b0`) that are distinct from both
zone renderer UDNs and physical speaker UDNs [OBSERVED]. These room identifiers represent the
logical grouping of speakers within a zone. A zone with two speakers in sync has a single room
UUID; a zone with speakers in separate rooms has multiple room UUIDs. This three-level indirection
(zone renderer → room → physical speaker) is the core of the Raumfeld multiroom model [INFERRED].

**Line-in always live.** Port 8888 on One S speakers serves a continuously running FLAC stream
regardless of whether line-in audio is assigned to any zone [CONFIRMED]. The stream exists as long
as the speaker is powered; any Raumfeld renderer — or any HTTP client — can consume
`http://{speaker-ip}:8888/stream.flac` as a live source without negotiation.

**ConfigService preferences are hub-resident.** User preferences (including those that drive
button behavior, EQ presets, and zone assignments) are stored inside the Expand hub via
ConfigService, not in the mobile app [CONFIRMED]. Preferences survive app reinstalls and are
accessible from any app instance on the LAN [INFERRED]. The RSA public-key encryption scheme
(`GetPublicKey` → client encrypts payload → `SetPreferences`) allows preferences to be stored on
the hub without the hub being able to read them in plaintext [APK].
