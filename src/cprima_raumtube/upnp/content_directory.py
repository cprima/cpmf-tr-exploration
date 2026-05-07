"""ContentDirectory client — browse and queue operations on the Raumfeld hub."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from cprima_raumtube.soap import soap_call

CD_SVC = "urn:schemas-upnp-org:service:ContentDirectory:1"
RF_SVC = "urn:schemas-raumfeld-com:service:RaumfeldGenerator:1"

_DIDL = "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
_DC = "http://purl.org/dc/elements/1.1/"
_UPNP = "urn:schemas-upnp-org:metadata-1-0/upnp/"


class ContentDirectory:
    def __init__(self, control_url: str) -> None:
        self._url = control_url

    # ── Browse ────────────────────────────────────────────────────────────────

    def browse(
        self,
        object_id: str = "0",
        flag: str = "BrowseDirectChildren",
        start: int = 0,
        count: int = 200,
    ) -> list[dict]:
        result = soap_call(
            self._url,
            CD_SVC,
            "Browse",
            {
                "ObjectID": object_id,
                "BrowseFlag": flag,
                "Filter": "*",
                "StartingIndex": str(start),
                "RequestedCount": str(count),
                "SortCriteria": "",
            },
        )
        didl_xml = result.get("Result", "")
        if not didl_xml:
            return []
        return _parse_didl(didl_xml)

    def browse_metadata(self, object_id: str) -> list[dict]:
        return self.browse(object_id, flag="BrowseMetadata")

    # ── Queue operations (Raumfeld-specific) ─────────────────────────────────

    def create_queue(self, title: str = "raumtube-queue") -> str:
        """Create a new server-side queue. Returns the new ObjectID."""
        result = soap_call(
            self._url,
            CD_SVC,
            "CreateObject",
            {
                "ContainerID": "0",
                "Elements": (
                    '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"'
                    ' xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"'
                    ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
                    f'<container id="" parentID="0" restricted="0">'
                    f"<dc:title>{title}</dc:title>"
                    "<upnp:class>object.container.playlistContainer</upnp:class>"
                    "</container>"
                    "</DIDL-Lite>"
                ),
            },
        )
        return result.get("ObjectID", "")

    def add_uri_to_queue(self, queue_id: str, uri: str, title: str = "", metadata: str = "") -> str:
        """Add a URI to an existing queue container. Returns new item ObjectID."""
        if not metadata:
            metadata = (
                '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"'
                ' xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"'
                ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
                f'<item id="" parentID="{queue_id}" restricted="0">'
                f"<dc:title>{title or uri}</dc:title>"
                "<upnp:class>object.item.audioItem.musicTrack</upnp:class>"
                f'<res protocolInfo="http-get:*:audio/mpeg:*">{uri}</res>'
                "</item>"
                "</DIDL-Lite>"
            )
        result = soap_call(
            self._url,
            CD_SVC,
            "CreateObject",
            {"ContainerID": queue_id, "Elements": metadata},
        )
        return result.get("ObjectID", "")

    # ── Raumfeld generator (native queue management) ─────────────────────────

    def rf_create_queue(self, control_url: str, name: str = "raumtube") -> str:
        """RaumfeldGenerator CreateQueue — returns queue ID."""
        result = soap_call(control_url, RF_SVC, "CreateQueue", {"QueueName": name})
        return result.get("QueueID", "")

    def rf_add_item(
        self,
        control_url: str,
        queue_id: str,
        uri: str,
        metadata: str = "",
    ) -> None:
        """RaumfeldGenerator AddItemToQueue."""
        soap_call(
            control_url,
            RF_SVC,
            "AddItemToQueue",
            {
                "QueueID": queue_id,
                "Uri": uri,
                "UriMetaData": metadata,
                "DesiredFirstTrackNumberEnqueued": "1",
                "EnqueuedAfterTrackNumber": "0",
            },
        )


def _parse_didl(xml_str: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return []

    items = []
    for el in root:
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        entry: dict = {
            "type": tag,
            "id": el.get("id", ""),
            "parentID": el.get("parentID", ""),
            "restricted": el.get("restricted", ""),
        }
        for child in el:
            ctag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if ctag == "res":
                entry.setdefault("resources", []).append({
                    "uri": child.text or "",
                    "protocolInfo": child.get("protocolInfo", ""),
                    "duration": child.get("duration", ""),
                    "size": child.get("size", ""),
                })
            else:
                entry[ctag] = child.text or ""
        items.append(entry)
    return items
