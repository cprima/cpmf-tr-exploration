"""Runtime configuration with three-tier resolution: CLI flag > env var > config file > default."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    source_ip: str = ""
    local_ip: str = ""
    port: int = 8080
    timeout: int = 6
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "raumtube")
    devices_file: Path = field(default_factory=lambda: Path.cwd() / "data" / "devices.json")
    scpd_file: Path = field(default_factory=lambda: Path.cwd() / "data" / "scpd_actions.json")


def load_config(config_file: Path | None = None) -> Config:
    """Load config from file (optional) then overlay env vars."""
    cfg: dict = {}

    path = config_file or Path.home() / ".config" / "raumtube" / "config.toml"
    if path.exists():
        with open(path, "rb") as f:
            cfg = tomllib.load(f)

    def _env(key: str, default: str = "") -> str:
        return os.environ.get(f"RAUMTUBE_{key.upper()}", cfg.get(key, default))

    return Config(
        source_ip=_env("source_ip"),
        local_ip=_env("local_ip"),
        port=int(_env("port", "8080")),
        timeout=int(_env("timeout", "6")),
        cache_dir=Path(_env("cache_dir", str(Path.home() / ".cache" / "raumtube"))),
        devices_file=Path(_env("devices_file", str(Path.cwd() / "data" / "devices.json"))),
        scpd_file=Path(_env("scpd_file", str(Path.cwd() / "data" / "scpd_actions.json"))),
    )
