# ADR-004: Each Stream Session Gets a Unique UUID Path

Status: Accepted
Date: 2026-05-07

## Context

Raumfeld renderers aggressively cache stream URLs. When a renderer's connection to the HTTP server
drops (network hiccup, renderer restart, zone group change), it may:

1. Re-use the **same URL** it last received via `SetAVTransportURI`.
2. Reconnect and issue a new `GET` to that cached URL.

If two consecutive `raumtube-play` invocations reuse the same URL path (e.g. `/stream.mp3`),
a stale reconnect from the *previous* session hits the *new* session's HTTP handler.
The renderer ends up playing the new track from byte 0 with the wrong content-type,
or receives a 404 if the new session hasn't started yet.

## Decision

Every `StreamSession` (both `LiveStreamSession` and `CachedStreamSession`) is assigned a UUID at creation.
The HTTP path is `/session/{uuid}/stream.mp3`.

This means:
- Each play invocation produces a URL the renderer has never seen before.
- A stale reconnect using the old UUID gets a 404, which the renderer interprets as end-of-media.
  Playback stops cleanly rather than playing the wrong content.
- The URL in `StreamSession.public_url` is the full absolute URL passed to `SetAVTransportURI`.

## Consequences

- URLs are truly one-use; there is no persistent `/stream` endpoint to bookmark or log.
- Session cleanup (closing the HTTP handler after the renderer disconnects) is safe to do by UUID.
- The HTTP server must route `/session/<uuid>/stream.mp3` to the active `StreamSession` for that UUID.
- Old session entries in `PlaybackAggregate.stream_sessions` with `state="closed"` can be pruned freely.
