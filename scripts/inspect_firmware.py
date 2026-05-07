#!/usr/bin/env python3
"""
Inspect Raumfeld/Teufel recovery firmware images and generate documentation.

Run from the project root inside WSL:
    python3 scripts/inspect_firmware.py

Requires: binwalk, squashfs-tools (unsquashfs), e2fsprogs (debugfs), strings
Install:  sudo apt-get install binwalk squashfs-tools e2fsprogs binutils
"""

import argparse
import hashlib
import re
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (resolved relative to this script so WSL /mnt/... paths work)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIRMWARE_DIR = PROJECT_ROOT / "data" / "firmware"
WORK_DIR = PROJECT_ROOT / "data" / "firmware_extracted"
DOCS_DIR = PROJECT_ROOT / "docs" / "firmware"

# ---------------------------------------------------------------------------
# U-Boot legacy image header (64 bytes, big-endian)
# ---------------------------------------------------------------------------
UBOOT_MAGIC = 0x27051956
UBOOT_OS = {0: "invalid", 1: "OpenBSD", 2: "NetBSD", 3: "FreeBSD", 4: "4_4BSD",
             5: "Linux", 6: "SVR4", 7: "Esix", 8: "Solaris", 9: "Irix",
             10: "SCO", 11: "Dell", 12: "NCR", 13: "LynxOS", 14: "VxWorks",
             15: "pSOS", 16: "QNX", 17: "U-Boot", 18: "RTEMS"}
UBOOT_ARCH = {0: "invalid", 1: "alpha", 2: "arm", 3: "i386", 4: "ia64",
              5: "mips", 6: "mips64", 7: "ppc", 8: "s390", 9: "sh", 10: "sparc",
              11: "sparc64", 12: "m68k", 13: "nios", 14: "microblaze",
              15: "nios2", 16: "blackfin", 17: "avr32", 18: "st200",
              19: "sandbox", 20: "arc", 21: "x86_64", 22: "xtensa",
              23: "aarch64"}
UBOOT_TYPE = {0: "invalid", 1: "standalone", 2: "kernel", 3: "ramdisk",
              4: "multi", 5: "firmware", 6: "script", 7: "filesystem",
              8: "flat_dt"}
UBOOT_COMP = {0: "none", 1: "gzip", 2: "bzip2", 3: "lzma", 4: "lzo", 5: "lz4"}

FIT_MAGIC = 0xD00DFEED  # Flattened Image Tree (FDT magic, big-endian)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: Path | None = None, timeout: int = 300) -> tuple[int, str, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def detect_format(path: Path) -> dict:
    with path.open("rb") as f:
        head = f.read(64)

    magic32 = struct.unpack_from(">I", head)[0] if len(head) >= 4 else 0

    if magic32 == UBOOT_MAGIC:
        return _parse_uboot_header(head)

    if magic32 == FIT_MAGIC:
        return {"format": "U-Boot FIT (Flattened Image Tree)", "magic": hex(magic32)}

    # ext2/3/4: magic at byte 1080
    with path.open("rb") as f:
        f.seek(1080)
        ext_magic = f.read(2)
    if ext_magic == b"\x53\xef":
        return {"format": "ext2/3/4 filesystem", "magic": "0xEF53"}

    # FAT/MBR: boot signature at 510
    with path.open("rb") as f:
        f.seek(510)
        fat_sig = f.read(2)
    if fat_sig == b"\x55\xaa":
        return {"format": "FAT/MBR disk image", "magic": "0x55AA"}

    return {"format": "unknown", "magic": hex(magic32)}


def _parse_uboot_header(head: bytes) -> dict:
    if len(head) < 64:
        return {"format": "U-Boot uImage (truncated header)"}
    magic, hcrc, timestamp, size, load, ep, dcrc, os_, arch, typ, comp = \
        struct.unpack_from(">IIIIIIIBBBBB", head)
    name = head[32:64].rstrip(b"\x00").decode(errors="replace")
    return {
        "format": "U-Boot uImage (legacy)",
        "magic": hex(magic),
        "name": name,
        "timestamp": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
        "data_size": size,
        "load_addr": hex(load),
        "entry_point": hex(ep),
        "os": UBOOT_OS.get(os_, str(os_)),
        "arch": UBOOT_ARCH.get(arch, str(arch)),
        "type": UBOOT_TYPE.get(typ, str(typ)),
        "compression": UBOOT_COMP.get(comp, str(comp)),
    }


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_with_binwalk(img_path: Path, out_dir: Path) -> bool:
    if not shutil.which("binwalk"):
        print("  [!] binwalk not found — skipping extraction")
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"  binwalk -e {img_path.name} …")
    code, stdout, stderr = run(
        ["binwalk", "--extract", "--directory", str(out_dir),
         "--matryoshka", "--depth", "4", str(img_path)],
        timeout=600,
    )
    if code != 0:
        print(f"  [!] binwalk exit {code}: {stderr[:200]}")
    return out_dir.exists() and any(out_dir.iterdir())


# ---------------------------------------------------------------------------
# Version / capability probing
# ---------------------------------------------------------------------------

VERSION_PATTERNS = [
    re.compile(r"Linux version (\S+)"),
    re.compile(r"raumfeld[_-](\d[\d.]+)", re.IGNORECASE),
    re.compile(r"GUPnP/(\d[\d.]+)", re.IGNORECASE),
    re.compile(r"GStreamer (\d[\d.]+)", re.IGNORECASE),
    re.compile(r"VERSION[_=]\"?(\d[\d.]+)\"?"),
    re.compile(r"PRETTY_NAME=\"([^\"]+)\""),
    re.compile(r"BUILD_ID[=:](\S+)"),
]

CAPABILITY_FILES = [
    "etc/os-release",
    "etc/version",
    "etc/raumfeld-version",
    "etc/raumfeld/version",
    "etc/builddate",
    "etc/hostname",
    "etc/openwrt_release",
]

CAPABILITY_PATTERNS = {
    "TuneIn": re.compile(r"tunein", re.IGNORECASE),
    "Spotify": re.compile(r"spotify", re.IGNORECASE),
    "GStreamer": re.compile(r"gstreamer|gst-launch", re.IGNORECASE),
    "UPnP/DLNA": re.compile(r"gupnp|upnp|dlna", re.IGNORECASE),
    "Raumfeld": re.compile(r"raumfeld", re.IGNORECASE),
    "OpenWRT": re.compile(r"openwrt", re.IGNORECASE),
    "Buildroot": re.compile(r"buildroot", re.IGNORECASE),
    "SSH": re.compile(r"dropbear|openssh|sshd", re.IGNORECASE),
    "Avahi/mDNS": re.compile(r"avahi|mdns", re.IGNORECASE),
}


def probe_extracted(root: Path) -> dict:
    """Walk extracted filesystem tree and collect version/capability info."""
    findings: dict = {
        "versions": [],
        "capability_files": {},
        "capabilities": set(),
        "interesting_files": [],
        "kernel_version": None,
    }

    if not root.exists():
        return findings

    # 1. Read known version files
    for rel in CAPABILITY_FILES:
        candidate = root / rel
        if not candidate.exists():
            # binwalk may nest under a subdirectory
            candidates = list(root.rglob(rel.split("/")[-1]))
            if candidates:
                candidate = candidates[0]
            else:
                continue
        try:
            text = candidate.read_text(errors="replace").strip()
            findings["capability_files"][rel] = text
            for pat in VERSION_PATTERNS:
                m = pat.search(text)
                if m:
                    findings["versions"].append(m.group(0))
        except OSError:
            pass

    # 2. strings scan on raw img for kernel version
    if shutil.which("strings"):
        code, out, _ = run(["strings", "-n", "8", str(root.parent / (root.name + ".img"))
                             if (root.parent / (root.name + ".img")).exists()
                             else str(list(root.parent.glob("*.img"))[0])
                             ], timeout=120)
        for line in out.splitlines():
            for pat in VERSION_PATTERNS:
                m = pat.search(line)
                if m and m.group(0) not in findings["versions"]:
                    findings["versions"].append(m.group(0))
                    if "Linux version" in m.group(0):
                        findings["kernel_version"] = m.group(0)

    # 3. Walk tree for interesting files and capabilities
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_str = str(path.relative_to(root))

        # Note interesting paths
        if any(kw in rel_str for kw in ("raumfeld", "gupnp", "gstreamer",
                                         "spotify", "tunein", "upnp", "version",
                                         "gst-plugin", "avahi", "dropbear")):
            findings["interesting_files"].append(rel_str)

        # Try to read text files for capability scan
        if path.stat().st_size < 512 * 1024:  # skip large binaries
            try:
                text = path.read_text(errors="replace")
                for cap, pat in CAPABILITY_PATTERNS.items():
                    if pat.search(text):
                        findings["capabilities"].add(cap)
            except OSError:
                pass

    findings["capabilities"] = sorted(findings["capabilities"])
    findings["interesting_files"] = sorted(set(findings["interesting_files"]))[:50]
    findings["versions"] = list(dict.fromkeys(findings["versions"]))  # dedupe, preserve order
    return findings


def probe_with_strings(img_path: Path) -> dict:
    """Fallback: run strings on raw image when extraction is unavailable."""
    findings: dict = {
        "versions": [],
        "capability_files": {},
        "capabilities": set(),
        "interesting_files": [],
        "kernel_version": None,
    }
    if not shutil.which("strings"):
        return findings

    print("  strings scan (no extraction available) …")
    code, out, _ = run(["strings", "-n", "8", str(img_path)], timeout=180)
    for line in out.splitlines():
        for pat in VERSION_PATTERNS:
            m = pat.search(line)
            if m and m.group(0) not in findings["versions"]:
                findings["versions"].append(m.group(0))
                if "Linux version" in m.group(0):
                    findings["kernel_version"] = m.group(0)
        for cap, pat in CAPABILITY_PATTERNS.items():
            if pat.search(line):
                findings["capabilities"].add(cap)

    findings["capabilities"] = sorted(findings["capabilities"])
    return findings


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

DEVICE_LABELS = {
    "base.img":     "Raumfeld Expand / Base (1st gen, ≤2014)",
    "base2.img":    "Raumfeld Expand (2nd gen, ≥2015)",
    "connect.img":  "Raumfeld Connector (1st gen, ≤2013, external antenna)",
    "connect2.img": "Raumfeld/Teufel Connector (2nd gen, no external antenna)",
    "connect3.img": "Teufel Streamer / Connector (3rd gen)",
    "speaker.img":  "Raumfeld Speaker (1st gen, external antenna)",
    "speaker2.img": "Teufel Speaker (2nd gen) / Soundbar Streaming",
    "speaker3.img": "Teufel Speaker (3rd gen, LED strip)",
}


def write_image_doc(img_path: Path, fmt: dict, findings: dict, docs_dir: Path) -> Path:
    doc_path = docs_dir / (img_path.stem + ".md")
    label = DEVICE_LABELS.get(img_path.name, img_path.name)
    digest = sha256(img_path)
    size = img_path.stat().st_size

    lines = [
        f"# {img_path.name}",
        "",
        f"**Device**: {label}  ",
        f"**Source**: <https://updates.raumfeld.com/repair/{img_path.name}>  ",
        f"**Size**: {human_size(size)} ({size:,} bytes)  ",
        f"**SHA-256**: `{digest}`  ",
        f"**Analysed**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
        "## Image format",
        "",
    ]

    for k, v in fmt.items():
        lines.append(f"- **{k}**: `{v}`")

    lines += ["", "## Versions found", ""]
    if findings["versions"]:
        for v in findings["versions"][:20]:
            lines.append(f"- `{v}`")
    else:
        lines.append("_none detected_")

    if findings["kernel_version"]:
        lines += ["", f"> **Kernel**: `{findings['kernel_version']}`"]

    lines += ["", "## Capabilities detected", ""]
    if findings["capabilities"]:
        for cap in findings["capabilities"]:
            lines.append(f"- {cap}")
    else:
        lines.append("_none detected_")

    if findings["capability_files"]:
        lines += ["", "## Version / release files", ""]
        for fname, content in findings["capability_files"].items():
            lines += [f"### `{fname}`", "", "```", content[:1000], "```", ""]

    if findings["interesting_files"]:
        lines += ["", "## Interesting paths (up to 50)", ""]
        for p in findings["interesting_files"]:
            lines.append(f"- `{p}`")

    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return doc_path


def write_summary(results: list[dict], docs_dir: Path) -> None:
    path = docs_dir / "README.md"
    lines = [
        "# Raumfeld/Teufel Recovery Firmware — Analysis Summary",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  ",
        f"Source: <https://updates.raumfeld.com/repair/>  ",
        f"Reference: <https://support.teufel.de/hc/de/articles/360011716460>",
        "",
        "| Image | Device | Format | Kernel | Capabilities |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        name = r["image"]
        label = DEVICE_LABELS.get(name, name)
        fmt = r["fmt"].get("format", "?")
        kernel = r["findings"].get("kernel_version") or "—"
        if "Linux version" in kernel:
            kernel = kernel.replace("Linux version ", "")
        caps = ", ".join(r["findings"]["capabilities"]) or "—"
        lines.append(f"| [{name}]({Path(name).stem}.md) | {label} | {fmt} | `{kernel}` | {caps} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nSummary written: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect Raumfeld/Teufel recovery firmware images.")
    ap.add_argument("--firmware-dir", default=str(FIRMWARE_DIR), help="Directory with .img files")
    ap.add_argument("--work-dir", default=str(WORK_DIR), help="Extraction working directory")
    ap.add_argument("--docs-dir", default=str(DOCS_DIR), help="Output documentation directory")
    ap.add_argument("--no-extract", action="store_true", help="Skip binwalk extraction (strings only)")
    ap.add_argument("images", nargs="*", help="Specific .img files to process (default: all)")
    args = ap.parse_args()

    fw_dir = Path(args.firmware_dir)
    work_dir = Path(args.work_dir)
    docs_dir = Path(args.docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)

    images = [fw_dir / n for n in args.images] if args.images else sorted(fw_dir.glob("*.img"))
    if not images:
        sys.exit(f"No .img files found in {fw_dir}")

    results = []
    for img_path in images:
        if not img_path.exists():
            print(f"[SKIP] {img_path} not found")
            continue

        print(f"\n{'='*60}")
        print(f"  {img_path.name}  ({human_size(img_path.stat().st_size)})")
        print(f"{'='*60}")

        fmt = detect_format(img_path)
        print(f"  Format : {fmt.get('format')}")
        if "name" in fmt:
            print(f"  Name   : {fmt['name']}")
        if "timestamp" in fmt:
            print(f"  Built  : {fmt['timestamp']}")

        out_dir = work_dir / img_path.stem
        extracted = False
        if not args.no_extract:
            extracted = extract_with_binwalk(img_path, out_dir)

        if extracted:
            findings = probe_extracted(out_dir)
        else:
            findings = probe_with_strings(img_path)

        if findings["kernel_version"]:
            print(f"  Kernel : {findings['kernel_version']}")
        if findings["versions"]:
            print(f"  Versions ({len(findings['versions'])}): {', '.join(findings['versions'][:4])}")
        if findings["capabilities"]:
            print(f"  Caps   : {', '.join(findings['capabilities'])}")

        doc = write_image_doc(img_path, fmt, findings, docs_dir)
        print(f"  Doc    : {doc}")

        results.append({"image": img_path.name, "fmt": fmt, "findings": findings})

    write_summary(results, docs_dir)


if __name__ == "__main__":
    main()
