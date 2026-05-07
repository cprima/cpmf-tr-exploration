"""FakeRenderer — controllable stand-in satisfying RendererPort.

Designed for use in tests and integration harnesses.  All failure points
are injectable per-instance so tests can exercise error paths without mocking.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cprima_raumtube.model.ids import RendererUdn


@dataclass
class FakeRenderer:
    """In-memory renderer that satisfies RendererPort structurally.

    pause_raises     if set, pause() raises this exception (tests SoapFault, OSError, …)
    pause_call_count incremented on every pause() call regardless of outcome
    _state           internal transport state string
    """

    udn: RendererUdn = field(default_factory=lambda: RendererUdn("fake-udn-1"))
    pause_raises: Exception | None = None
    pause_call_count: int = field(default=0, init=False)
    _state: str = field(default="PLAYING", init=False, repr=False)

    def pause(self) -> None:
        self.pause_call_count += 1
        if self.pause_raises is not None:
            raise self.pause_raises
        self._state = "PAUSED_PLAYBACK"

    def play(self, _speed: str = "1") -> None:
        self._state = "PLAYING"

    def stop(self) -> None:
        self._state = "STOPPED"

    def set_uri(self, _uri: str, _metadata: str) -> None:
        pass

    def get_state(self) -> str:
        return self._state

    def get_volume(self) -> int:
        return 50

    def set_volume(self, _level: int) -> None:
        pass
