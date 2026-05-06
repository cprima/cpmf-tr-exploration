# Protocol Overview: UPnP in cprima-raumtube

A quick-reference for how the UPnP stack is used in this project.
This is not a UPnP tutorial — it describes only the layers actually exercised here.

---

## The Three-Layer Stack

```
SSDP  ──────────────────────────────────────────  discovery/ssdp.py
  │   UDP multicast → device location URL
  ▼
SCPD  ──────────────────────────────────────────  scpd/fetch.py
  │   HTTP GET device description XML
  │   HTTP GET service SCPD XML → actions, state variables
  ▼
SOAP  ──────────────────────────────────────────  soap.py, upnp/transport.py
      HTTP POST SOAP envelope → action + response
```

---

## Layer 1: SSDP (Discovery)

- **Purpose:** Find devices on the LAN without prior knowledge of their IP.
- **Transport:** UDP multicast to `239.255.255.250:1900`.
- **Request:** `M-SEARCH` (see `docs/protocol/ssdp-discovery.md`).
- **Response:** Each device replies with its `LOCATION` URL (the device description XML).
- **Used by:** `discovery/ssdp.py` → `discover()`, `build_registry()`.

---

## Layer 2: SCPD (Service Description)

- **Purpose:** Enumerate the SOAP actions and state variables a device supports.
- **Transport:** HTTP GET.
- **Device description XML** (`/device.xml`): lists UDN, friendly name, and `<serviceList>`.
- **Service SCPD XML** (`/AVTransport/scpd.xml` etc.): lists `<actionList>` and `<stateTable>`.
- **Used by:** `scpd/fetch.py` → `fetch_all()`, `parse_scpd()` → `RendererCapabilities`.

Key services on Raumfeld renderers:

| Service | URN | Purpose |
|---|---|---|
| AVTransport | `urn:schemas-upnp-org:service:AVTransport:1` | Play, Stop, Seek, queue |
| RenderingControl | `urn:schemas-upnp-org:service:RenderingControl:1` | Volume, mute |
| ConnectionManager | `urn:schemas-upnp-org:service:ConnectionManager:1` | Protocol info, MIME types |

---

## Layer 3: SOAP (Control)

- **Purpose:** Invoke an action on a device service.
- **Transport:** HTTP POST to the service's `controlURL`.
- **Envelope format:**

```xml
<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
    </u:Play>
  </s:Body>
</s:Envelope>
```

- **Response:** Same structure with `<u:PlayResponse>` containing output arguments.
- **Fault:** `<s:Fault>` with `faultstring`, UPnP error code, error description.
- **Used by:** `soap.soap_call()` (generic), `upnp/transport.py` (domain-aware wrapper).

---

## InstanceID

All Raumfeld AVTransport and RenderingControl actions require `InstanceID = "0"`.
This is the standard single-instance value. Multi-instance renderers (uncommon) use other values.

---

## Eventing (not implemented)

UPnP also supports GENA (General Event Notification Architecture) for push-based state updates.
Devices send `NOTIFY` HTTP messages to a subscribed callback URL when state changes.

`cprima-raumtube` does not implement eventing — it uses polling via `GetTransportInfo` instead.
Eventing would allow reactive UI updates without polling; it is a future capability.
