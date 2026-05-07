"""raumtube-scpd — fetch SCPD XMLs and save action signatures."""

import argparse
import json
from pathlib import Path

from cprima_raumtube._compat import ensure_utf8_stdout
from cprima_raumtube.config import load_config
from cprima_raumtube.scpd.fetch import PRIORITY, fetch_all, format_sig


def main() -> None:
    ensure_utf8_stdout()

    cfg = load_config()

    ap = argparse.ArgumentParser(
        description="Fetch SCPD action signatures from discovered devices."
    )
    ap.add_argument("--devices-file", default=str(cfg.devices_file))
    ap.add_argument("--output", default=str(cfg.scpd_file))
    args = ap.parse_args()

    with open(args.devices_file, encoding="utf-8") as f:
        registry = json.load(f)

    output = fetch_all(registry)

    for info in output.values():
        svc_type = info["service_type"]
        svc_short = svc_type.split(":")[-2]
        actions = info["actions"]
        state_vars = info["state_variables"]
        want = PRIORITY.get(svc_type, [])

        print(f"\n{'=' * 60}")
        print(f"Service:  {svc_short}")
        print(f"Type:     {svc_type}")
        print(f"SCPD:     {info['scpd_url']}")

        if want:
            print("\n  --- Priority actions ---")
            for aname in want:
                if aname in actions:
                    print(format_sig(aname, actions[aname], state_vars))
                else:
                    print(f"  {aname}: NOT FOUND")

        other = [a for a in actions if a not in want]
        if other:
            print("\n  --- Other actions ---")
            for aname in sorted(other):
                print(format_sig(aname, actions[aname], state_vars))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n\n{len(output)} service SCPDs written to {out}")
