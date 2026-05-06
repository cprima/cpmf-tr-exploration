"""Fetch SCPD XMLs, parse action signatures, build output dict."""

import logging
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

log = logging.getLogger(__name__)

PRIORITY = {
    "urn:schemas-upnp-org:service:AVTransport:1": [
        "GetTransportInfo",
        "GetPositionInfo",
        "GetMediaInfo",
        "SetAVTransportURI",
        "Play",
        "Pause",
        "Stop",
    ],
    "urn:schemas-upnp-org:service:RenderingControl:1": [
        "GetVolume",
        "SetVolume",
        "GetMute",
        "SetMute",
    ],
    "urn:schemas-upnp-org:service:ConnectionManager:1": [
        "GetProtocolInfo",
    ],
}


def fetch_xml(url: str) -> ET.Element | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return ET.fromstring(r.read())
    except Exception as exc:
        log.warning("Could not fetch %s: %s", url, exc)
        return None


def parse_scpd(root: ET.Element) -> tuple[dict, dict]:
    """Return (actions, state_vars) dicts."""
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]

    state_vars: dict[str, dict] = {}
    for sv in root.iter("stateVariable"):
        name = sv.findtext("name", "")
        dtype = sv.findtext("dataType", "")
        allowed = [v.text for v in sv.findall("allowedValueList/allowedValue")]
        state_vars[name] = {"dataType": dtype, "allowedValues": allowed or None}

    actions: dict[str, dict] = {}
    for action in root.iter("action"):
        aname = action.findtext("name", "")
        in_args, out_args = [], []
        for arg in action.findall("argumentList/argument"):
            aarg = {
                "name": arg.findtext("name", ""),
                "relatedStateVariable": arg.findtext("relatedStateVariable", ""),
            }
            if arg.findtext("direction") == "in":
                in_args.append(aarg)
            else:
                out_args.append(aarg)
        actions[aname] = {"in": in_args, "out": out_args}

    return actions, state_vars


def format_sig(aname: str, action: dict, state_vars: dict) -> str:
    def arg_str(a: dict) -> str:
        sv = state_vars.get(a["relatedStateVariable"], {})
        dtype = sv.get("dataType", "?")
        allowed = sv.get("allowedValues")
        suffix = f" [{','.join(allowed)}]" if allowed else ""
        return f"{a['name']}: {dtype}{suffix}"

    ins = ", ".join(arg_str(a) for a in action["in"]) or "—"
    outs = ", ".join(arg_str(a) for a in action["out"]) or "—"
    return f"  {aname}(in=[{ins}], out=[{outs}])"


def fetch_all(registry: dict) -> dict[str, dict]:
    """Fetch all SCPDs from a device registry, deduplicated by (service_type, filename)."""
    seen: dict[tuple, dict] = {}
    for device in registry["devices"]:
        for svc_type, svc in device["services"].items():
            scpd_url = svc["scpd_url"]
            filename = urlparse(scpd_url).path.split("/")[-1]
            key = (svc_type, filename)
            if key not in seen:
                seen[key] = {
                    "service_type": svc_type,
                    "scpd_url": scpd_url,
                    "example_device": device["friendly_name"],
                    "control_url": svc["control_url"],
                }

    priority_types = set(PRIORITY.keys())
    ordered = sorted((k, v) for k, v in seen.items() if k[0] in priority_types) + sorted(
        (k, v) for k, v in seen.items() if k[0] not in priority_types
    )

    output: dict[str, dict] = {}
    for key, info in ordered:
        svc_type = info["service_type"]
        svc_short = svc_type.split(":")[-2]
        root = fetch_xml(info["scpd_url"])
        if root is None:
            continue
        actions, state_vars = parse_scpd(root)
        output[f"{svc_short}::{key[1]}"] = {
            "service_type": svc_type,
            "scpd_url": info["scpd_url"],
            "control_url": info["control_url"],
            "actions": actions,
            "state_variables": state_vars,
        }
    return output
