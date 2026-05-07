"""Tests for ProtocolInfo parsing."""

import pytest

from cprima_raumtube.model.protocol import ProtocolInfo


def test_parse_full():
    raw = "http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_FLAGS=01700000"
    pi = ProtocolInfo.parse(raw)
    assert pi.protocol == "http-get"
    assert pi.network == "*"
    assert pi.content_format == "audio/mpeg"
    assert pi.additional_info["DLNA.ORG_PN"] == "MP3"
    assert "DLNA.ORG_FLAGS" in pi.additional_info
    assert pi.raw == raw


def test_parse_minimal_additional():
    pi = ProtocolInfo.parse("http-get:*:audio/mpeg:")
    assert pi.protocol == "http-get"
    assert pi.content_format == "audio/mpeg"
    assert pi.additional_info == {}


def test_parse_missing_fields():
    pi = ProtocolInfo.parse("http-get")
    assert pi.protocol == "http-get"
    assert pi.network == "*"
    assert pi.content_format == ""


def test_parse_raw_preserved():
    raw = "http-get:*:audio/flac:DLNA.ORG_PN=FLAC"
    pi = ProtocolInfo.parse(raw)
    assert pi.raw == raw


def test_parse_is_frozen():
    pi = ProtocolInfo.parse("http-get:*:audio/mpeg:")
    with pytest.raises((AttributeError, TypeError)):
        pi.protocol = "rtsp"  # type: ignore[misc]


def test_parse_additional_info_key_only():
    pi = ProtocolInfo.parse("http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;SOMEKEY")
    assert "SOMEKEY" in pi.additional_info
    assert pi.additional_info["SOMEKEY"] == ""
