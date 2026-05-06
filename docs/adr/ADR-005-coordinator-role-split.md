# ADR-005: Transport, Clock, and Group Control May Live on Different UDNs

Status: Accepted
Date: 2026-05-07

## Context

In a Raumfeld multiroom group, synchronized playback requires three distinct control concerns:

1. **Transport control** — who accepts `SetAVTransportURI`, `Play`, `Stop`, `Seek`.
2. **Clock master** — who drives the synchronized audio clock across group members (gapless, in-sync playback).
3. **Group master** — who decides which physical renderers belong to the current group.

Naively, a caller might send `Play` to the same UDN that owns the group, or assume the group master
and transport controller are co-located. In practice, Raumfeld splits these across different virtual
renderer UDNs depending on zone configuration and group state.

Sending `SetAVTransportURI` to the wrong UDN silently succeeds at the SOAP level but produces no audio,
or only plays on one device in the group.

## Decision

`Zone` holds a `coordinators: list[Coordinator]` field. Each `Coordinator` has:
- `renderer_udn` — the UDN to address for this role
- `role` — one of `transport`, `clock_master`, `group_master`

`Zone.transport_coordinator` is a property that returns the `Coordinator` with `role="transport"`,
or `None` if not yet probed.

All playback SOAP calls (`SetAVTransportURI`, `Play`, `Stop`, `Pause`, `Seek`) must be directed to
the **transport coordinator's** `renderer_udn`, not to `Zone.renderer_udn` directly.

## Consequences

- `TopologyAggregate.get_renderer_for_zone()` returns the `ZoneRenderer` for `Zone.renderer_udn` (the primary renderer).
  Callers needing the transport coordinator must use `zone.transport_coordinator` explicitly.
- Coordinator assignments must be refreshed after group topology changes (`GroupTopologyEvent`).
- When no coordinator is probed (`zone.coordinators` is empty), fall back to `zone.renderer_udn`
  and treat it as the transport controller — this matches the single-zone (non-grouped) case.
- `group_master` and `clock_master` roles are reserved for future multiroom sync implementation;
  they are not yet used by the CLI.
