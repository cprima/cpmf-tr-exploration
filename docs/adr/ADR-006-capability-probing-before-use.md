# ADR-006: Renderer Capabilities Must Be Probed Before Use

Status: Accepted
Date: 2026-05-07

## Context

UPnP does not mandate which optional actions a renderer implements. Across the Raumfeld device family:
- Some renderers support `Seek`; others return a UPnP error code.
- `SetNextAVTransportURI` (gapless pre-load) is present on physical speakers and virtual renderers,
  but its absence cannot be assumed without checking the SCPD.
- `Pause` may not be supported on broadcast/live renderers.
- Volume control (`RenderingControl` service) may be absent on some virtual zone renderers.

Calling an unsupported action causes a SOAP fault. Without probing, the caller cannot distinguish
"action failed transiently" from "action is not supported by this device."

## Decision

`RendererCapabilities` defaults all boolean fields to `False`:

```python
seek: bool = False
pause: bool = False
next_previous: bool = False
set_next_uri: bool = False
volume_control: bool = False
```

`ZoneRenderer.capabilities` is `None` until probed. `ZoneRenderer.probed` (property) returns `True`
only when `capabilities is not None`.

Capabilities are populated by:
1. Parsing the SCPD for `AVTransport` and `RenderingControl` services (`scpd/fetch.py`).
2. Calling `GetProtocolInfo` on the `ConnectionManager` service for MIME type support.

Callers **must** check `renderer.probed` and the relevant capability flag before attempting:
- Seek → `capabilities.seek`
- Pause/resume → `capabilities.pause`
- Gapless pre-load → `capabilities.set_next_uri`
- Volume → `capabilities.volume_control`

`RendererCapabilities.unknown()` is the factory for the unprobed state.

## Consequences

- First-time use of a renderer requires a SCPD fetch round-trip before playback can begin.
- `scpd/fetch.py` populates `RendererCapabilities` and stores raw `ProtocolSnapshot` for debugging.
- The capability matrix (`docs/findings/capability-matrix.md`) is the living record of what was
  observed on real devices; update it after probing new hardware.
- Feature flags like `Queue.crossfade` are only respected at execution time if `set_next_uri` is `True`.
