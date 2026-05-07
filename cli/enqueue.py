"""raumtube-enqueue — add a URL to a zone's persistent queue."""

import argparse

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.devices import get_zone
from cprima_raumtube.model.registry import Installation
from cprima_raumtube.services import QueueManager, load_index, load_queue, save_index, save_queue


def _print_queue(installation: Installation, zone_id: str) -> None:
    queue = installation.state.get_or_create_queue(zone_id)
    if not queue.items:
        print("  (queue empty)")
        return
    for i, qi in enumerate(queue.items):
        item = installation.library.find_item(qi.media_item_id)
        title = item.title if item else qi.media_item_id
        marker = "▶" if i == queue.current_index else " "
        print(f"  {marker} [{i}] {title}")


def main() -> None:
    ensure_utf8_stdout()
    cfg = load_config()

    ap = argparse.ArgumentParser(description="Append a URL to a Raumfeld zone queue.")
    ap.add_argument("url", help="YouTube or stream URL to enqueue")
    ap.add_argument("zone", nargs="?", default="HomeOffice")
    ap.add_argument("--live", action="store_true", help="Force pipe mode")
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    args = ap.parse_args()

    zone = get_zone(args.zone, args.devices_file)
    zone_id = zone["udn"]
    print(f"Zone   : {zone['friendly_name']}")

    installation = Installation.ephemeral()
    load_index(installation.library, cfg.cache_dir)
    load_queue(installation.state, zone_id, cfg.cache_dir)

    qm = QueueManager(installation, cfg)
    mode = "live" if args.live else "auto"
    item = qm.enqueue(zone_id, args.url, mode=mode, replace=False)
    print(f"Queued : {item.title}")

    save_index(installation.library, cfg.cache_dir)
    queue = installation.state.get_or_create_queue(zone_id)
    save_queue(queue, cfg.cache_dir)

    print(f"\nQueue ({zone['friendly_name']}):")
    _print_queue(installation, zone_id)


if __name__ == "__main__":
    main()
