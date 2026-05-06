# ADR-002: Live Streams Are Non-Seekable

Status: Accepted
Date: 2026-05-07

## Context

Two streaming modes are supported:

1. **Cached file** — audio downloaded to disk; served as a static file with HTTP `Range` support.
2. **Live pipe** — ffmpeg stdout piped directly into the HTTP response; no buffering to disk.

HTTP `Range` requests (e.g. `Range: bytes=1048576-`) require the server to know the total file size
and to seek to an arbitrary byte offset. An ffmpeg pipe has neither property:
- Total duration is unknown at stream start (or infinite for radio).
- The byte stream is generated sequentially; there is no random-access buffer.

Raumfeld renderers attempt seek operations by sending a new `Range` request to the stream URL.
For live pipes, this request fails or returns an error status, causing playback to stop.

## Decision

`StreamSession.seekable` is `False` for `live_pipe` mode and `True` for `cached_file` mode.
`StreamSession.range_supported` follows the same split.

The local HTTP streaming server (`cprima_raumtube.streaming`):
- Returns `Accept-Ranges: bytes` and handles `Range` headers only for `CachedStreamSession`.
- Returns `Accept-Ranges: none` for `LiveStreamSession` and ignores `Range` headers.

`MediaItem.seekable` reflects whether the *source* supports seeking (separate from stream mode).
A cached YouTube track is seekable; a SomaFM radio stream is not.

## Consequences

- Any UI layer must disable seek controls when `StreamSession.seekable` is `False`.
- `PlaybackPosition.estimated_rel_seconds()` is unreliable for live streams (position drifts without a reference).
- `Queue.crossfade` (gapless via `SetNextAVTransportURI`) is feasible for cached files but not live pipes,
  because the renderer needs to pre-fetch the next track URL before the current one ends.
- When a renderer reconnects after a dropout, a live-pipe session cannot resume mid-stream;
  playback restarts from the current live position.
