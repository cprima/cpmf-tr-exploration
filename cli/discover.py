"""raumtube-discover — scan the LAN for Raumfeld/Teufel UPnP devices."""

import argparse
import asyncio
import json
from pathlib import Path

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.discovery.ssdp import build_registry, discover


def main() -> None:
    ensure_utf8_stdout()

    cfg = load_config()

    ap = argparse.ArgumentParser(description="Scan for Raumfeld UPnP devices.")
    ap.add_argument(
        "--source-ip",
        default=cfg.source_ip,
        help="Local IP to bind the SSDP multicast socket (required on Windows)",
    )
    ap.add_argument(
        "--timeout", type=int, default=cfg.timeout, help="SSDP search timeout in seconds"
    )
    ap.add_argument("--output", default=str(cfg.devices_file), help="Where to write devices.json")
    args = ap.parse_args()

    if not args.source_ip:
        ap.error("--source-ip is required (or set RAUMTUBE_SOURCE_IP)")

    print(f"Searching (source={args.source_ip}, timeout={args.timeout}s)...\n")
    devices = asyncio.run(discover(args.source_ip, args.timeout))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    registry = build_registry(devices)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"\n{len(devices)} virtual devices written to {out}")
