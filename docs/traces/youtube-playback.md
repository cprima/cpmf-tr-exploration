# Sequence: YouTube Playback (Cached File Mode)

This diagram covers the full flow from CLI invocation to audio output on a Raumfeld renderer,
using `cached_file` stream mode (downloaded to disk, served with HTTP Range support).

---

## Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant CLI as cli/play.py
    participant YT as sources/youtube.py
    participant ytdlp as yt-dlp
    participant Lib as LibraryAggregate
    participant HTTP as StreamManager / HTTP server
    participant Renderer as upnp/transport.py (Renderer)
    participant Raumfeld as Raumfeld ZoneRenderer

    User->>CLI: raumtube-play "https://youtube.com/watch?v=..." HomeOffice

    CLI->>Lib: find_by_canonical("youtube:VIDEO_ID")
    alt item not in library
        CLI->>YT: probe(url, cache_dir)
        YT->>ytdlp: extract_info(url, download=False)
        ytdlp-->>YT: info dict (title, duration, formats)
        YT-->>CLI: MediaItem + MediaResolution (expires_at ~6h)
        CLI->>Lib: add MediaItem, add MediaResolution
    end

    CLI->>Lib: get_fresh_resolution(media_item_id)
    alt resolution expired or missing
        CLI->>YT: probe(url, cache_dir)  [re-resolve]
        YT->>ytdlp: extract_info(url)
        ytdlp-->>YT: fresh info dict
        YT-->>CLI: new MediaResolution
        CLI->>Lib: add MediaResolution
    end

    CLI->>YT: download_to_cache(resolved_uri, cache_dir)
    YT->>ytdlp: download audio → cache_dir/VIDEO_ID.mp3
    ytdlp-->>YT: local path
    YT-->>CLI: CacheEntry (path, size_bytes)
    CLI->>Lib: add CacheEntry

    CLI->>HTTP: start_stream(cached_file, cache_entry.path)
    HTTP-->>CLI: StreamSession (public_url="/session/{uuid}/stream.mp3", seekable=True)

    CLI->>Renderer: set_uri(public_url, didl_metadata)
    Renderer->>Raumfeld: SOAP SetAVTransportURI(CurrentURI=public_url, CurrentURIMetaData=didl)
    Raumfeld-->>Renderer: 200 OK

    CLI->>Renderer: play()
    Renderer->>Raumfeld: SOAP Play(Speed="1")
    Raumfeld-->>Renderer: 200 OK

    Note over Raumfeld,HTTP: State: STOPPED → TRANSITIONING

    Raumfeld->>HTTP: GET /session/{uuid}/stream.mp3
    HTTP-->>Raumfeld: 200 OK (Content-Length, Accept-Ranges: bytes)

    Note over Raumfeld,HTTP: State: TRANSITIONING → PLAYING

    loop seek / buffer refill
        Raumfeld->>HTTP: GET /session/{uuid}/stream.mp3 Range: bytes=N-M
        HTTP-->>Raumfeld: 206 Partial Content
    end

    Note over Raumfeld: Audio output on physical speaker
```

---

## Key Points

- `yt-dlp` is called at most twice per play: once for metadata (probe), once for download.
- `MediaResolution` expiry is checked before download; re-resolve if expired (see ADR-003).
- The HTTP server serves the cached file with `Accept-Ranges: bytes`; the renderer uses Range requests for seeking and buffering.
- The UUID path in the stream URL prevents stale renderer reconnects from hitting a new session (see ADR-004).
- `didl_metadata` is built by `didl.build_didl(uri, title, live=False, duration=N)`.
- Transport state transitions (`STOPPED → TRANSITIONING → PLAYING`) are observable via `GetTransportInfo`.
