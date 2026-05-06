"""YouTube audio source — requires the [youtube] extra (yt-dlp)."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)


def probe(url: str) -> dict:
    """Quick metadata probe via yt-dlp — no download."""
    import yt_dlp  # lazy import: only available with [youtube] extra

    opts = {
        "format": "bestaudio[ext=webm]/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def is_live_stream(info: dict) -> bool:
    return bool(info.get("is_live")) or info.get("live_status") in {"is_live", "is_upcoming"}


# ── Sidecar (metadata cache) ──────────────────────────────────────────────────


def _sidecar_path(cache_dir: Path, video_id: str) -> Path:
    return cache_dir / f"{video_id}.json"


def save_sidecar(cache_dir: Path, info: dict) -> None:
    sidecar = {
        "id": info.get("id", ""),
        "title": info.get("title", ""),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail", ""),
        "uploader": info.get("uploader", ""),
        "is_live": bool(info.get("is_live")),
        "live_status": info.get("live_status", ""),
        "cached_at": datetime.now(UTC).isoformat(),
    }
    with open(_sidecar_path(cache_dir, info["id"]), "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)


def load_sidecar(cache_dir: Path, video_id: str) -> dict | None:
    path = _sidecar_path(cache_dir, video_id)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


# ── Download ──────────────────────────────────────────────────────────────────


def download_to_cache(url: str, info: dict, cache_dir: Path) -> Path:
    """Download + transcode to MP3. Returns path; uses cached file if present."""
    import yt_dlp  # lazy import

    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{info['id']}.mp3"

    if path.exists():
        log.info("Cache hit: %s  (%.1f MB)", path.name, path.stat().st_size / 1024 / 1024)
        return path

    def progress(d: dict) -> None:
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "").strip()
            speed = d.get("_speed_str", "").strip()
            eta = d.get("_eta_str", "").strip()
            print(f"\r  {pct:>6}  {speed:>12}  ETA {eta}   ", end="", flush=True)
        elif d["status"] == "finished":
            print()

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(cache_dir / "%(id)s.%(ext)s"),
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
        "progress_hooks": [progress],
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not path.exists():
        raise FileNotFoundError(f"Expected {path} — check ffmpeg is in PATH")

    save_sidecar(cache_dir, info)
    return path
