# Sequence: Radio / Live Stream Playback (Live Pipe Mode)

This diagram covers playback of an internet radio stream or other live HTTP audio source,
using `live_pipe` stream mode (ffmpeg piped to the HTTP server; no caching).

---

## Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant CLI as cli/play.py
    participant HTTP as StreamManager / HTTP server
    participant ffmpeg as ffmpeg subprocess
    participant Radio as Internet Radio (e.g. SomaFM)
    participant Renderer as upnp/transport.py (Renderer)
    participant Raumfeld as Raumfeld ZoneRenderer

    User->>CLI: raumtube-play "https://ice1.somafm.com/groovesalad-128-mp3" HomeOffice

    Note over CLI: No yt-dlp probe needed — direct HTTP URL

    CLI->>HTTP: start_stream(live_pipe, source_url)
    HTTP->>ffmpeg: spawn ffmpeg -i source_url -f mp3 pipe:1
    ffmpeg->>Radio: HTTP GET (audio stream)
    Radio-->>ffmpeg: audio bytes (continuous)
    ffmpeg-->>HTTP: stdout pipe (MP3 chunks)
    HTTP-->>CLI: StreamSession(public_url="/session/{uuid}/stream.mp3", seekable=False)

    CLI->>Renderer: set_uri(public_url, didl_metadata)
    Renderer->>Raumfeld: SOAP SetAVTransportURI(CurrentURI=public_url,\nCurrentURIMetaData=didl_broadcast)
    Raumfeld-->>Renderer: 200 OK

    CLI->>Renderer: play()
    Renderer->>Raumfeld: SOAP Play(Speed="1")
    Raumfeld-->>Renderer: 200 OK

    Note over Raumfeld,HTTP: State: STOPPED → TRANSITIONING

    Raumfeld->>HTTP: GET /session/{uuid}/stream.mp3
    HTTP-->>Raumfeld: 200 OK (no Content-Length, Accept-Ranges: none)
    Note over HTTP,Raumfeld: Continuous byte stream (no Range support)

    Note over Raumfeld: State: TRANSITIONING → PLAYING

    loop continuous audio
        ffmpeg-->>HTTP: MP3 chunks
        HTTP-->>Raumfeld: forwarded chunks
    end

    Note over Raumfeld: Audio output on physical speaker
```

---

## Key Differences vs. Cached File Mode

| Aspect | Live Pipe | Cached File |
|---|---|---|
| `StreamSession.mode` | `live_pipe` | `cached_file` |
| `StreamSession.seekable` | `False` | `True` |
| `Accept-Ranges` header | `none` | `bytes` |
| `Content-Length` header | absent | present |
| HTTP status code | `200` | `200` or `206` (with Range) |
| Renderer can seek | No | Yes |
| Dropout recovery | Restart from live position | Re-issue Range request |
| DIDL class | `audioBroadcast` | `audioItem` |

---

## DIDL Metadata for Live Streams

```python
build_didl(uri, title, live=True)
# → upnp:class = object.item.audioItem.audioBroadcast
```

Using `audioBroadcast` signals to the renderer that the stream is infinite and non-seekable.
Some renderers suppress seek controls on the display when this class is set.

---

## Notes

- ffmpeg must be installed and on `PATH`.
- If ffmpeg or the radio source fails, `StreamSession.state` transitions to `failed`.
- The renderer may reconnect after a dropout using the same UUID URL — it receives the live stream from the current position (no rewind).
- `GetPositionInfo` returns `TrackDuration = "NOT_IMPLEMENTED"` for live streams.
- `Pause` is unreliable for live streams — see ADR-002.
