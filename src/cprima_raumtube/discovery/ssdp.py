"""SSDP discovery — async, returns a list of device dicts."""

import logging
import socket
from datetime import UTC, datetime

from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.search import async_search

log = logging.getLogger(__name__)


def detect_source_ip() -> str | None:
    """Return the IP of the default outbound interface, or None if unreachable.

    Uses a non-sending UDP connect trick: the OS selects the right interface
    without sending any packets.  Works on Windows, Linux, and macOS.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


async def discover(
    source_ip: str | None = None,
    timeout: int = 6,
    search_target: str = "ssdp:all",
) -> list[dict]:
    """Run SSDP discovery and return a list of device entry dicts.

    Only GUPnP devices are included (Raumfeld/Teufel stack).
    source_ip binds the multicast socket to a specific interface.  When
    omitted it is auto-detected from the default outbound interface.
    """
    effective_ip = source_ip or detect_source_ip()
    source = (effective_ip, 0) if effective_ip else None

    requester = AiohttpRequester()
    factory = UpnpFactory(requester)
    seen: dict[str, dict] = {}

    async def on_response(data: dict) -> None:
        if "GUPnP" not in data.get("server", ""):
            return
        location = data.get("location", "")
        if location in seen:
            return
        seen[location] = {}
        try:
            device = await factory.async_create_device(location)
        except Exception as exc:
            log.warning("Could not load %s: %s", location, exc)
            return

        entry = {
            "ip": data["_host"],
            "location": location,
            "friendly_name": device.friendly_name,
            "manufacturer": device.manufacturer,
            "model_name": device.model_name,
            "udn": device.udn,
            "server": data.get("server", ""),
            "services": {
                svc_id: {
                    "service_type": svc.service_type,
                    "control_url": svc.control_url,
                    "event_sub_url": svc.event_sub_url,
                    "scpd_url": svc.scpd_url,
                }
                for svc_id, svc in device.services.items()
            },
        }
        seen[location] = entry
        log.info("  %s  %s  [%s]", entry["ip"], entry["friendly_name"], entry["model_name"])

    await async_search(
        async_callback=on_response,
        timeout=timeout,
        search_target=search_target,
        source=source,
    )
    return list(seen.values())


def build_registry(devices: list[dict]) -> dict:
    return {
        "discovered_at": datetime.now(UTC).isoformat(),
        "devices": devices,
    }
