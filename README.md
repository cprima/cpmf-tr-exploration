# cpmf-tr-exploration

Python toolkit for controlling Teufel/Raumfeld speakers over LAN via raw UPnP/SOAP — no cloud, no vendor SDK.

Discovers devices with SSDP, parses SCPD action signatures, and sends SOAP commands directly to zone renderers on a Raumfeld Expand hub. Streams YouTube audio by resolving URLs with yt-dlp, transcoding through ffmpeg, and serving seekable MP3 over HTTP with Range support. Auto-detects live vs. cached mode.

## Modules

| File | Purpose |
|---|---|
| `devices.py` | SSDP registry, zone lookup |
| `soap.py` | Generic UPnP SOAP caller |
| `streaming.py` | HTTP audio server (live pipe + seekable cache) |
| `play_youtube.py` | Orchestration: YouTube → Raumfeld |

## Usage

```bash
uv run discover.py                                        # scan network, write devices.json
uv run play_youtube.py "https://youtube.com/watch?v=..." HomeOffice
uv run play_youtube.py "https://ice1.somafm.com/..." HomeOffice --live
```

## Requirements

- Python 3.11+
- ffmpeg in PATH
