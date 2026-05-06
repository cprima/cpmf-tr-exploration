"""raumtube-play — stream a URL to a Raumfeld zone renderer."""

import argparse
import re
import time

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.devices import CM_SVC, get_zone
from cprima_raumtube.didl import _fmt_dur, build_didl
from cprima_raumtube.soap import soap_call
from cprima_raumtube.streaming import CachedStreamSession, LiveStreamSession
from cprima_raumtube.upnp.transport import Renderer

STOP_STATES = {"STOPPED", "NO_MEDIA_PRESENT"}


def _print_protocol_info(zone: dict) -> None:
    cm = zone.get("cm_control")
    if not cm:
        return
    try:
        result = soap_call(cm, CM_SVC, "GetProtocolInfo", {})
        sink = result.get("Sink", "")
        formats = sorted(
            {
                e.split(":")[2]
                for e in sink.split(",")
                if e.strip().startswith("http-get") and len(e.split(":")) >= 3
            }
        )
        print(f"Accepts: {', '.join(formats) or '(none parsed)'}")
    except RuntimeError:
        pass


def _play_and_poll(renderer: Renderer, stream_url: str, metadata: str) -> None:
    print(f"\n→ SetAVTransportURI  {stream_url}")
    renderer.set_uri(stream_url, metadata)
    print("→ Play")
    renderer.play()

    print("\nState (Ctrl+C to stop):")
    try:
        while True:
            time.sleep(2)
            state = renderer.get_state()
            try:
                pos = renderer.get_position().get("RelTime", "")
            except RuntimeError:
                pos = ""
            print(f"  {state:20s} {pos}")
            if state in STOP_STATES:
                print("Renderer stopped.")
                break
    except KeyboardInterrupt:
        print("\nInterrupted — stopping Raumfeld ...")
        try:
            renderer.stop()
        except RuntimeError:
            pass


def main() -> None:
    ensure_utf8_stdout()

    cfg = load_config()

    ap = argparse.ArgumentParser(description="Play a URL on a Raumfeld zone.")
    ap.add_argument("url")
    ap.add_argument("zone", nargs="?", default="HomeOffice")
    ap.add_argument(
        "--live", action="store_true", help="Force pipe mode (radio, TTS, generated streams)"
    )
    ap.add_argument(
        "--local-ip", default=cfg.local_ip, help="Local IP exposed to the Raumfeld renderer"
    )
    ap.add_argument("--port", type=int, default=cfg.port)
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    args = ap.parse_args()

    if not args.local_ip:
        ap.error("--local-ip is required (or set RAUMTUBE_LOCAL_IP)")

    zone = get_zone(args.zone, args.devices_file)
    renderer = Renderer.from_zone(zone)
    print(f"Zone   : {zone['friendly_name']} ({zone['model']})")

    # Try to load from cache before probing
    from cprima_raumtube.sources import youtube as yt

    yt_id_match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", args.url)
    yt_id = yt_id_match.group(1) if yt_id_match else None

    sidecar = yt.load_sidecar(cfg.cache_dir, yt_id) if yt_id else None
    mp3_path = (cfg.cache_dir / f"{yt_id}.mp3") if yt_id else None
    has_cache = bool(sidecar and mp3_path and mp3_path.exists())

    if has_cache and not args.live:
        print(f"\nCache hit for {yt_id} — skipping probe")
        title = sidecar["title"]
        thumbnail = sidecar.get("thumbnail", "")
        duration = int(sidecar.get("duration") or 0)
        live = False
        info = sidecar
    else:
        print(f"\nProbing: {args.url}")
        info = yt.probe(args.url)
        title = info.get("title", "Unknown")
        thumbnail = info.get("thumbnail", "")
        duration = int(info.get("duration") or 0)
        live = args.live or yt.is_live_stream(info)

    print(f"Title  : {title}")
    if duration:
        print(f"Duration: {_fmt_dur(duration)}")
    live_status = info.get("live_status", "")
    print(
        f"Mode   : {'LIVE (forced)' if args.live else 'LIVE' if live else 'CACHE'}"
        + (f"  [{live_status}]" if live_status else "")
    )

    _print_protocol_info(zone)

    if live:
        audio_url = info.get("url") or info["formats"][-1]["url"]
        with LiveStreamSession(audio_url, args.local_ip, args.port) as session:
            meta = build_didl(session.stream_url, title, live=True)
            _play_and_poll(renderer, session.stream_url, meta)
    else:
        if has_cache and mp3_path:
            path = mp3_path
        else:
            print(f"\nDownloading to cache ({_fmt_dur(duration)}) ...")
            path = yt.download_to_cache(args.url, info, cfg.cache_dir)
        print(f"File   : {path}  ({path.stat().st_size / 1024 / 1024:.1f} MB)")
        with CachedStreamSession(path, args.local_ip, args.port) as session:
            meta = build_didl(
                session.stream_url, title, live=False, thumbnail=thumbnail, duration=duration
            )
            _play_and_poll(renderer, session.stream_url, meta)
