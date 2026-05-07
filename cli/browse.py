"""raumtube-browse — explore the Raumfeld MediaServer ContentDirectory."""

import argparse
import json

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.devices import load_media_server
from cprima_raumtube.upnp.content_directory import ContentDirectory


def main() -> None:
    ensure_utf8_stdout()

    cfg = load_config()

    ap = argparse.ArgumentParser(description="Browse the Raumfeld MediaServer ContentDirectory.")
    ap.add_argument("object_id", nargs="?", default="0", help="ObjectID to browse (default: root)")
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    ap.add_argument("--metadata", action="store_true", help="BrowseMetadata instead of children")
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--json", dest="as_json", action="store_true", help="Raw JSON output")
    args = ap.parse_args()

    server = load_media_server(args.devices_file)
    if server is None:
        ap.error("No ContentDirectory device found in devices file — run raumtube-discover first")

    print(f"Server : {server['friendly_name']} ({server['model']})  {server['ip']}")
    print(f"CD URL : {server['cd_control']}")
    print(f"Object : {args.object_id}")
    print()

    cd = ContentDirectory(server["cd_control"])
    items = cd.browse(args.object_id, count=args.count) if not args.metadata else cd.browse_metadata(args.object_id)

    if args.as_json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return

    if not items:
        print("(empty)")
        return

    for item in items:
        kind = item.get("type", "?")
        oid = item.get("id", "?")
        title = item.get("title", item.get("name", "—"))
        cls = item.get("class", "")
        resources = item.get("resources", [])
        res_uri = resources[0]["uri"] if resources else ""

        marker = "[C]" if kind == "container" else "[I]"
        print(f"{marker} {oid:30s}  {title}")
        if cls:
            print(f"         class: {cls}")
        if res_uri:
            print(f"         uri:   {res_uri}")
