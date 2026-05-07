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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from cprima_raumtube.didl import build_didl
from cprima_raumtube.model.aggregates import CommandRecord, CommandStatus, new_id
from cprima_raumtube.model.events import TransportEvent, VolumeEvent
from cprima_raumtube.model.media import QueueItemState
from cprima_raumtube.model.playback import (
    DesiredTransportState,
    PlaybackFailureKind,
    PlaybackSessionState,
    TransportStateName,
)
from cprima_raumtube.model.topology import CapabilityConfidence
from cprima_raumtube.soap import SoapFault

if TYPE_CHECKING:
    from collections.abc import Callable

    from cprima_raumtube.model.registry import Installation
    from cprima_raumtube.model.services import RendererPort
    from cprima_raumtube.services.queue_manager import QueueManager
    from cprima_raumtube.services.stream_manager import StreamManager

_log = logging.getLogger(__name__)

StopReason = Literal["natural_end", "manual_stop", "error", "skip"]


def _finish_command(
    record: CommandRecord,
    status: CommandStatus,
    *,
    soap_fault_code: str | None = None,
    soap_fault_description: str | None = None,
    network_error: str | None = None,
) -> None:
    record.status = status
    record.finished_at = datetime.now(UTC)
    if soap_fault_code is not None:
        record.soap_fault_code = soap_fault_code
    if soap_fault_description is not None:
        record.soap_fault_description = soap_fault_description
    if network_error is not None:
        record.network_error = network_error


class PlaybackManager:
    def __init__(
        self,
        installation: Installation,
        renderer: RendererPort,
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

        # Start stream session
        if mode == "cached_file":
            from pathlib import Path

            session = self._sm.start_cached(Path(source))
        elif mode == "direct_url":
            session = self._sm.start_direct(str(source))
        else:
            session = self._sm.start_live(str(source))

        session.media_item_id = media_item.id
        self._installation.state.stream_sessions[session.id] = session

        # Build DIDL metadata — broadcast and direct streams use audioBroadcast class
        live = mode in {"live_pipe", "direct_url"}
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
        queue.mark_current_resolved(session.id)
        queue.mark_current_playing()
        ps = self._installation.state.get_or_create_playback_session(zone_id)
        if not ps.is_active:
            ps.start()
        ps.current_item_id = qi.media_item_id
        ps.stream_session_id = session.id

        _log.info(
            "[play] zone=%s  %r  mode=%s  url=%s",
            zone_id,
            media_item.title,
            mode,
            session.public_url,
        )

    def stop(self, zone_id: str, reason: StopReason = "manual_stop") -> None:
        """Stop renderer, close stream session, update PlaybackSession.

        Best-effort: local model cleanup proceeds even if the SOAP call fails,
        because abandoning a playback session is always the right local decision.
        """
        ps = self._installation.state.get_playback_session(zone_id)

        # Record desired intent
        zone_state = self._installation.state.get_or_create_zone_state(zone_id)
        zone_state.desired = DesiredTransportState(target_state=TransportStateName.STOPPED)

        # Audit record
        record = CommandRecord(
            id=new_id(),
            action="Stop",
            target_udn=self._renderer.udn,
            zone_id=zone_id,  # type: ignore[arg-type]
            status=CommandStatus.RUNNING,
        )
        self._installation.state.command_log.append(record)

        # SOAP call — split exception handling; proceed with local cleanup regardless
        old_state = (
            zone_state.transport.state if zone_state.transport else TransportStateName.PLAYING
        )
        soap_ok = False
        try:
            self._renderer.stop()
            soap_ok = True
        except SoapFault as exc:
            _finish_command(
                record,
                CommandStatus.FAILED,
                soap_fault_code=str(exc.code) if exc.code is not None else None,
                soap_fault_description=str(exc),
            )
            _log.warning("[play] renderer stop SOAP fault: %s", exc)
        except TimeoutError as exc:
            _finish_command(record, CommandStatus.TIMED_OUT, network_error=str(exc))
            _log.warning("[play] renderer stop timeout: %s", exc)
        except OSError as exc:
            _finish_command(record, CommandStatus.FAILED, network_error=str(exc))
            _log.warning("[play] renderer stop OS error: %s", exc)

        if soap_ok:
            _finish_command(record, CommandStatus.SUCCEEDED)

        # Local cleanup unconditionally — model must reflect abandoned intent
        if ps is not None:
            if ps.stream_session_id:
                self._sm.stop(ps.stream_session_id)
                ps.stream_session_id = None
            if ps.is_active:
                ps.stop()

        # Mark current queue item as played on natural end
        queue = self._installation.state.get_or_create_queue(zone_id)
        qi = queue.current_item
        if qi is not None and qi.state == QueueItemState.PLAYING and reason == "natural_end":
            queue.mark_current_played()

        if soap_ok:
            zone_state.updated_at = datetime.now(UTC)
            self._installation.state.emit(
                TransportEvent(
                    zone_id=zone_id,  # type: ignore[arg-type]
                    new_state=TransportStateName.STOPPED,
                    old_state=old_state,
                )
            )

        _log.info("[play] zone=%s stopped  reason=%s", zone_id, reason)

    def pause(self, zone_id: str) -> None:
        # 1. Session guard
        ps = self._installation.state.get_playback_session(zone_id)
        if ps is None or ps.state != PlaybackSessionState.PLAYING:
            raise ValueError(f"pause requires PLAYING session, zone={zone_id!r}")

        # 2. Capability check — UNTESTED confidence means unprobed: do not block
        zr = self._installation.inventory.zone_renderers.get(self._renderer.udn)
        if zr is not None and zr.profile is not None:
            pause_cap = zr.profile.playback.pause
            if pause_cap.confidence != CapabilityConfidence.UNTESTED and not pause_cap.supported:
                raise ValueError(
                    f"Renderer {self._renderer.udn!r} does not support pause"
                    f" (source={pause_cap.source}, confidence={pause_cap.confidence})"
                )

        # 3. Record desired intent
        zone_state = self._installation.state.get_or_create_zone_state(zone_id)
        zone_state.desired = DesiredTransportState(target_state=TransportStateName.PAUSED_PLAYBACK)

        # 4. Audit record — RUNNING marks the attempt as in-flight
        record = CommandRecord(
            id=new_id(),
            action="Pause",
            target_udn=self._renderer.udn,
            zone_id=zone_id,  # type: ignore[arg-type]
            status=CommandStatus.RUNNING,
        )
        self._installation.state.command_log.append(record)

        # 5. SOAP call — split exception handling: known failures stay in ERROR state;
        #    unexpected exceptions re-raise so they are not silently swallowed.
        old_state = zone_state.transport.state if zone_state.transport else TransportStateName.PLAYING
        try:
            self._renderer.pause()
        except SoapFault as exc:
            _finish_command(
                record,
                CommandStatus.FAILED,
                soap_fault_code=str(exc.code) if exc.code is not None else None,
                soap_fault_description=str(exc),
            )
            ps.fail(f"SOAP fault: {exc}", PlaybackFailureKind.DEVICE_REJECTED)
            return
        except TimeoutError as exc:
            _finish_command(record, CommandStatus.TIMED_OUT, network_error=str(exc))
            ps.fail(str(exc), PlaybackFailureKind.TIMEOUT)
            return
        except OSError as exc:
            _finish_command(record, CommandStatus.FAILED, network_error=str(exc))
            ps.fail(str(exc), PlaybackFailureKind.NETWORK)
            return

        # 6. Success path
        _finish_command(record, CommandStatus.SUCCEEDED)
        ps.pause()
        zone_state.updated_at = datetime.now(UTC)
        self._installation.state.emit(
            TransportEvent(
                zone_id=zone_id,  # type: ignore[arg-type]
                new_state=TransportStateName.PAUSED_PLAYBACK,
                old_state=old_state,
            )
        )

    def resume(self, zone_id: str) -> None:
        # 1. Session guard
        ps = self._installation.state.get_playback_session(zone_id)
        if ps is None or ps.state != PlaybackSessionState.PAUSED:
            raise ValueError(f"resume requires PAUSED session, zone={zone_id!r}")

        # 2. Record desired intent
        zone_state = self._installation.state.get_or_create_zone_state(zone_id)
        zone_state.desired = DesiredTransportState(target_state=TransportStateName.PLAYING)

        # 3. Audit record
        record = CommandRecord(
            id=new_id(),
            action="Play",
            target_udn=self._renderer.udn,
            zone_id=zone_id,  # type: ignore[arg-type]
            status=CommandStatus.RUNNING,
        )
        self._installation.state.command_log.append(record)

        # 4. SOAP call
        old_state = (
            zone_state.transport.state if zone_state.transport else TransportStateName.PAUSED_PLAYBACK
        )
        try:
            self._renderer.play()
        except SoapFault as exc:
            _finish_command(
                record,
                CommandStatus.FAILED,
                soap_fault_code=str(exc.code) if exc.code is not None else None,
                soap_fault_description=str(exc),
            )
            ps.fail(f"SOAP fault: {exc}", PlaybackFailureKind.DEVICE_REJECTED)
            return
        except TimeoutError as exc:
            _finish_command(record, CommandStatus.TIMED_OUT, network_error=str(exc))
            ps.fail(str(exc), PlaybackFailureKind.TIMEOUT)
            return
        except OSError as exc:
            _finish_command(record, CommandStatus.FAILED, network_error=str(exc))
            ps.fail(str(exc), PlaybackFailureKind.NETWORK)
            return

        # 5. Success path
        _finish_command(record, CommandStatus.SUCCEEDED)
        ps.resume()
        zone_state.updated_at = datetime.now(UTC)
        self._installation.state.emit(
            TransportEvent(
                zone_id=zone_id,  # type: ignore[arg-type]
                new_state=TransportStateName.PLAYING,
                old_state=old_state,
            )
        )

    def set_volume(self, zone_id: str, level: int) -> None:
        # 1. Guard: valid range
        if not 0 <= level <= 100:
            raise ValueError(f"Volume must be 0-100, got {level}")

        # 2. Capability check — UNTESTED means unprobed: do not block
        zr = self._installation.inventory.zone_renderers.get(self._renderer.udn)
        if zr is not None and zr.profile is not None:
            vol_cap = zr.profile.audio.volume
            if vol_cap.confidence != CapabilityConfidence.UNTESTED and not vol_cap.supported:
                raise ValueError(
                    f"Renderer {self._renderer.udn!r} does not support volume control"
                    f" (source={vol_cap.source}, confidence={vol_cap.confidence})"
                )

        # 3. Audit record
        record = CommandRecord(
            id=new_id(),
            action="SetVolume",
            target_udn=self._renderer.udn,
            zone_id=zone_id,  # type: ignore[arg-type]
            status=CommandStatus.RUNNING,
            details={"level": str(level)},
        )
        self._installation.state.command_log.append(record)

        # 4. SOAP call
        zone_state = self._installation.state.get_or_create_zone_state(zone_id)
        old_volume = zone_state.rendering.volume.get("Master")
        try:
            self._renderer.set_volume(level)
        except SoapFault as exc:
            _finish_command(
                record,
                CommandStatus.FAILED,
                soap_fault_code=str(exc.code) if exc.code is not None else None,
                soap_fault_description=str(exc),
            )
            return
        except TimeoutError as exc:
            _finish_command(record, CommandStatus.TIMED_OUT, network_error=str(exc))
            return
        except OSError as exc:
            _finish_command(record, CommandStatus.FAILED, network_error=str(exc))
            return

        # 5. Success path — update observed rendering state and emit event
        _finish_command(record, CommandStatus.SUCCEEDED)
        zone_state.rendering.volume["Master"] = level
        zone_state.updated_at = datetime.now(UTC)
        self._installation.state.emit(
            VolumeEvent(
                zone_id=zone_id,  # type: ignore[arg-type]
                new_volume=level,
                old_volume=old_volume,
            )
        )

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
