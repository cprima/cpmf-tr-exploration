# C4 Level 2: Containers

The major deployable / importable units within `cprima-raumtube`.

---

```mermaid
C4Container
    title Containers — cprima-raumtube

    Person(user, "User")

    System_Boundary(pkg, "cprima-raumtube package") {
        Container(cli, "CLI entrypoints", "Python (cli/)", "Argument parsing, config loading, output formatting. No business logic.")
        Container(core, "Core library", "Python (src/cprima_raumtube/)", "Discovery, SOAP, streaming, domain model, sources.")
        Container(httpserver, "Local HTTP server", "Python (cprima_raumtube.streaming)", "Serves cached MP3 files and live ffmpeg pipes to the renderer.")
    }

    System_Ext(youtube, "YouTube / yt-dlp", "Resolves and downloads audio")
    System_Ext(raumfeld, "Raumfeld Expand Hub", "UPnP SOAP control plane")
    System_Ext(speakers, "Physical speakers", "Audio output")

    Rel(user, cli, "Runs", "shell")
    Rel(cli, core, "Calls", "Python import")
    Rel(core, httpserver, "Manages sessions", "Python import")
    Rel(core, youtube, "Extracts stream URL, downloads audio", "yt-dlp / HTTPS")
    Rel(core, raumfeld, "SSDP discovery, SOAP SetAVTransportURI / Play", "UDP multicast + HTTP")
    Rel(raumfeld, httpserver, "Fetches audio stream", "HTTP GET (with Range)")
    Rel(raumfeld, speakers, "Routes audio", "Proprietary RF / Ethernet")
```

---

## Container Descriptions

### `cli/` — CLI Entrypoints

Three thin scripts, one per command. Each:
1. Calls `_compat.ensure_utf8_stdout()`.
2. Parses args with `argparse`.
3. Calls `load_config()`, applies CLI overrides.
4. Delegates entirely to `cprima_raumtube.*`.

Contains zero business logic.

### `src/cprima_raumtube/` — Core Library

The installable package. Sub-packages:

| Sub-package | Purpose |
|---|---|
| `discovery/` | SSDP M-SEARCH, device registry |
| `upnp/` | `Renderer` class — ergonomic SOAP wrapper |
| `scpd/` | SCPD fetch, parse, capability extraction |
| `sources/` | `AudioSource` protocol, `YouTubeSource` |
| `model/` | Domain model (topology, media, playback, events, registry) |

Top-level modules: `soap.py`, `devices.py`, `didl.py`, `streaming.py`, `config.py`.

### `cprima_raumtube.streaming` — Local HTTP Server

Runs in-process on a configurable port (default 8080).
Two session types:
- `CachedStreamSession` — serves a static file with `Accept-Ranges: bytes`.
- `LiveStreamSession` — pipes ffmpeg stdout; no Range support.

Each session has a UUID URL path (see ADR-004).
