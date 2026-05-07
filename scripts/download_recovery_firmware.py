#!/usr/bin/env python3
"""Download Teufel/Raumfeld recovery firmware images from the official update server."""

import hashlib
import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://updates.raumfeld.com/repair"

# Source: https://support.teufel.de/hc/de/articles/360011716460
IMAGES = [
    "base.img",      # Raumfeld Expand (alte Version, bis 2014)
    "base2.img",     # Raumfeld Expand (letzte Version, ab 2015)
    "connect.img",   # Raumfeld/Teufel Connector 1. Gen (bis 2013, WLAN-Antenne)
    "connect2.img",  # Raumfeld/Teufel Connector 2. Gen (keine äußere WLAN-Antenne)
    "connect3.img",  # Teufel Streamer / Connector 3. Gen
    "speaker.img",   # Raumfeld Speaker 1. Gen (äußere WLAN-Antenne)
    "speaker2.img",  # Teufel Speaker 2. Gen / Soundbar/-deck Streaming
    "speaker3.img",  # Teufel Speaker 3. Gen (LED-Streifen)
]

DEST = Path(__file__).parent.parent / "data" / "firmware"


def download(filename: str) -> None:
    url = f"{BASE_URL}/{filename}"
    dest = DEST / filename
    if dest.exists():
        print(f"  skip  {filename} (already exists, {dest.stat().st_size:,} bytes)")
        return
    print(f"  fetch {url}")
    with urllib.request.urlopen(url, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        data = bytearray()
        while chunk := resp.read(65536):
            data += chunk
            if total:
                pct = len(data) * 100 // total
                print(f"\r        {pct:3d}%  {len(data):,}/{total:,} bytes", end="", flush=True)
    print()
    dest.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    print(f"        saved {dest.stat().st_size:,} bytes  sha256={sha[:16]}…")


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"Destination: {DEST}\n")
    errors: list[str] = []
    for name in IMAGES:
        try:
            download(name)
        except Exception as exc:
            print(f"  ERROR {name}: {exc}")
            errors.append(name)
    print()
    if errors:
        print(f"Failed: {errors}")
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
