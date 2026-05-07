"""raumtube-fav — list and play ContentDirectory favourites on a Raumfeld zone."""

import argparse

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.devices import get_zone, load_media_server
from cprima_raumtube.soap import soap_call
from cprima_raumtube.upnp.content_directory import ContentDirectory

AVT_SVC = "urn:schemas-upnp-org:service:AVTransport:1"
FAV_OBJ = "0/Favorites/MyFavorites"


def _list_favs(cd: ContentDirectory) -> list[dict]:
    return cd.browse(FAV_OBJ)


def _play_item(item: dict, avt_control: str, metadata_didl: str) -> None:
    uri = ""
    for res in item.get("resources", []):
        if res.get("uri"):
            uri = res["uri"]
            break
    if not uri:
        raise ValueError(f"No stream URI in favourite {item.get('title', '?')!r}")
    soap_call(avt_control, AVT_SVC, "SetAVTransportURI", {
        "InstanceID": "0",
        "CurrentURI": uri,
        "CurrentURIMetaData": metadata_didl,
    })
    soap_call(avt_control, AVT_SVC, "Play", {"InstanceID": "0", "Speed": "1"})


def main() -> None:
    ensure_utf8_stdout()

    cfg = load_config()

    ap = argparse.ArgumentParser(description="List and play ContentDirectory favourites.")
    ap.add_argument("action", choices=["list", "play"], default="list", nargs="?")
    ap.add_argument("index", type=int, nargs="?", help="1-based index to play")
    ap.add_argument("--zone", default="HomeOffice")
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    args = ap.parse_args()

    server = load_media_server(args.devices_file)
    if server is None:
        ap.error("No ContentDirectory device found — run raumtube-discover first")

    cd = ContentDirectory(server["cd_control"])
    favs = _list_favs(cd)

    if not favs or args.action == "list":
        print(f"{'#':>3}  {'Title':<35}  Class")
        print("-" * 70)
        for i, fav in enumerate(favs, 1):
            title = fav.get("title", fav.get("id", "?"))
            cls = fav.get("class", "").split(".")[-1]
            resources = fav.get("resources", [])
            uri = resources[0]["uri"][:50] if resources else "—"
            print(f"{i:>3}  {title:<35}  {cls}")
            print(f"     {uri}")
        if not favs:
            print("(no favourites found)")
        return

    # play mode
    if args.index is None:
        ap.error("provide an index (1-based) to play")
    if not (1 <= args.index <= len(favs)):
        ap.error(f"index must be 1-{len(favs)}")

    item = favs[args.index - 1]
    title = item.get("title", item.get("id", "?"))

    zone = get_zone(args.zone, args.devices_file)
    avt = zone["avt_control"]

    # Build minimal DIDL-Lite metadata for the item
    item_id = item.get("id", "")
    parent_id = item.get("parentID", FAV_OBJ)
    item_class = item.get("class", "object.item.audioItem")
    resources = item.get("resources", [])
    res_xml = ""
    for res in resources:
        proto = res.get("protocolInfo", "http-get:*:audio/mpeg:*")
        uri = res.get("uri", "")
        res_xml += f'<res protocolInfo="{proto}">{uri}</res>'

    metadata = (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"'
        ' xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<item id="{item_id}" parentID="{parent_id}" restricted="1">'
        f"<dc:title>{title}</dc:title>"
        f"<upnp:class>{item_class}</upnp:class>"
        f"{res_xml}"
        "</item>"
        "</DIDL-Lite>"
    )

    print(f"Zone   : {zone['friendly_name']}")
    print(f"Playing: {title}")
    if resources:
        print(f"URI    : {resources[0]['uri'][:80]}")

    _play_item(item, avt, metadata)
    print("Playing — press Ctrl+C to stop")
    try:
        import contextlib
        with contextlib.suppress(KeyboardInterrupt):
            input()
    finally:
        soap_call(avt, AVT_SVC, "Stop", {"InstanceID": "0"})
        print("\nStopped.")
