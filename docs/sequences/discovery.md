# Sequence: SSDP Discovery

This diagram covers device discovery from M-SEARCH multicast through to a populated `TopologyAggregate`.

---

## Sequence Diagram

```mermaid
sequenceDiagram
    actor CLI as cli/discover.py
    participant SSDP as discovery/ssdp.py
    participant Net as LAN (multicast 239.255.255.250:1900)
    participant Hub as Raumfeld Expand Hub
    participant SCPD as scpd/fetch.py
    participant Topo as TopologyAggregate

    CLI->>SSDP: await discover(source_ip, timeout=6)

    SSDP->>Net: M-SEARCH * HTTP/1.1\nMX: 3\nST: ssdp:all
    Note over Net: Multicast to 239.255.255.250:1900

    Hub-->>SSDP: HTTP/1.1 200 OK\nLOCATION: http://10.38.20.100:49152/device.xml\nSERVER: ... GUPnP/...
    Hub-->>SSDP: (multiple responses — one per virtual renderer)

    Note over SSDP: Filter: keep only responses with "GUPnP" in SERVER header
    Note over SSDP: Deduplicate by LOCATION URL

    SSDP->>Hub: GET http://10.38.20.100:49152/device.xml
    Hub-->>SSDP: device description XML\n(UDN, friendlyName, serviceList)

    SSDP->>SSDP: build_registry(devices)
    Note over SSDP: Extract AVTransport, RenderingControl,\nConnectionManager control URLs

    SSDP-->>CLI: list[dict]  (one entry per discovered renderer)

    CLI->>Topo: register_device(PhysicalDevice) for each hub/speaker
    CLI->>Topo: register_zone_renderer(ZoneRenderer) for each virtual renderer

    opt capability probing
        CLI->>SCPD: fetch_all(registry)
        SCPD->>Hub: GET scpd_url (AVTransport SCPD)
        Hub-->>SCPD: SCPD XML
        SCPD->>SCPD: parse_scpd(root) → actions, state_variables
        SCPD->>Topo: add_snapshot(ProtocolSnapshot)
        SCPD-->>CLI: RendererCapabilities per renderer
    end

    CLI-->>CLI: save data/devices.json (optional)
```

---

## Key Points

- Discovery binds to `NetworkProfile.effective_source_ip` for the SSDP socket (important on Windows for correct multicast binding).
- The GUPnP filter limits responses to the Raumfeld/Teufel device stack; third-party UPnP devices on the LAN are ignored.
- Deduplication is by `LOCATION` URL — the hub sends one response per virtual renderer, all at the same host IP.
- `build_registry()` extracts control URLs from the device XML's `<serviceList>` and returns structured dicts.
- SCPD fetch is optional at discovery time; capability probing can be deferred to first use of a renderer.
- `ProtocolSnapshot` stores raw SCPD XML for offline analysis and debugging (see `model/protocol.py`).
- `data/devices.json` is gitignored; it is the persistent cache of the last discovery result.
