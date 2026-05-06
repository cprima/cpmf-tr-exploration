# C4 Level 1: System Context

How `cprima-raumtube` fits into its environment.

---

```mermaid
C4Context
    title System Context — cprima-raumtube

    Person(user, "User", "Runs CLI commands to play audio on Raumfeld speakers")

    System(raumtube, "cprima-raumtube", "UPnP audio bridge: resolves media, streams audio, controls Raumfeld renderers via SOAP")

    System_Ext(youtube, "YouTube", "Video/audio platform. Direct stream URLs resolved by yt-dlp.")
    System_Ext(raumfeld, "Raumfeld Installation", "Expand hub + physical speakers on a local LAN. Controlled via UPnP/SOAP.")
    System_Ext(radio, "Internet Radio", "HTTP audio streams (SomaFM, etc.). No resolution needed.")

    Rel(user, raumtube, "Invokes", "CLI: raumtube-play, raumtube-discover, raumtube-scpd")
    Rel(raumtube, youtube, "Resolves stream URLs", "yt-dlp (HTTPS)")
    Rel(raumtube, raumfeld, "Discovers devices, controls playback", "SSDP (multicast UDP), SOAP (HTTP)")
    Rel(raumtube, radio, "Pipes live audio", "HTTP")
    Rel(raumfeld, raumtube, "Fetches audio stream", "HTTP (GET with Range)")
```

---

## Narrative

The user has one or more Raumfeld multiroom audio installations on local LANs.
`cprima-raumtube` bridges between the user's intent (play this YouTube URL on that zone)
and the Raumfeld UPnP control plane (SOAP actions on AVTransport).

For YouTube content, the system uses `yt-dlp` to resolve an ephemeral CDN URL,
downloads the audio to a local cache, and serves it over HTTP to the renderer.

For internet radio and other HTTP streams, the system pipes the live byte stream
to the renderer without caching.

The Raumfeld installation is treated as an external system: `cprima-raumtube` never
modifies device firmware or configuration — it only uses the standard UPnP/SOAP protocol.
