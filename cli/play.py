"""raumtube-play — play a URL or the persisted queue on a Raumfeld zone."""

import argparse

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.devices import get_zone
from cprima_raumtube.discovery.ssdp import detect_source_ip
from cprima_raumtube.model.registry import Installation
from cprima_raumtube.services import (
    PlaybackManager,
    QueueManager,
    StreamManager,
    load_index,
    load_queue,
    save_queue,
)
from cprima_raumtube.upnp.transport import Renderer


def main() -> None:
    ensure_utf8_stdout()

    cfg = load_config()

    ap = argparse.ArgumentParser(
        description="Play a URL (or the persisted queue) on a Raumfeld zone."
    )
    ap.add_argument("url", nargs="?", default=None, help="URL to play (omit to play from queue)")
    ap.add_argument("zone", nargs="?", default="HomeOffice")
    ap.add_argument(
        "--live", action="store_true", help="Force pipe mode (radio, TTS, live streams)"
    )
    ap.add_argument(
        "--enqueue",
        action="store_true",
        help="Append URL to existing queue instead of replacing it",
    )
    ap.add_argument(
        "--repeat",
        choices=["off", "one", "all"],
        default=None,
        help="Set repeat mode (default: off)",
    )
    ap.add_argument(
        "--no-autoplay",
        action="store_true",
        help="Play one item and exit without advancing the queue",
    )
    ap.add_argument(
        "--local-ip",
        default=cfg.local_ip or None,
        help="Local IP exposed to the Raumfeld renderer (auto-detected when omitted)",
    )
    ap.add_argument("--port", type=int, default=cfg.port)
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    args = ap.parse_args()

    if not args.local_ip:
        args.local_ip = detect_source_ip() or ""

    zone = get_zone(args.zone, args.devices_file)
    zone_id = zone["udn"]
    renderer = Renderer.from_zone(zone)
    print(f"Zone   : {zone['friendly_name']} ({zone.get('model', '?')})")

    installation = Installation.ephemeral()
    load_index(installation.library, cfg.cache_dir)
    load_queue(installation.state, zone_id, cfg.cache_dir)

    sm = StreamManager(args.local_ip, args.port)
    qm = QueueManager(installation, cfg)
    pm = PlaybackManager(installation, renderer, qm, sm)

    if args.url:
        mode = "live" if args.live else "auto"
        item = qm.enqueue(zone_id, args.url, mode=mode, replace=not args.enqueue)
        print(f"Title  : {item.title}")
        if item.duration_seconds:
            from cprima_raumtube.didl import _fmt_dur
            print(f"Duration: {_fmt_dur(item.duration_seconds)}")
        queue = installation.state.get_or_create_queue(zone_id)
        save_queue(queue, cfg.cache_dir)
    else:
        queue = installation.state.get_or_create_queue(zone_id)
        if not queue.items:
            ap.error("Queue is empty — provide a URL or use 'raumtube-enqueue' first")
        print(f"Queue  : {len(queue.items)} item(s)")
        # Reset to start of queue
        queue.current_index = 0

    if args.repeat:
        qm.set_repeat(zone_id, args.repeat)

    pm.play_current(zone_id)

    if args.no_autoplay:
        import contextlib
        with contextlib.suppress(KeyboardInterrupt):
            input("\nPress Enter to stop …")
        pm.stop(zone_id)
    else:
        def _on_change(_uri: str, reason: object) -> None:
            if reason:
                print(f"\n  [{reason}]  advancing queue …")

        pm.run_autoplay_loop(zone_id, on_state_change=_on_change)

    sm.stop_all()
