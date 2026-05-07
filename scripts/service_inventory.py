#!/usr/bin/env python3
"""
Scan ~/fw_work/ extracted rootfs trees and produce docs/firmware/SERVICES.md.

Run from the project root on WSL:
    python3 -u scripts/service_inventory.py

Or via uv:
    uv run scripts/service_inventory.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

WORK_DIR = Path.home() / "fw_work"

# Resolved relative to the script's own location so it works from any cwd.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUT_FILE = PROJECT_ROOT / "docs" / "firmware" / "SERVICES.md"

# Images in generation order.
IMAGES = [
    ("base",     "Gen 1 – Base Station"),
    ("base2",    "Gen 2 – Base Station"),
    ("connect",  "Gen 1 – Connector"),
    ("connect2", "Gen 2 – Connector"),
    ("connect3", "Gen 3 – Connector"),
    ("speaker",  "Gen 1 – Speaker"),
    ("speaker2", "Gen 2 – Speaker"),
    ("speaker3", "Gen 3 – Speaker"),
]


def find_rootfs(image_dir: Path) -> Path | None:
    """Return the best-guess rootfs root inside an extracted image directory."""
    # Prefer _pass2_0 (the largest/fullest extracted filesystem).
    candidate = image_dir / "_pass2_0"
    if candidate.is_dir():
        return candidate
    # Fall back: any _pass2_* dir.
    for p in sorted(image_dir.glob("_pass2_*")):
        if p.is_dir():
            return p
    return None


def rel(path: Path, base: Path) -> str:
    try:
        return "/" + str(path.relative_to(base))
    except ValueError:
        return str(path)


def collect_files(root: Path, glob: str) -> list[Path]:
    return sorted(root.glob(glob))


def collect_raumfeld_bins(root: Path) -> list[Path]:
    bins: list[Path] = []
    for d in ("usr/bin", "usr/sbin", "bin", "sbin", "raumfeld/hardwared"):
        p = root / d
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if f.is_file() and "raumfeld" in f.name.lower():
                    bins.append(f)
    return bins


def collect_libs(root: Path) -> list[Path]:
    libs: list[Path] = []
    for d in ("usr/lib", "lib"):
        p = root / d
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if f.is_file() and f.name.startswith("libraumfeld"):
                    libs.append(f)
    return libs


def read_services_endpoints(root: Path) -> str | None:
    p = root / "usr" / "share" / "raumfeld-1.0" / "services"
    if p.is_file():
        return p.read_text(errors="replace").strip()
    return None


def collect_dsp_devices(root: Path) -> list[str]:
    dsp_dir = root / "raumfeld" / "hardwared" / "dsp-config"
    if not dsp_dir.is_dir():
        return []
    names = []
    for f in sorted(dsp_dir.glob("*.xml")):
        name = f.stem.removesuffix("-alsa")
        names.append(name)
    return names


def collect_dbus_configs(root: Path) -> list[Path]:
    d = root / "etc" / "dbus-1" / "system.d"
    if not d.is_dir():
        return []
    return sorted(f for f in d.iterdir() if f.is_file())


def collect_init_scripts(root: Path) -> list[Path]:
    d = root / "etc" / "init.d"
    if not d.is_dir():
        return []
    return sorted(f for f in d.iterdir() if f.is_file())


def build_section(image_name: str, label: str) -> list[str]:
    lines: list[str] = []
    image_dir = WORK_DIR / image_name

    if not image_dir.is_dir():
        lines.append(f"## {image_name} — {label}\n")
        lines.append(f"_Not extracted (missing `{image_dir}`)._\n")
        return lines

    root = find_rootfs(image_dir)
    if root is None:
        lines.append(f"## {image_name} — {label}\n")
        lines.append(f"_No rootfs found under `{image_dir}`._\n")
        return lines

    print(f"  Scanning {image_name} → {root.name} …", flush=True)

    lines.append(f"## {image_name} — {label}\n")
    lines.append(f"Rootfs: `{root.name}`\n")

    # --- Init scripts ---
    inits = collect_init_scripts(root)
    if inits:
        lines.append("\n### Boot / init scripts\n")
        lines.append("| Script | Purpose |\n|---|---|\n")
        for f in inits:
            purpose = _init_purpose(f.name)
            lines.append(f"| `{f.name}` | {purpose} |\n")

    # --- D-Bus configs ---
    dbus = collect_dbus_configs(root)
    if dbus:
        lines.append("\n### D-Bus policy files\n")
        for f in dbus:
            lines.append(f"- `{rel(f, root)}`\n")

    # --- Raumfeld binaries ---
    bins = collect_raumfeld_bins(root)
    if bins:
        lines.append("\n### Raumfeld binaries\n")
        for f in bins:
            lines.append(f"- `{rel(f, root)}`\n")

    # --- Shared libraries ---
    libs = collect_libs(root)
    if libs:
        lines.append("\n### Raumfeld shared libraries\n")
        for f in libs:
            lines.append(f"- `{f.name}`\n")

    # --- Cloud API endpoints ---
    endpoints = read_services_endpoints(root)
    if endpoints:
        lines.append("\n### Cloud API endpoints (`usr/share/raumfeld-1.0/services`)\n")
        lines.append("```\n")
        lines.append(endpoints + "\n")
        lines.append("```\n")

    # --- DSP device profiles ---
    dsp = collect_dsp_devices(root)
    if dsp:
        lines.append("\n### DSP / hardware profiles (`raumfeld/hardwared/dsp-config/`)\n")
        for name in dsp:
            lines.append(f"- `{name}`\n")

    lines.append("\n")
    return lines


def _init_purpose(name: str) -> str:
    MAP = {
        "S05avahi-setup.sh": "Avahi/mDNS early setup",
        "S10udev":           "udev device manager",
        "S20urandom":        "Seed /dev/urandom entropy",
        "S30dbus":           "Start D-Bus system daemon",
        "S40network":        "Network interface bringup",
        "S50dropbear":       "SSH daemon (dropbear)",
        "S80dhcp-relay":     "DHCP relay agent",
        "S80dhcp-server":    "DHCP server",
        "rcS":               "Sysinit entry point",
        "rcK":               "Shutdown entry point",
    }
    return MAP.get(name, "—")


def main() -> None:
    if not WORK_DIR.is_dir():
        sys.exit(f"ERROR: {WORK_DIR} does not exist — run inspect_firmware.py first.")

    print(f"Service inventory scan → {OUT_FILE}", flush=True)

    doc: list[str] = []
    doc.append("# Raumfeld Firmware — Service Inventory\n\n")
    doc.append(
        "Extracted from `~/fw_work/` by `scripts/service_inventory.py`.\n"
        "Each section covers one firmware image's rootfs (`_pass2_0`).\n\n"
    )

    for image_name, label in IMAGES:
        doc.extend(build_section(image_name, label))
        doc.append("---\n\n")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text("".join(doc), encoding="utf-8")
    print(f"Written: {OUT_FILE}", flush=True)


if __name__ == "__main__":
    main()
