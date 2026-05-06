# Protocol: SSDP Discovery

SSDP (Simple Service Discovery Protocol) is used to locate UPnP devices on the local LAN.
Implementation: `cprima_raumtube.discovery.ssdp`.

---

## M-SEARCH Request

Sent as a UDP multicast to `239.255.255.250:1900`.

```
M-SEARCH * HTTP/1.1
HOST: 239.255.255.250:1900
MAN: "ssdp:discover"
MX: 3
ST: ssdp:all
```

| Field | Value | Notes |
|---|---|---|
| `HOST` | `239.255.255.250:1900` | UPnP multicast group |
| `MAN` | `"ssdp:discover"` | Required literal |
| `MX` | `3` | Maximum wait seconds before response |
| `ST` | `ssdp:all` | Search all device types |

The socket is bound to `NetworkProfile.effective_source_ip` (= `source_ip` or `local_ip`).
On Windows, binding to the correct interface IP is required for multicast to work.

---

## Response Format

Devices respond with HTTP/1.1 200 OK over UDP (unicast back to the requester).

```
HTTP/1.1 200 OK
CACHE-CONTROL: max-age=1800
DATE: ...
EXT:
LOCATION: http://10.38.20.100:49152/device.xml
SERVER: Linux/4.9 UPnP/1.0 GUPnP/1.2.3
ST: urn:schemas-upnp-org:device:MediaRenderer:1
USN: uuid:zone-homeoffice::urn:schemas-upnp-org:device:MediaRenderer:1
```

Key headers:

| Header | Purpose |
|---|---|
| `LOCATION` | URL of the device description XML — used for deduplication and SCPD fetch |
| `SERVER` | Used to filter for GUPnP devices (Raumfeld/Teufel stack) |
| `USN` | Unique Service Name — `uuid:<UDN>::<service-type>` |

---

## GUPnP Filter

Only responses with `"GUPnP"` in the `SERVER` header are kept.

**Rationale:** The LAN may contain other UPnP devices (smart TVs, NAS boxes, printers).
The Raumfeld/Teufel stack always reports `GUPnP` in its server string.
Filtering on this avoids attempting SOAP control of unrelated devices.

---

## Deduplication

The Expand hub sends **multiple responses** for a single M-SEARCH — one per virtual zone renderer,
plus one for the hub device itself. All share the same `LOCATION` base host.

Deduplication is performed by `LOCATION` URL: if two responses have the same `LOCATION`, only one is kept.

---

## Device Description Fetch

After dedup, `discover()` fetches each unique `LOCATION` URL to retrieve the device XML:

```xml
<device>
  <UDN>uuid:zone-homeoffice</UDN>
  <friendlyName>HomeOffice</friendlyName>
  <serviceList>
    <service>
      <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
      <controlURL>/TransportService/Control</controlURL>
      <SCPDURL>/TransportService/scpd.xml</SCPDURL>
      <eventSubURL>/TransportService/Event</eventSubURL>
    </service>
    ...
  </serviceList>
</device>
```

`build_registry(devices)` extracts control URLs for AVTransport, RenderingControl, and ConnectionManager.

---

## `build_registry()` Output Shape

Returns `list[dict]`, one entry per device:

```python
{
    "udn":           "uuid:zone-homeoffice",
    "friendly_name": "HomeOffice",
    "location":      "http://10.38.20.100:49152/device.xml",
    "avt_control":   "http://10.38.20.100:49935/TransportService/Control",
    "rc_control":    "http://10.38.20.100:49936/RenderingControl/Control",
    "cm_control":    "http://10.38.20.100:49937/ConnectionManager/Control",
    "avt_scpd":      "http://10.38.20.100:49152/TransportService/scpd.xml",
}
```

---

## Timeout Semantics

`NetworkProfile.discovery_timeout` (default: `6` seconds) sets how long `discover()` waits
for responses after sending M-SEARCH.

- Increase on slow or congested LANs.
- Decrease for faster CLI response when the device count is known.
- The Expand hub typically responds within 1–2 seconds on a local LAN.
