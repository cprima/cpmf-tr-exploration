# ADR-001: Zone Renderer and Physical Device are Distinct Entities

Status: Accepted
Date: 2026-05-07

## Context

Raumfeld/Teufel multiroom audio systems use an **Expand hub** as a network controller.
Physical speakers (One S, Cinebar Lux, etc.) connect to the hub over a proprietary RF or Ethernet protocol.
The hub discovers physical speakers and **synthesizes a virtual UPnP renderer** for each zone.

This means:
- The UDN of a `ZoneRenderer` (the SOAP control endpoint) is **not** the same as the UDN of the physical hardware.
- The IP address of the control endpoint belongs to the **hub**, not the speaker.
- Physical speakers do not directly expose SOAP/AVTransport services to the LAN.

During SSDP discovery, both physical devices and virtual zone renderers appear as separate UPnP devices.
Without an explicit split in the model, callers would conflate "the thing I send SOAP to" with "the hardware making sound."

## Decision

Maintain two distinct model entities:

| Entity | Represents | Identified by |
|---|---|---|
| `PhysicalDevice` | Real hardware on the LAN | `udn`, `ip`, `role` (hub/speaker/soundbar) |
| `ZoneRenderer` | Virtual SOAP endpoint on the hub | `udn`, `location_url`, AVTransport control URL |

`Zone.renderer_udn` points to a `ZoneRenderer`, never to a `PhysicalDevice`.
`TopologyAggregate` holds both in separate dicts (`physical_devices`, `zone_renderers`).

## Consequences

- Callers always address playback control through `ZoneRenderer`, regardless of which physical speaker is involved.
- Topology changes (speaker moved to different zone, group created) only affect `ZoneRenderer` associations — `PhysicalDevice` records remain stable.
- Capability probing (SCPD fetch, `GetProtocolInfo`) targets the `ZoneRenderer` URL, not the physical device.
- A `Room` may contain multiple physical devices but maps to at most one zone's renderer.
