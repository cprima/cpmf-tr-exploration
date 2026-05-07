"""Generic UPnP SOAP caller — no domain logic."""

import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

log = logging.getLogger(__name__)


class SoapFault(RuntimeError):
    """Raised when a UPnP SOAP action returns an HTTP error response.

    code   HTTP status code from the device response (e.g. 500).
    """

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code

SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP_ENC = "http://schemas.xmlsoap.org/soap/encoding/"


def soap_call(
    control_url: str,
    service_type: str,
    action: str,
    arguments: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, str]:
    """Send a UPnP SOAP action and return response arguments as a dict.

    Values in `arguments` are inserted verbatim — callers are responsible
    for any XML escaping required by the UPnP layer.
    """
    args_xml = "".join(f"<{k}>{v}</{k}>" for k, v in (arguments or {}).items())
    body = (
        f'<?xml version="1.0"?>'
        f'<s:Envelope xmlns:s="{SOAP_ENV}" s:encodingStyle="{SOAP_ENC}">'
        f"<s:Body>"
        f'<u:{action} xmlns:u="{service_type}">'
        f"{args_xml}"
        f"</u:{action}>"
        f"</s:Body>"
        f"</s:Envelope>"
    )

    if debug:
        log.debug("POST %s  SOAPAction: %s#%s", control_url, service_type, action)
        log.debug("body: %s", body)

    req = urllib.request.Request(
        control_url,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{service_type}#{action}"',
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        fault = _parse_fault(raw)
        raise SoapFault(f"SOAP fault {e.code}: {fault}", code=e.code) from e

    if debug:
        log.debug("response: %s", raw.decode(errors="replace")[:400])

    return _parse_response(raw, action)


def _parse_response(raw: bytes, action: str) -> dict[str, str]:
    root = ET.fromstring(raw)
    result: dict[str, str] = {}
    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag == f"{action}Response":
            for child in el:
                ctag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                result[ctag] = child.text or ""
    return result


def _parse_fault(raw: bytes) -> str:
    try:
        root = ET.fromstring(raw)
        parts = []
        for el in root.iter():
            tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if tag in ("faultstring", "errorCode", "errorDescription") and el.text:
                parts.append(f"{tag}={el.text.strip()}")
        return "; ".join(parts) or raw.decode(errors="replace")[:300]
    except Exception:
        return raw.decode(errors="replace")[:300]
