"""Load the device registry and select zone renderers by friendly name."""

import json
from pathlib import Path

AVT_SVC = "urn:schemas-upnp-org:service:AVTransport:1"
RC_SVC = "urn:schemas-upnp-org:service:RenderingControl:1"
CM_SVC = "urn:schemas-upnp-org:service:ConnectionManager:1"


def load_zones(path: str | Path = "data/devices.json") -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        registry = json.load(f)

    zones: dict[str, dict] = {}
    for device in registry["devices"]:
        svcs = device["services"]
        if AVT_SVC in svcs and RC_SVC in svcs:
            name = device["friendly_name"]
            zones[name] = {
                "friendly_name": name,
                "model": device["model_name"],
                "ip": device["ip"],
                "udn": device["udn"],
                "avt_control": svcs[AVT_SVC]["control_url"],
                "rc_control": svcs[RC_SVC]["control_url"],
                "cm_control": svcs[CM_SVC]["control_url"] if CM_SVC in svcs else None,
            }
    return zones


def get_zone(name: str, path: str | Path = "data/devices.json") -> dict:
    zones = load_zones(path)
    if name in zones:
        return zones[name]
    for zone_name, zone in zones.items():
        if name.lower() in zone_name.lower():
            return zone
    available = list(zones.keys())
    raise KeyError(f"Zone {name!r} not found. Available: {available}")
