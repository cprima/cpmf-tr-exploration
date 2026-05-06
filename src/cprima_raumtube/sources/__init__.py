"""AudioSource Protocol — implemented by any pluggable audio backend."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioSource(Protocol):
    """Minimal contract: resolve a URL to a streamable audio URL."""

    def resolve(self, url: str) -> str:
        """Return a direct audio URL ready for the renderer."""
        ...
