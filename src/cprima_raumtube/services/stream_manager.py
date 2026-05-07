"""StreamManager — HTTP streaming session lifecycle.

PlaybackManager delegates here; never touches LiveStreamSession or
CachedStreamSession directly.  One active session per zone is the
current constraint (single-zone scope).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cprima_raumtube.model.aggregates import new_id
from cprima_raumtube.model.streaming import StreamSession, StreamSessionState

if TYPE_CHECKING:
    from pathlib import Path
from cprima_raumtube.streaming import CachedStreamSession, LiveStreamSession

_log = logging.getLogger(__name__)

_Impl = CachedStreamSession | LiveStreamSession | None


class StreamManager:
    def __init__(self, local_ip: str = "", port: int = 8080) -> None:
        self._local_ip = local_ip
        self._port = port
        # session_id → (model descriptor, implementation object or None for direct_url)
        self._sessions: dict[str, tuple[StreamSession, _Impl]] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def start_cached(self, file_path: Path) -> StreamSession:
        """Start a CachedStreamSession and return the model descriptor."""
        impl = CachedStreamSession(file_path, self._local_ip, self._port)
        impl.start()
        descriptor = StreamSession(
            id=new_id(),
            media_item_id="",  # filled in by caller
            mode="cached_file",
            public_url=impl.stream_url,
            content_type="audio/mpeg",
            seekable=True,
            range_supported=True,
            state=StreamSessionState.ACTIVE,
            local_path=str(file_path),
        )
        self._sessions[descriptor.id] = (descriptor, impl)
        _log.info(
            "[stream] cached session %s started  url=%s", descriptor.id, descriptor.public_url
        )
        return descriptor

    def start_live(self, source_url: str) -> StreamSession:
        """Start a LiveStreamSession (ffmpeg pipe) and return the model descriptor."""
        impl = LiveStreamSession(source_url, self._local_ip, self._port)
        impl.start()
        descriptor = StreamSession(
            id=new_id(),
            media_item_id="",  # filled in by caller
            mode="live_pipe",
            public_url=impl.stream_url,
            content_type="audio/mpeg",
            seekable=False,
            range_supported=False,
            state=StreamSessionState.ACTIVE,
        )
        self._sessions[descriptor.id] = (descriptor, impl)
        _log.info("[stream] live session %s started  url=%s", descriptor.id, descriptor.public_url)
        return descriptor

    def start_direct(self, source_url: str) -> StreamSession:
        """Direct URL — renderer fetches source_url itself; no local server started."""
        descriptor = StreamSession(
            id=new_id(),
            media_item_id="",  # filled in by caller
            mode="direct_url",
            public_url=source_url,
            content_type="audio/mpeg",
            seekable=False,
            range_supported=False,
            state=StreamSessionState.ACTIVE,
        )
        self._sessions[descriptor.id] = (descriptor, None)
        _log.info("[stream] direct session %s  url=%s", descriptor.id, descriptor.public_url)
        return descriptor

    def stop(self, session_id: str) -> None:
        """Stop and remove a session by ID."""
        entry = self._sessions.pop(session_id, None)
        if entry is None:
            return
        descriptor, impl = entry
        if impl is not None:
            try:
                impl.stop()
            except Exception as exc:
                _log.warning("[stream] error stopping session %s: %s", session_id, exc)
        descriptor.state = StreamSessionState.CLOSED
        _log.info("[stream] session %s closed", session_id)

    def stop_all(self) -> None:
        """Stop all active sessions (called on CLI exit)."""
        for session_id in list(self._sessions):
            self.stop(session_id)
