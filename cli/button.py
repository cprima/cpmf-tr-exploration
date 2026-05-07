"""raumtube-button — list and trigger station buttons on a Raumfeld renderer.

Physical button presses fail on some firmware versions because the renderer
cannot parse TuneIn M3U playlists (missing GStreamer plug-in). This command
resolves the M3U to a direct stream URL before calling SetAVTransportURI.
"""

import argparse
import urllib.request

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.devices import get_zone, load_media_server
from cprima_raumtube.soap import soap_call
from cprima_raumtube.upnp.content_directory import ContentDirectory

AVT_SVC = "urn:schemas-upnp-org:service:AVTransport:1"


def _resolve_stream(uri: str) -> str:
    """Follow M3U/PLS redirects to get a direct stream URL."""
    content_type = ""
    try:
        req = urllib.request.Request(uri, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            content_type = r.headers.get("Content-Type", "")
            if "mpegurl" in content_type or "scpls" in content_type or uri.endswith((".m3u", ".m3u8", ".pls")):
                lines = r.read().decode(errors="replace").strip().splitlines()
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and line.startswith("http"):
                        return line
    except Exception:
        pass
    return uri


def _buttons_for_renderer(cd: ContentDirectory, renderer_udn: str) -> list[dict]:
    items = cd.browse(f"0/Renderers/{renderer_udn}/StationButtons")
    enriched = []
    for item in items:
        if not item.get("resources"):
            meta = cd.browse_metadata(item["id"])
            if meta:
                item = meta[0]
        enriched.append(item)
    return enriched


def main() -> None:
    ensure_utf8_stdout()

    cfg = load_config()

    ap = argparse.ArgumentParser(
        description="List and trigger station buttons on a Raumfeld renderer."
    )
    ap.add_argument("action", choices=["list", "play"], default="list", nargs="?")
    ap.add_argument("button", type=int, nargs="?", help="Button number to play (1-based)")
    ap.add_argument("--zone", default="HomeOffice")
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    args = ap.parse_args()

    server = load_media_server(args.devices_file)
    if server is None:
        ap.error("No ContentDirectory device found — run raumtube-discover first")

    zone = get_zone(args.zone, args.devices_file)
    renderer_udn = zone["udn"]
    avt = zone["avt_control"]

    cd = ContentDirectory(server["cd_control"])
    buttons = _buttons_for_renderer(cd, renderer_udn)

    if not buttons:
        print(f"No button assignments found for {zone['friendly_name']}")
        return

    if args.action == "list" or args.button is None:
        print(f"Zone: {zone['friendly_name']} ({renderer_udn})")
        print(f"{'Btn':>4}  {'Title':<30}  Stream URI")
        print("-" * 80)
        for item in buttons:
            btn_num = item.get("button", "?")
            title = item.get("title", "?")
            resources = item.get("resources", [])
            uri = resources[0]["uri"][:55] if resources else "—"
            print(f"{btn_num:>4}  {title:<30}  {uri}")
        return

    # play mode
    target = next((it for it in buttons if str(it.get("button")) == str(args.button)), None)
    if target is None:
        available = [it.get("button") for it in buttons]
        ap.error(f"Button {args.button} not found. Available: {available}")

    resources = target.get("resources", [])
    if not resources:
        ap.error(f"Button {args.button} has no stream URI in ContentDirectory")

    raw_uri = resources[0]["uri"]
    title = target.get("title", "?")

    print(f"Zone    : {zone['friendly_name']}")
    print(f"Button  : {args.button} — {title}")
    print(f"Raw URI : {raw_uri}")

    stream_uri = _resolve_stream(raw_uri)
    if stream_uri != raw_uri:
        print(f"Resolved: {stream_uri}")

    item_id = target.get("id", "")
    item_class = target.get("class", "object.item.audioItem.audioBroadcast.radio")
    proto = resources[0].get("protocolInfo", "http-get:*:audio/mpeg:*")
    if stream_uri != raw_uri:
        proto = "http-get:*:audio/mpeg:*"

    metadata = (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"'
        ' xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<item id="{item_id}" parentID="0/Renderers/{renderer_udn}/StationButtons" restricted="1">'
        f"<dc:title>{title}</dc:title>"
        f"<upnp:class>{item_class}</upnp:class>"
        f'<res protocolInfo="{proto}">{stream_uri}</res>'
        "</item>"
        "</DIDL-Lite>"
    )

    soap_call(avt, AVT_SVC, "SetAVTransportURI", {
        "InstanceID": "0",
        "CurrentURI": stream_uri,
        "CurrentURIMetaData": metadata,
    })
    soap_call(avt, AVT_SVC, "Play", {"InstanceID": "0", "Speed": "1"})
    print("Playing — press Enter to stop")

    import contextlib
    with contextlib.suppress(KeyboardInterrupt):
        input()

    soap_call(avt, AVT_SVC, "Stop", {"InstanceID": "0"})
    print("Stopped.")
