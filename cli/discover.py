"""raumtube-discover — scan the LAN for Raumfeld/Teufel UPnP devices."""

import argparse
import asyncio
import json
from pathlib import Path

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.discovery.ssdp import build_registry, detect_source_ip, discover


def main() -> None:
    ensure_utf8_stdout()

    cfg = load_config()

    ap = argparse.ArgumentParser(description="Scan for Raumfeld UPnP devices.")
    ap.add_argument(
        "--source-ip",
        default=cfg.source_ip or None,
        help="Local IP to bind the SSDP multicast socket (auto-detected when omitted)",
    )
    ap.add_argument(
        "--timeout", type=int, default=cfg.timeout, help="SSDP search timeout in seconds"
    )
    ap.add_argument("--output", default=str(cfg.devices_file), help="Where to write devices.json")
    args = ap.parse_args()

    source_ip = args.source_ip or detect_source_ip()
    if source_ip:
        print(f"Searching (source={source_ip}, timeout={args.timeout}s)...\n")
    else:
        print(f"Searching (source=auto, timeout={args.timeout}s)...\n")

    devices = asyncio.run(discover(source_ip, args.timeout))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    registry = build_registry(devices)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"\n{len(devices)} virtual devices written to {out}")
