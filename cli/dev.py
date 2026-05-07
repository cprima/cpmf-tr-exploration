"""raumtube-dev — exploratory developer commands for manual testing.

Subcommands
-----------
pause   Send Pause to a zone renderer and show the audit result.
"""

from __future__ import annotations

import argparse
import sys

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.devices import get_zone
from cprima_raumtube.model.ids import ZoneId
from cprima_raumtube.model.playback import PlaybackSessionState
from cprima_raumtube.model.registry import Installation
from cprima_raumtube.services.playback_manager import PlaybackManager
from cprima_raumtube.upnp.transport import Renderer


def _cmd_pause(args: argparse.Namespace) -> None:
    zone = get_zone(args.zone, args.devices_file)
    zone_id = ZoneId(zone["udn"])
    renderer = Renderer.from_zone(zone)

    print(f"zone={args.zone!r}  renderer={zone_id}  endpoint={zone.get('avt_control', '?')}")

    installation = Installation.ephemeral()

    # Bootstrap a PLAYING session so pause() has something to transition
    ps = installation.state.get_or_create_playback_session(zone_id)
    ps.start()
    ps.mark_playing()

    pm = PlaybackManager(
        installation=installation,
        renderer=renderer,
        queue_manager=None,  # type: ignore[arg-type]
        stream_manager=None,  # type: ignore[arg-type]
    )

    try:
        pm.pause(zone_id)
    except Exception as exc:
        print(f"ERROR  {exc}", file=sys.stderr)
        sys.exit(1)

    record = installation.state.command_log[-1]
    print(f"SOAP Pause → {record.status.upper()}")

    ps_after = installation.state.get_playback_session(zone_id)
    session_state = ps_after.state if ps_after else "?"
    events = installation.state.events_for_zone(zone_id)
    observed = events[-1].new_state if events else "?"  # type: ignore[union-attr]
    print(f"session={session_state}  observed={observed}")

    if ps_after and ps_after.state != PlaybackSessionState.PAUSED:
        sys.exit(1)


def main() -> None:
    ensure_utf8_stdout()
    cfg = load_config()

    ap = argparse.ArgumentParser(description="Developer / exploratory commands for raumtube.")
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    sub = ap.add_subparsers(dest="command", required=True)

    pause_p = sub.add_parser("pause", help="Send Pause to a zone renderer")
    pause_p.add_argument("--zone", default="HomeOffice", help="Zone friendly name or UDN")

    args = ap.parse_args()

    if args.command == "pause":
        _cmd_pause(args)
