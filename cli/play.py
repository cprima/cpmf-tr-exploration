"""raumtube-play — stream a URL to a Raumfeld zone renderer."""

import argparse

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.devices import get_zone
from cprima_raumtube.model.aggregates import System
from cprima_raumtube.services import PlaybackManager, QueueManager, StreamManager, load_index
from cprima_raumtube.upnp.transport import Renderer


def main() -> None:
    ensure_utf8_stdout()

    cfg = load_config()

    ap = argparse.ArgumentParser(description="Play a URL on a Raumfeld zone.")
    ap.add_argument("url")
    ap.add_argument("zone", nargs="?", default="HomeOffice")
    ap.add_argument(
        "--live", action="store_true", help="Force pipe mode (radio, TTS, live streams)"
    )
    ap.add_argument(
        "--enqueue",
        action="store_true",
        help="Append to existing queue instead of replacing it",
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
        "--local-ip", default=cfg.local_ip, help="Local IP exposed to the Raumfeld renderer"
    )
    ap.add_argument("--port", type=int, default=cfg.port)
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    args = ap.parse_args()

    if not args.local_ip:
        ap.error("--local-ip is required (or set RAUMTUBE_LOCAL_IP)")

    zone = get_zone(args.zone, args.devices_file)
    zone_id = zone["udn"]
    renderer = Renderer.from_zone(zone)
    print(f"Zone   : {zone['friendly_name']} ({zone.get('model', '?')})")

    # Build in-memory system, load persistent cache index
    system = System()
    load_index(system.library, cfg.local_ip and cfg.cache_dir or cfg.cache_dir)

    sm = StreamManager(args.local_ip, args.port)
    qm = QueueManager(system, cfg)
    pm = PlaybackManager(system, renderer, qm, sm)

    mode = "live" if args.live else "auto"
    item = qm.enqueue(zone_id, args.url, mode=mode, replace=not args.enqueue)
    print(f"Title  : {item.title}")
    if item.duration_seconds:
        from cprima_raumtube.didl import _fmt_dur

        print(f"Duration: {_fmt_dur(item.duration_seconds)}")

    if args.repeat:
        qm.set_repeat(zone_id, args.repeat)

    pm.play_current(zone_id)

    if args.no_autoplay:
        try:
            input("\nPress Enter to stop …")
        except KeyboardInterrupt:
            pass
        pm.stop(zone_id)
    else:

        def _on_change(uri: str, reason: object) -> None:
            if reason:
                print(f"\n  [{reason}]  advancing queue …")

        pm.run_autoplay_loop(zone_id, on_state_change=_on_change)

    sm.stop_all()
