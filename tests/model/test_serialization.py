"""Serialization boundary tests — verify dataclasses can be round-tripped via dict."""
from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime

from cprima_raumtube.model.media import AppQueue, QueueItem, QueueItemState
from cprima_raumtube.model.playback import PlaybackPosition
from cprima_raumtube.model.protocol import ProtocolInfo


def _json_serializable(obj: object) -> object:
    """Minimal converter for dataclasses.asdict output."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_serializable(i) for i in obj]
    return obj


class TestProtocolInfoSerialization:
    def test_asdict_fields_present(self) -> None:
        pi = ProtocolInfo.parse("http-get:*:audio/mpeg:DLNA.ORG_PN=MP3")
        d = dataclasses.asdict(pi)
        assert set(d.keys()) == {"protocol", "network", "content_format", "additional_info", "raw"}

    def test_json_roundtrip(self) -> None:
        pi = ProtocolInfo.parse("http-get:*:audio/mpeg:DLNA.ORG_PN=MP3")
        d = dataclasses.asdict(pi)
        serialized = json.dumps(d)
        restored = json.loads(serialized)
        assert restored["protocol"] == "http-get"
        assert restored["additional_info"]["DLNA.ORG_PN"] == "MP3"


class TestPlaybackPositionSerialization:
    def test_asdict_fields(self) -> None:
        pos = PlaybackPosition(rel_seconds=42.0)
        d = dataclasses.asdict(pos)
        assert "rel_seconds" in d
        assert "updated_at" in d
        assert d["rel_seconds"] == 42.0

    def test_json_roundtrip(self) -> None:
        t = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        pos = PlaybackPosition(rel_seconds=10.0, updated_at=t)
        d = dataclasses.asdict(pos)
        serialized = json.dumps(_json_serializable(d))
        restored = json.loads(serialized)
        assert restored["rel_seconds"] == 10.0


class TestAppQueueSerialization:
    def test_asdict_with_items(self) -> None:
        q = AppQueue(id="q1", zone_id="z1")
        q.append(QueueItem(id="i1", media_item_id="m1"))
        d = dataclasses.asdict(q)
        assert d["zone_id"] == "z1"
        # Private backing field is serialized as "_items" by dataclasses.asdict
        assert len(d["_items"]) == 1
        assert d["_items"][0]["state"] == QueueItemState.PENDING

    def test_json_roundtrip_state_as_string(self) -> None:
        q = AppQueue(id="q1", zone_id="z1")
        q.append(QueueItem(id="i1", media_item_id="m1"))
        d = dataclasses.asdict(q)
        serialized = json.dumps(_json_serializable(d))
        restored = json.loads(serialized)
        # Private backing field is serialized as "_items" by dataclasses.asdict
        assert restored["_items"][0]["state"] == "pending"
