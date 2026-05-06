# ADR-003: YouTube Resolved URLs Are Ephemeral

Status: Accepted
Date: 2026-05-07

## Context

YouTube does not serve audio directly from its public URLs (e.g. `https://youtube.com/watch?v=mAKxcNQpiSg`).
`yt-dlp` resolves a video/audio page into a direct CDN stream URL. These CDN URLs:

- Are signed with a time-limited token.
- Typically expire within **a few hours** of resolution.
- Cannot be refreshed by re-using the same signed URL — a new extraction is required.

A naive model that stores the resolved URL on the `MediaItem` itself will silently serve stale URLs
after the token expires, causing `SetAVTransportURI` to succeed but playback to fail at the renderer side.

## Decision

Three separate identity fields are maintained on `MediaItem`:

| Field | Stability | Example |
|---|---|---|
| `canonical_id` | Permanent | `"youtube:mAKxcNQpiSg"` |
| `source_locator` | Permanent | `"https://youtube.com/watch?v=mAKxcNQpiSg"` |
| `resolved_uri` | Ephemeral cache hint — may be `None` or stale | CDN signed URL |

A separate `MediaResolution` record is created each time `yt-dlp` resolves a video.
It carries `expires_at` and must be validated with `is_valid(now)` before use.

`LibraryAggregate.get_fresh_resolution(media_item_id)` is the single authoritative lookup path.
Callers must **never** use `MediaItem.resolved_uri` directly for playback.

## Consequences

- Resolution is a separate, re-triggerable operation distinct from item discovery.
- `LibraryAggregate` accumulates multiple `MediaResolution` objects per item over time;
  expired ones should be pruned periodically.
- The CLI `raumtube-play` must always call `get_fresh_resolution()` before building the stream URL,
  even for items already in the library.
- Caching (`cached_file` stream mode) partially mitigates expiry: once the file is on disk,
  the CDN URL is no longer needed. `CacheEntry` records track this state.
