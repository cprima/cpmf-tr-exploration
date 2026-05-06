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

## MIME Types (observed via GetProtocolInfo)

| MIME Type | Expand | One S | Cinebar Lux |
|---|---|---|---|
| `audio/mpeg` (MP3) | Yes | Yes | Yes |
| `audio/mp4` (AAC/M4A) | Unknown | Unknown | Unknown |
| `audio/ogg` | Unknown | Unknown | Unknown |
| `audio/x-flac` | Unknown | Unknown | Unknown |

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
