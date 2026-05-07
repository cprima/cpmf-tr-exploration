"""raumtube-dequeue — remove an item from a zone's persistent queue."""

import argparse

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.devices import get_zone
from cprima_raumtube.model.registry import Installation
from cprima_raumtube.services import clear_queue, load_index, load_queue, save_queue


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

    ap = argparse.ArgumentParser(description="Remove an item from a Raumfeld zone queue.")
    ap.add_argument("zone", nargs="?", default="HomeOffice")
    ap.add_argument(
        "index",
        nargs="?",
        type=int,
        default=None,
        help="0-based index to remove (omit to clear entire queue)",
    )
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    args = ap.parse_args()

    zone = get_zone(args.zone, args.devices_file)
    zone_id = zone["udn"]
    print(f"Zone   : {zone['friendly_name']}")

    installation = Installation.ephemeral()
    load_index(installation.library, cfg.cache_dir)
    load_queue(installation.state, zone_id, cfg.cache_dir)

    queue = installation.state.get_or_create_queue(zone_id)

    if args.index is None:
        queue.clear()
        clear_queue(zone_id, cfg.cache_dir)
        print("Queue cleared.")
        return

    idx = args.index
    if idx < 0 or idx >= len(queue.items):
        ap.error(f"Index {idx} out of range (queue has {len(queue.items)} items)")

    removed = queue.remove_at(idx)
    item = installation.library.find_item(removed.media_item_id)
    print(f"Removed: {item.title if item else removed.media_item_id}")

    save_queue(queue, cfg.cache_dir)

    print(f"\nQueue ({zone['friendly_name']}):")
    _print_queue(installation, zone_id)


if __name__ == "__main__":
    main()
