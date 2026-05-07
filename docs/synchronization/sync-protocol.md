# Raumfeld Multi-Room Synchronization Protocol

Source: binary string analysis of firmware 2.21.0 (`renderer`, `stream-relay`) and SCPD XML from `renderer/xml/avtransport.xml`. See `docs/dsp/audio-pipeline.md` §4 for the DSP-side `timestretcher` implementation.

---

## 1. Design Principle

Raumfeld uses **wall-clock-anchored synchronization**: all renderers in a zone are given a shared future timestamp and start their DAC output at exactly that moment. Continuous rate adaptation via a `timestretcher` DSP module keeps them locked to the wall clock for the duration of playback.

The Android/iOS app is purely the control plane. It sends standard UPnP `SetAVTransportURI` + `Play` to the zone's virtual renderer (`stream-relay`). The sync protocol runs entirely within the device firmware, invisible to the app.

---

## 2. Components

| Component | Role |
|---|---|
| `timeserver` | Zone host service; NTP-synchronized wall clock reference |
| `stream-relay` | Zone virtual renderer; sync coordinator |
| `renderer` | Per-device physical renderer; receives and executes sync commands |
| `timestretcher` | DSP module inside `renderer`; continuous rate adaptation |

---

## 3. Protocol Sequence

```
Control app
  │
  │  SetAVTransportURI(zone-relay-url, metadata)
  │  Play()
  ▼
stream-relay
  │
  ├── ZoneObserverSetNextAndWaitForConnect
  │     Waits until all zone members are connected and ready
  │
  ├── Zone::pickNextStartTriggerTime()
  │     Selects a future wall-clock timestamp T₀
  │     Must be far enough ahead for all renderers to buffer audio
  │
  ├── For each renderer in zone:
  │     SetNextStartTriggerTime(
  │       InstanceID=0,
  │       TimeService=<timeserver-UDN>,
  │       StartTime=T₀
  │     )
  │
  └── Zone::handleRoomStateChanges()
        Monitors RoomStates JSON for per-room acknowledgement

Each renderer (concurrent):
  │
  ├── Resolves TimeService UDN → timeserver URL
  ├── Begins decoding and buffering audio
  ├── Polls wall clock via clock_gettime() until T₀
  └── Starts DAC output at T₀
        AudioLoop continuously compares clock_gettime() against expected
        playback position and feeds correction into timestretcher
```

---

## 4. UPnP Action: `SetNextStartTriggerTime`

Defined in `renderer/xml/avtransport.xml`. Not part of the UPnP AV standard.

```xml
<action>
  <name>SetNextStartTriggerTime</name>
  <argumentList>
    <argument>
      <name>InstanceID</name>
      <direction>in</direction>
      <relatedStateVariable>A_ARG_TYPE_InstanceID</relatedStateVariable>
    </argument>
    <argument>
      <name>TimeService</name>
      <direction>in</direction>
      <relatedStateVariable>A_ARG_TYPE_WallClockService</relatedStateVariable>
    </argument>
    <argument>
      <name>StartTime</name>
      <direction>in</direction>
      <relatedStateVariable>A_ARG_TYPE_WallClockTime</relatedStateVariable>
    </argument>
  </argumentList>
</action>
```

`TimeService` is a UDN reference to the zone host's `timeserver` device. `StartTime` is an absolute wall-clock timestamp in a format derived from the timeserver protocol.

---

## 5. Continuous Synchronization

After the scheduled start, the renderer `AudioLoop` maintains sync by:

1. Sampling `clock_gettime(CLOCK_REALTIME)` at each output write
2. Computing the expected playback position from the wall clock and elapsed time since T₀
3. Comparing against the actual decoded sample position
4. Signalling the `timestretcher` to increase or decrease playback rate to close the gap

Log strings in `renderer` binary:
```
AudioLoop: OUT OF SYNC, we are lagging behind the system clock (…)
AudioLoop: OUT OF SYNC, we are running ahead of the system clock (…)
```

The `hw_delay_ms` parameter in `/etc/asound.conf` feeds the DAC hardware latency into the sync calculation, so the target is the wall clock at the moment of speaker output, not at the software write.

---

## 6. Zone State Variable: `RoomStates`

The `stream-relay` `TransportService` exposes `RoomStates` (type: string, non-evented) — a JSON blob encoding the playback state of each physical room in the zone. `stream-relay` monitors this to detect when a room falls out of sync or drops from the zone.

---

## 7. Zone-Level Transport Extensions

Beyond standard AVTransport, `stream-relay`'s `TransportService.xml` defines:

| Action | Purpose |
|---|---|
| `BendAVTransportURI` | Swap the URI without tearing down the active stream session; used for seamless zone handoff |
| `SetResourceForCurrentStream` | Replace the backing resource (e.g., switch to a cached copy) while the stream session stays alive |

These enable the zone host to redirect audio without the audible gap that `SetAVTransportURI` + `Stop` + `Play` would cause.

---

## 8. Relation to App Architecture

From APK analysis (`ZoneRendererBridge`, `ZoneBridgeStateMachine`, `UpnpActionsKt`):

- The app models multi-room as a **zone** with multiple rooms and players.
- For a virtual zone the app picks the first player as the service anchor.
- The app sends only standard `SetAVTransportURI` / `Play` / `Stop` / `Pause` to the zone's `stream-relay`.
- It monitors zone and renderer state via UPnP eventing and updates UI accordingly.
- **The sample-locking / device-to-device timing logic is entirely absent from the APK** — it lives in the firmware.
