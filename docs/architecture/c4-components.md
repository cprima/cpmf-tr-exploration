# C4 Level 3: Components

Components within the `src/cprima_raumtube/` core library.

---

```mermaid
C4Component
    title Components — cprima_raumtube core library

    Container_Boundary(core, "cprima_raumtube") {
        Component(ssdp, "discovery/ssdp.py", "Python", "SSDP M-SEARCH, GUPnP filter, device XML fetch, build_registry()")
        Component(transport, "upnp/transport.py", "Python", "Renderer class — ergonomic SOAP wrapper for AVTransport + RenderingControl")
        Component(soap, "soap.py", "Python", "Generic soap_call() — low-level XML envelope builder and response parser")
        Component(scpd, "scpd/fetch.py", "Python", "Fetch SCPD XML, parse actions/state variables, populate RendererCapabilities")
        Component(youtube, "sources/youtube.py", "Python", "probe(), download_to_cache(), sidecar helpers — wraps yt-dlp")
        Component(streaming, "streaming.py", "Python", "LiveStreamSession, CachedStreamSession — HTTP server session management")
        Component(didl, "didl.py", "Python", "build_didl() — constructs DIDL-Lite XML metadata for SetAVTransportURI")
        Component(config, "config.py", "Python", "Config dataclass, load_config() — three-tier resolution: flag > env > file > default")
        Component(model, "model/", "Python", "Domain model: topology, media, playback, events, aggregates, registry")
    }

    System_Ext(raumfeld, "Raumfeld Expand Hub", "UPnP/SOAP")
    System_Ext(ytdlp, "yt-dlp", "YouTube extraction")

    Rel(ssdp, raumfeld, "M-SEARCH + device XML fetch", "UDP / HTTP")
    Rel(ssdp, model, "Populates TopologyAggregate")
    Rel(transport, soap, "Delegates SOAP calls")
    Rel(soap, raumfeld, "SOAP HTTP POST")
    Rel(scpd, raumfeld, "Fetches SCPD XML", "HTTP")
    Rel(scpd, model, "Populates RendererCapabilities, ProtocolSnapshot")
    Rel(youtube, ytdlp, "extract_info(), download", "subprocess")
    Rel(youtube, model, "Creates MediaItem, MediaResolution, CacheEntry")
    Rel(streaming, model, "Creates StreamSession")
    Rel(transport, didl, "Uses build_didl() for metadata")
    Rel(transport, model, "Reads ZoneRenderer, updates PlaybackSession")
```

---

## Component Responsibilities

| Component | Owns | Does not own |
|---|---|---|
| `discovery/ssdp.py` | Device discovery, registry building | Capability probing (→ `scpd/fetch.py`) |
| `upnp/transport.py` | Renderer API (set_uri, play, stop, seek, volume) | SOAP envelope construction (→ `soap.py`) |
| `soap.py` | HTTP POST, XML envelope, fault parsing | Domain knowledge |
| `scpd/fetch.py` | SCPD download, parse, capability mapping | Storing capabilities (→ model) |
| `sources/youtube.py` | yt-dlp integration, sidecar JSON | Streaming (→ `streaming.py`) |
| `streaming.py` | HTTP session lifecycle, Range responses | SOAP control (→ `upnp/transport.py`) |
| `didl.py` | DIDL-Lite XML construction | UPnP protocol details |
| `config.py` | Config loading and merging | Application state |
| `model/` | Domain entities, aggregates, events | I/O, networking |
