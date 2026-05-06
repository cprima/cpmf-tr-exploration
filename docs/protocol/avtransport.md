# Protocol: AVTransport Service

Service URN: `urn:schemas-upnp-org:service:AVTransport:1`
Control URL (example): `http://10.38.20.100:49935/TransportService/Control`

All actions are invoked via `soap.soap_call(control_url, AVT_SVC, action_name, args)`.

---

## Actions

### `SetAVTransportURI`

Set the media URI to be played. Does not start playback.

**Inputs**

| Argument | Type | Notes |
|---|---|---|
| `InstanceID` | `ui4` | Always `"0"` on Raumfeld |
| `CurrentURI` | `string` | The stream URL (HTTP, local HTTP server, or direct CDN) |
| `CurrentURIMetaData` | `string` | DIDL-Lite XML, XML-escaped. Use `didl.build_didl()`. Pass `""` to clear. |

**Outputs:** none (empty response body)

**State transition:** `NO_MEDIA_PRESENT` → `STOPPED` or `STOPPED` → `STOPPED` (replace)

**Timing:** Responds within ~500 ms. Renderer may not connect to the stream URL until `Play` is called.

**Notes:**
- `CurrentURIMetaData` must be raw XML — do **not** double-escape. The SOAP envelope handles outer escaping.
- Passing `""` for metadata is accepted; title will appear as the raw URL on device displays.

---

### `Play`

Start playback of the current URI.

**Inputs**

| Argument | Type | Notes |
|---|---|---|
| `InstanceID` | `ui4` | Always `"0"` |
| `Speed` | `string` | Always `"1"` (normal speed) |

**Outputs:** none

**State transition:** `STOPPED` → `TRANSITIONING` → `PLAYING`

**Timing:** `TRANSITIONING` lasts 1–5 s for cached files, 2–10 s for live streams.
Poll `GetTransportInfo` until state is `PLAYING`.

---

### `Stop`

Stop playback and release the stream connection.

**Inputs**

| Argument | Type | Notes |
|---|---|---|
| `InstanceID` | `ui4` | Always `"0"` |

**Outputs:** none

**State transition:** `PLAYING` / `PAUSED_PLAYBACK` → `STOPPED`

---

### `Pause`

Pause playback at the current position.

**Inputs**

| Argument | Type | Notes |
|---|---|---|
| `InstanceID` | `ui4` | Always `"0"` |

**Outputs:** none

**State transition:** `PLAYING` → `PAUSED_PLAYBACK`

**Notes:** Only available if `RendererCapabilities.pause` is `True`. See ADR-006.
Not supported for live streams (`live_pipe` mode). See ADR-002.

---

### `Seek`

Seek to an absolute time position within the current track.

**Inputs**

| Argument | Type | Notes |
|---|---|---|
| `InstanceID` | `ui4` | Always `"0"` |
| `Unit` | `string` | `"ABS_TIME"` (format: `HH:MM:SS`) |
| `Target` | `string` | Position, e.g. `"0:02:30"` |

**Outputs:** none

**State transition:** `PLAYING` → `TRANSITIONING` → `PLAYING`

**Notes:**
- Only available if `RendererCapabilities.seek` is `True`.
- The renderer issues a new `Range` request to the HTTP server. The server must support Range responses.
- Live streams cannot be seeked (see ADR-002).

---

### `GetTransportInfo`

Poll the current transport state.

**Inputs**

| Argument | Type |
|---|---|
| `InstanceID` | `ui4` |

**Outputs**

| Argument | Values |
|---|---|
| `CurrentTransportState` | `STOPPED`, `PLAYING`, `PAUSED_PLAYBACK`, `TRANSITIONING`, `NO_MEDIA_PRESENT` |
| `CurrentTransportStatus` | `OK`, `ERROR_OCCURRED` |
| `CurrentSpeed` | `"1"` |

---

### `GetPositionInfo`

Get the current playback position.

**Inputs**

| Argument | Type |
|---|---|
| `InstanceID` | `ui4` |

**Outputs**

| Argument | Example | Notes |
|---|---|---|
| `RelTime` | `"0:01:23"` | Position within current track (HH:MM:SS) |
| `TrackDuration` | `"0:04:12"` | Total duration or `"NOT_IMPLEMENTED"` for live streams |
| `AbsTime` | `"0:01:23"` | Same as RelTime for single-track queues |

---

### `GetMediaInfo`

Inspect the currently loaded URI.

**Inputs**

| Argument | Type |
|---|---|
| `InstanceID` | `ui4` |

**Outputs**

| Argument | Notes |
|---|---|
| `CurrentURI` | The URI set by `SetAVTransportURI` |
| `CurrentURIMetaData` | The DIDL metadata |
| `NextURI` | Pre-loaded next URI (if `SetNextAVTransportURI` was called) |
| `NrTracks` | `"1"` for single items |
| `MediaDuration` | `"NOT_IMPLEMENTED"` for live streams |

---

### `SetNextAVTransportURI`

Pre-load the next track URI for gapless playback.

**Inputs**

| Argument | Type | Notes |
|---|---|---|
| `InstanceID` | `ui4` | Always `"0"` |
| `NextURI` | `string` | The next stream URL |
| `NextURIMetaData` | `string` | DIDL-Lite XML, XML-escaped |

**Outputs:** none

**Notes:**
- Only available if `RendererCapabilities.set_next_uri` is `True`.
- The renderer transitions to `NextURI` automatically when the current track ends.
- This is the mechanism behind `Queue.crossfade`. See ADR-006.
- Confirmed working on Raumfeld Expand virtual renderers and physical One S / Cinebar Lux.

---

## Error Handling

SOAP faults are raised as `RuntimeError` by `soap.soap_call()`. The error string includes:
- `faultstring` — human-readable description
- `errorCode` — UPnP error code (e.g. `701` = Transition not available)
- `errorDescription` — device-specific message

Common error codes:

| Code | Meaning |
|---|---|
| `701` | Transition not available (e.g. Pause on unsupported renderer) |
| `714` | Illegal seek target |
| `716` | Argument value out of range |
| `800` | Device internal error |
