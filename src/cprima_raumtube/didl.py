"""DIDL-Lite metadata builder for UPnP/DLNA."""

import xml.sax.saxutils as saxutils


def _fmt_dur(s: int) -> str:
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}"


def build_didl(
    uri: str,
    title: str,
    live: bool,
    thumbnail: str = "",
    duration: int = 0,
) -> str:
    if live:
        upnp_class = "object.item.audioItem.audioBroadcast"
        dur_attr = ""
        thumb_elem = ""
    else:
        upnp_class = "object.item.audioItem.musicTrack"
        dur_attr = f' duration="{_fmt_dur(duration)}"' if duration else ""
        thumb_elem = (
            (
                f'<upnp:albumArtURI dlna:profileID="JPEG_TN"'
                f' xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/">'
                f"{saxutils.escape(thumbnail)}</upnp:albumArtURI>"
            )
            if thumbnail
            else ""
        )

    raw = (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
        '<item id="0" parentID="-1" restricted="1">'
        f"<dc:title>{saxutils.escape(title)}</dc:title>"
        f"<upnp:class>{upnp_class}</upnp:class>"
        f"{thumb_elem}"
        f'<res protocolInfo="http-get:*:audio/mpeg:*"{dur_attr}>{saxutils.escape(uri)}</res>'
        "</item></DIDL-Lite>"
    )
    return saxutils.escape(raw)
