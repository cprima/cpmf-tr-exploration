"""Repository interfaces — abstract persistence contracts for the model layer.

These Protocol classes define how the application can persist and retrieve
Installation state. Implementations (in-memory, file-based, remote) live
outside the model layer and depend only on these interfaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from cprima_raumtube.model.registry import Installation


class InstallationRepository(Protocol):
    """Read/write access to persisted Installations."""

    def get(self, installation_id: str) -> Installation:
        """Retrieve an Installation by ID. Raises KeyError if not found."""
        ...

    def save(self, installation: Installation) -> None:
        """Persist an Installation (create or update)."""
        ...

    def list_ids(self) -> list[str]:
        """Return all known installation IDs."""
        ...

    def delete(self, installation_id: str) -> None:
        """Remove a persisted Installation. No-op if not found."""
        ...
