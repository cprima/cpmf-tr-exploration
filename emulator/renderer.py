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

    Each method has a matching `<method>_raises` slot and `<method>_call_count`
    so tests can assert exactly which SOAP actions were attempted.
    """

    udn: RendererUdn = field(default_factory=lambda: RendererUdn("fake-udn-1"))

    pause_raises: Exception | None = None
    play_raises: Exception | None = None
    stop_raises: Exception | None = None
    set_volume_raises: Exception | None = None

    pause_call_count: int = field(default=0, init=False)
    play_call_count: int = field(default=0, init=False)
    stop_call_count: int = field(default=0, init=False)
    set_volume_call_count: int = field(default=0, init=False)

    _state: str = field(default="PLAYING", init=False, repr=False)
    _volume: int = field(default=50, init=False, repr=False)

    def pause(self) -> None:
        self.pause_call_count += 1
        if self.pause_raises is not None:
            raise self.pause_raises
        self._state = "PAUSED_PLAYBACK"

    def play(self, _speed: str = "1") -> None:
        self.play_call_count += 1
        if self.play_raises is not None:
            raise self.play_raises
        self._state = "PLAYING"

    def stop(self) -> None:
        self.stop_call_count += 1
        if self.stop_raises is not None:
            raise self.stop_raises
        self._state = "STOPPED"

    def set_uri(self, _uri: str, _metadata: str) -> None:
        pass

    def get_state(self) -> str:
        return self._state

    def get_volume(self) -> int:
        return self._volume

    def set_volume(self, level: int) -> None:
        self.set_volume_call_count += 1
        if self.set_volume_raises is not None:
            raise self.set_volume_raises
        self._volume = level
