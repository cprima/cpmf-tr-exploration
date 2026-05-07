"""PlaybackManager — SOAP playback control for a single zone.

Owns:
- play_current / stop / pause / resume
- advance_and_play (skip + play)
- run_autoplay_loop (blocking polling loop)

Delegates HTTP session lifecycle to StreamManager.
Delegates queue navigation to QueueManager.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Literal

from cprima_raumtube.didl import build_didl
from cprima_raumtube.model.media import QueueItemState
from cprima_raumtube.model.playback import PlaybackSessionState

if TYPE_CHECKING:
    from collections.abc import Callable

    from cprima_raumtube.model.registry import Installation
    from cprima_raumtube.services.queue_manager import QueueManager
    from cprima_raumtube.services.stream_manager import StreamManager
    from cprima_raumtube.upnp.transport import Renderer

_log = logging.getLogger(__name__)

StopReason = Literal["natural_end", "manual_stop", "error", "skip"]


class PlaybackManager:
    def __init__(
        self,
        installation: Installation,
        renderer: Renderer,
        queue_manager: QueueManager,
        stream_manager: StreamManager,
    ) -> None:
        self._installation = installation
        self._renderer = renderer
        self._qm = queue_manager
        self._sm = stream_manager

    # ── Core playback ─────────────────────────────────────────────────────────

    def play_current(self, zone_id: str) -> None:
        """Resolve current queue item → start stream → set_uri + play."""
        queue = self._installation.state.get_or_create_queue(zone_id)
        qi = queue.current_item
        if qi is None:
            raise RuntimeError(f"Queue for zone {zone_id!r} is empty or has no current item")

        media_item = self._installation.library.find_item(qi.media_item_id)
        if media_item is None:
            raise KeyError(f"MediaItem {qi.media_item_id!r} not in library")

        # Resolve to stream source
        source, mode = self._qm.resolve_item(qi)

        # Start HTTP session
        if mode == "cached_file":
            from pathlib import Path

            session = self._sm.start_cached(Path(source))
        else:
            session = self._sm.start_live(str(source))

        session.media_item_id = media_item.id
        self._installation.state.stream_sessions[session.id] = session

        # Build DIDL metadata
        live = mode == "live_pipe"
        didl = build_didl(
            uri=session.public_url,
            title=media_item.title,
            live=live,
            thumbnail=media_item.thumbnail_uri or "",
            duration=media_item.duration_seconds or 0,
        )

        # SOAP control
        self._renderer.set_uri(session.public_url, didl)
        self._renderer.play()

        # Update model state
        ps = self._installation.state.get_or_create_playback_session(zone_id)
        ps.state = PlaybackSessionState.STARTING
        ps.current_item_id = qi.media_item_id
        ps.stream_session_id = session.id
        qi.state = QueueItemState.PLAYING
        qi.resolved_stream_id = session.id

        _log.info(
            "[play] zone=%s  %r  mode=%s  url=%s",
            zone_id,
            media_item.title,
            mode,
            session.public_url,
        )

    def stop(self, zone_id: str, reason: StopReason = "manual_stop") -> None:
        """Stop renderer, close stream session, update PlaybackSession."""
        try:
            self._renderer.stop()
        except Exception as exc:
            _log.warning("[play] renderer stop error: %s", exc)

        ps = self._installation.state.get_playback_session(zone_id)
        if ps is not None:
            if ps.stream_session_id:
                self._sm.stop(ps.stream_session_id)
                ps.stream_session_id = None
            ps.state = PlaybackSessionState.STOPPED

        # Mark current queue item as played/failed
        queue = self._installation.state.get_or_create_queue(zone_id)
        qi = queue.current_item
        if qi is not None and qi.state == QueueItemState.PLAYING:
            qi.state = QueueItemState.PLAYED if reason == "natural_end" else qi.state

        _log.info("[play] zone=%s stopped  reason=%s", zone_id, reason)

    def pause(self, zone_id: str) -> None:
        self._renderer.pause()
        ps = self._installation.state.get_playback_session(zone_id)
        if ps:
            ps.state = PlaybackSessionState.PAUSED

    def resume(self, zone_id: str) -> None:
        self._renderer.play()
        ps = self._installation.state.get_playback_session(zone_id)
        if ps:
            ps.state = PlaybackSessionState.PLAYING

    def advance_and_play(self, zone_id: str) -> bool:
        """stop(skip) → skip_next → play_current. Returns True if started, False if exhausted."""
        self.stop(zone_id, reason="skip")
        next_item = self._qm.skip_next(zone_id)
        if next_item is None:
            return False
        self.play_current(zone_id)
        return True

    # ── Autoplay loop ─────────────────────────────────────────────────────────

    def run_autoplay_loop(
        self,
        zone_id: str,
        poll_interval: float = 2.0,
        on_state_change: Callable[[str, StopReason | None], None] | None = None,
    ) -> None:
        """Blocking polling loop. Advances queue on natural track end.

        Distinguishes natural end from manual stop by tracking the URI last
        seen in PLAYING state. When STOPPED with the same URI → natural end.
        When STOPPED with a different URI → external/manual stop → exit.
        """
        queue = self._installation.state.get_or_create_queue(zone_id)
        last_playing_uri: str | None = None
        last_state: str = ""

        _log.info("[autoplay] loop started  zone=%s", zone_id)
        try:
            while True:
                time.sleep(poll_interval)
                try:
                    state = self._renderer.get_state()
                except Exception as exc:
                    _log.warning("[autoplay] get_state error: %s", exc)
                    continue

                if state != last_state:
                    _log.info("[autoplay] state: %s → %s", last_state, state)
                    last_state = state

                if state == "PLAYING":
                    try:
                        info = self._renderer.get_media_info()
                        last_playing_uri = info.get("CurrentURI", last_playing_uri)
                    except Exception:
                        pass
                    if on_state_change:
                        on_state_change(last_playing_uri or "", None)

                elif state == "STOPPED":
                    try:
                        info = self._renderer.get_media_info()
                        current_uri = info.get("CurrentURI", "")
                    except Exception:
                        current_uri = ""

                    natural_end = last_playing_uri is not None and current_uri == last_playing_uri

                    if natural_end and queue.has_next:
                        _log.info("[autoplay] natural end → advancing")
                        if on_state_change:
                            on_state_change(last_playing_uri or "", "natural_end")
                        self.advance_and_play(zone_id)
                        last_playing_uri = None

                    elif natural_end and not queue.has_next:
                        _log.info(
                            "[autoplay] queue exhausted  behavior=%s", queue.queue_end_behavior
                        )
                        if on_state_change:
                            on_state_change(last_playing_uri or "", "natural_end")
                        # Only "stop" implemented for now
                        self.stop(zone_id, reason="natural_end")
                        break

                    else:
                        # URI mismatch → manual stop or external control
                        _log.info("[autoplay] external stop detected → exiting loop")
                        if on_state_change:
                            on_state_change(current_uri, "manual_stop")
                        break

        except KeyboardInterrupt:
            _log.info("[autoplay] interrupted by user")
            self.stop(zone_id, reason="manual_stop")
        finally:
            _log.info("[autoplay] loop exited  zone=%s", zone_id)
