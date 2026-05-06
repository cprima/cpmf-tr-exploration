# Capability Matrix

Per-device feature support based on SCPD analysis and live testing.

**Key:** Yes = confirmed working | No = confirmed unsupported | Unknown = not yet probed | Partial = works with caveats

---

## Playback Control

| Capability | Expand (virtual renderer) | One S (physical) | Cinebar Lux (physical) | Notes |
|---|---|---|---|---|
| `SetAVTransportURI` | Yes | Yes | Yes | Core; required for all playback |
| `Play` | Yes | Yes | Yes | |
| `Stop` | Yes | Yes | Yes | |
| `Pause` | Yes | Unknown | Unknown | Physical speakers may not support Pause |
| `Seek` (ABS_TIME) | Yes (cached) | Unknown | Unknown | Requires `Range` support on HTTP server; not valid for live streams (ADR-002) |
| `SetNextAVTransportURI` | Yes | Yes | Yes | Confirmed in exploration; enables gapless (ADR-006) |
| `GetTransportInfo` | Yes | Yes | Yes | |
| `GetPositionInfo` | Yes | Yes | Yes | `TrackDuration` = `"NOT_IMPLEMENTED"` for live streams |
| `GetMediaInfo` | Yes | Yes | Yes | |

---

## Volume / Rendering

| Capability | Expand (virtual) | One S | Cinebar Lux | Notes |
|---|---|---|---|---|
| `GetVolume` | Yes | Yes | Yes | `RenderingControl` service |
| `SetVolume` | Yes | Yes | Yes | Range 0–100 |
| `GetMute` | Yes | Unknown | Unknown | |
| `SetMute` | Yes | Unknown | Unknown | |

---

## Stream Modes

| Stream Mode | Expand (virtual) | One S | Cinebar Lux | Notes |
|---|---|---|---|---|
| Cached MP3 (`cached_file`) | Yes | Yes | Yes | `Accept-Ranges: bytes`; seekable |
| Live pipe (`live_pipe`) | Yes | Yes | Yes | No Range; non-seekable (ADR-002) |
| Direct URL (`direct_url`) | Yes | Unknown | Unknown | Renderer fetches source URL directly |

---

## MIME Types (from GetProtocolInfo — Zone Renderer)

| MIME Type | Expand (zone renderer) | Notes |
|---|---|---|
| `audio/mpeg` / `audio/mp3` | Yes | Multiple aliases supported |
| `audio/mp4` / `audio/m4a` / `audio/m4b` | Yes | AAC in M4A/M4B containers |
| `audio/ogg` / `audio/vorbis` | Yes | Multiple OGG aliases |
| `audio/x-flac` / `audio/flac` | Yes | Lossless |
| `audio/alac` | Yes | Apple Lossless |
| `audio/wav` / `audio/x-wav` | Yes | Uncompressed PCM |
| `audio/x-ac3` | Yes | Dolby Digital |
| `audio/x-mpegurl` | Yes | M3U playlist / TuneIn streams |
| `application/xspf+xml` | Yes | XSPF playlist format |
| `video/mp4` | Yes | Video container (audio track) |
| `dlna-playcontainer` | Yes | DLNA multi-item playlist |

---

## Proprietary / Extended Capabilities

| Capability | Service | Notes |
|---|---|---|
| Sleep timer | AVTransport | `StartSleepTimer(SecondsUntilSleep, SecondsForVolumeRamp)` on zone renderer |
| Standby control | AVTransport | `EnterAutomaticStandby` / `EnterManualStandby` / `LeaveStandby(Room)` |
| Play mode | AVTransport | `SetPlayMode`: NORMAL, SHUFFLE, REPEAT_ONE, REPEAT_ALL, RANDOM |
| Spotify presets | AVTransport | `GetSpotifyPreset(Button)` — requires active Spotify session |
| Stream properties | AVTransport | `GetStreamProperties()` — returns ContentType + Bitrate during playback |
| Like/unlike | AVTransport | `LikeCurrentTrack` / `UnlikeCurrentTrack` (music service integration) |
| Hot-swap stream | AVTransport | `SetResourceForCurrentStream(ResourceURI)` — untested |
| 3-band EQ | RenderingControl | `GetFilter`/`SetFilter(LowDB, MidDB, HighDB)` — Cinebar Lux confirmed |
| Stereo widening | RenderingControl | `QueryFilter`/`ToggleFilter(stereo-widening)` — Cinebar Lux |
| Stereo balance | RenderingControl | `GetBalance`/`SetBalance` — Cinebar Lux |
| dB volume | RenderingControl | `GetVolumeDB`/`SetVolumeDB(Channel)` — Cinebar Lux |
| Line-in URL | RenderingControl | `GetLineInStreamURL()` — returns `http://{ip}:8888/stream.flac` |
| Generic device settings | RenderingControl | `GetDeviceSetting`/`SetDeviceSetting(Name, Value)` — Cinebar |
| Station buttons (presets) | ContentDirectory | `AssignStationButton(Renderer, Button, ObjectID)` — see exploration doc |
| Queue management | ContentDirectory | `CreateQueue`, `AddItemToQueue`, `MoveInQueue`, `RemoveFromQueue` |
| Firmware version | SetupService | `GetInfo()` → `SoftwareVersion=2.17.4` |
| Network info | SetupService | `GetNetworkInfo()` → IP, WiFi access point, signal strength |
| Device mode | SetupService | `GetDeviceMode()` → MASTER / CLIENT / WAIT_FOR_SETUP |
| OTA update | SetupService | `CheckForUpdate` / `DoUpdate(Version)` |
| Config preferences | ConfigService | `GetPreferences(PublicKey)` / `SetPreferences` — RSA-encrypted store |
| Per-room volume | RenderingControl (zone) | `GetRoomVolume`/`SetRoomVolume(Room)` — zone-level room control |

---

## Group / Multiroom

| Capability | Notes |
|---|---|
| Group playback | Expand hub coordinates; send SOAP to coordinator zone only (ADR-005) |
| Synchronized clock | Managed internally by hub; not exposed via SOAP |
| `SetNextAVTransportURI` in group | Confirmed on virtual group renderers |

---

## Notes

- "Expand (virtual renderer)" refers to the zone renderers synthesized by the Raumfeld Expand hub (see ADR-001).
- Physical speakers (One S, Cinebar Lux) are controlled exclusively through the hub's virtual renderers in normal operation.
  Direct SOAP to a physical speaker UDN is not tested.
- Update this table after running `raumtube-scpd` on new hardware and inspecting capability output.
- Cross-reference with ADR-006 (capability probing) before adding new capabilities.

---

## Capability Fields in Model

`RendererCapabilities` (`model/topology.py`):

| Field | Corresponds to |
|---|---|
| `seek` | Seek (ABS_TIME) row above |
| `pause` | Pause row above |
| `next_previous` | GetMediaInfo NextURI support |
| `set_next_uri` | SetNextAVTransportURI row above |
| `volume_control` | GetVolume / SetVolume rows above |
