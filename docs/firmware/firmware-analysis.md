# Raumfeld Firmware Analysis

**Scope**: Static inspection of two official firmware images — filesystem layout, configuration, init scripts, service names, public binary strings, and protocol constants. Private keys are not extracted, signatures are not bypassed, firmware is not modified, proprietary code blobs are not published.

| Attribute | Expand 5 (hub) | One S / Cinebar Lux (speaker) |
|---|---|---|
| Model codes | `Raumfeld_5` | `Raumfeld_23` / `Raumfeld_27` |
| Firmware version | 2.17.4 | 2.21.0 |
| File size | 36 MB (XZ tar) | 32 MB (XZ tar) |
| SHA-256 | `f89bbc6…` | `7f123d2…` |
| Architecture | x86 (AMD Geode) | ARM (NXP i.MX7) |
| Linux kernel | 4.4.179 | 4.1.45 |
| Base system | Buildroot 2016.11.3 | Buildroot 2016.11.3 |
| libc | glibc 2.23 | glibc 2.23 |

---

## 1. Image Format

Both images are **XZ-compressed GNU tar archives** of a complete Linux root filesystem. The archive is downloaded from `https://raumfeld.updates.teufel.de/live/{sha256}` where the SHA-256 of the archive itself is the path component.

```
raumfeld_speaker_23_27_2.21.0.bin
  └── GNU tar, XZ compression
      └── Linux root filesystem
          ├── boot/uImage.FIT          # ARM U-Boot FIT kernel image (speaker)
          ├── boot/bzImage             # x86 installer kernel (hub)
          ├── tmp/raumfeld-update.zImage  # kexec updater kernel (hub)
          ├── etc/
          ├── raumfeld/                # proprietary service tree
          ├── factory/                 # device-specific certs
          └── ...
```

The hub's installer uses `kexec` to boot the inner `bzImage` directly from the running kernel, performs UBIFS flashing, then reboots into the new system. No code signing is enforced on the archive.

---

## 2. Filesystem Layout

```
/
├── bin/          Standard BusyBox + glibc utilities
├── boot/         Kernel image(s)
├── etc/          Configuration (see §4)
├── factory/      Device-class Google Cast certificates
├── lib/          glibc 2.23, kernel modules, udev rules
├── raumfeld/     Proprietary Raumfeld/Teufel services (see §5)
├── sbin/         init, kmod, etc.
├── tmp/          tmpfs at runtime; contains kexec updater
├── usr/lib/      ALSA plugins, GStreamer plugins, Raumfeld shared libs
└── var/          Runtime state (tmpfs symlinks)
```

Notable symlinks extracted from the archive (some fail on non-Linux hosts):
- `/etc/resolv.conf` → `../tmp/resolv.conf`
- `/var/lib/connman` → `/tmp/connman`

---

## 3. Init Sequence

SysV-style init via BusyBox `init` and `/etc/inittab`:

| Script | Function |
|---|---|
| `S01logging` | Syslog daemon |
| `S01raumfeld-led-update` | LED driver (HW indication) |
| `S05avahi-setup.sh` | Avahi hostname / mDNS bootstrap |
| `S10hostname` | Set hostname from factory config |
| `S10udev` | udevd |
| `S20urandom` / `S21haveged` | Entropy seeding |
| `S30dbus` | D-Bus session broker |
| `S40network` | Wired networking (connman) |
| `S41setup-gc-cert` | Install Google Cast cert from `/factory/template.crt` |
| `S42gc4a` | Google Cast for audio initialization |
| `S45connman` | ConnMan main daemon |
| `S46bluetooth` | Bluetooth (speaker only) |
| `S50avahi-daemon` | Avahi mDNS/DNS-SD |
| `S50dropbear` | SSH server (if `/etc/raumfeld/sshd_enabled` exists) |
| `S80harddisk` | Mount HDD (hub only) |
| `S85hardwared` | Hardware abstraction daemon (see §6) |
| `S90music` | Music daemon (hub only) |
| `S99master-process` | Start master-process supervisor loop |

`S99master-process` launches `start-master-process.sh`, which:
1. Runs `/usr/bin/raumfeld-key-creator` (generates device keypair if absent)
2. Enters a watchdog loop: starts `master-process`, restarts on exit unless `/run/raumfeld/shutdown-request` exists
3. Calls `/raumfeld/hardwared/hw-cli set-indication initializing` on each restart

---

## 4. Configuration Files

| Path | Purpose |
|---|---|
| `/etc/raumfeld-version` | Single-line firmware version string (`2.21.0`) |
| `/etc/os-release` | Buildroot identity (`2016.11.3`) |
| `/etc/TZ` | Timezone (empty = UTC) |
| `/etc/avahi/avahi-daemon.conf` | mDNS configuration; `use-ipv6=no` |
| `/etc/connman/main.conf` | Network manager settings |
| `/etc/ssh/sshd_config` | `PermitRootLogin yes`, `PermitEmptyPasswords yes` |
| `/etc/shadow` | Root password hash (blank = passwordless) |
| `/etc/asound.conf` | Custom ALSA PCM types (see §7) |
| `/etc/fw_const.config` | MTD partition map: `/dev/mtd2`, 256 KB, 2 sectors |
| `/etc/fw_env.config` | U-Boot environment partition (speaker) |
| `/etc/usbmount/mount.d/80setup-conf` | Symlinks `raumfeld-setup.json` from USB |
| `/etc/usbmount/mount.d/60updates` | Serves `raumfeld-updates.img` via local HTTP |
| `/etc/wpa_supplicant.conf` | Wi-Fi configuration template |
| `/etc/bluetooth/main.conf` | Bluetooth adapter settings (speaker) |

---

## 5. Raumfeld Service Tree (`/raumfeld/`)

All proprietary binaries live under `/raumfeld/`. The `master-process` reads `master-process-apps.json` to determine which services to start and in which role (host vs. client).

### 5.1 master-process-apps.json — Service Groups

```
alwaysApps    (run on every device regardless of zone role)
  renderer          Physical audio renderer — UPnP MediaRenderer
  stream-decoder    GStreamer/codec process for renderer
  rf-bluetoothd     Bluetooth audio (platforms: sue_s800, sue_s810 only)

hostApps      (only when device is zone host)
  timeserver        Wall clock reference server
  config-service    Distributed preferences store
  meta-server       UPnP ContentDirectory server
  stream-relay      Virtual zone MediaRenderer
  web-service       HTTP admin UI
  streamcastd       Google Cast audio (platforms: sue_s800 only)

clientApps    (when device is zone client)
  streamcastd       Google Cast audio (sue_s800 only)
```

Platform identifiers seen in the JSON: `sue_s800`, `sue_s810`, `virtual:sue_s810`.

### 5.2 Binary Summary

| Binary | Path | Role |
|---|---|---|
| `master-process` | `master-process/master-process` | Supervisor, zone orchestrator |
| `renderer` | `renderer/renderer` | Physical audio playback, AVTransport |
| `stream-relay` | `stream-relay/stream-relay` | Zone virtual renderer, sync coordinator |
| `hardwared` | `hardwared/hardwared` | Hardware abstraction (LEDs, buttons, MCU) |
| `hw-cli` | `hardwared/hw-cli` | CLI wrapper for hardwared |
| `meta-server` | `meta-server/meta-server` | ContentDirectory / media library |
| `config-service` | `config-service/config-service` | UPnP config key-value store |
| `timeserver` | `timeserver/timeserver` | NTP-synchronized wall clock server |
| `web-service` | `web-service/web-service` | HTTP admin interface |
| `rf-bluetoothd` | `bluetooth/rf-bluetoothd` | Raumfeld Bluetooth audio daemon |
| `mcu-talk` | `hardwared/mcu-talk` | Serial MCU communication tool |
| `mcu-flash` | `hardwared/mcu-flash` | MCU firmware updater |
| `component-flash` | `hardwared/component-flash` | Component firmware flash utility |

---

## 6. UPnP Service Architecture

### 6.1 Zone Virtual Renderer (`stream-relay`)

Device type: `urn:schemas-upnp-org:device:MediaRenderer:1`  
Friendly name: `Raumfeld Audio Stream Relay`  
`X_DLNACAP: playcontainer-0-1`

Services from `ZoneDevice.xml` / `TransportService.xml`:

| Service | ServiceType |
|---|---|
| AVTransport | `urn:schemas-upnp-org:service:AVTransport:1` |
| RenderingControl | `urn:schemas-upnp-org:service:RenderingControl:1` |
| ConnectionManager | `urn:schemas-upnp-org:service:ConnectionManager:1` |

Proprietary actions beyond standard AVTransport:

| Action | Arguments | Notes |
|---|---|---|
| `BendAVTransportURI` | `InstanceID`, `CurrentURI`, `CurrentURIMetaData` | Swap URI without tearing down the stream session; used for seamless handoff between zone states |
| `SetResourceForCurrentStream` | `ResourceURI` | Change the backing resource for the active stream without stopping |

Proprietary state variables in TransportService:

| Variable | Type | Events | Notes |
|---|---|---|---|
| `RoomStates` | string | no | JSON blob encoding per-room playback states within the zone |
| `SleepTimerActive` | boolean | no | Whether sleep timer is running |
| `SecondsUntilSleep` | ui4 | no | Countdown to automatic stop |
| `A_ARG_TYPE_ButtonNumber` | ui4 | no | Input for button-triggered transport actions |
| `A_ARG_TYPE_JsonObject` | string | no | Generic JSON argument for proprietary actions |

### 6.2 Physical Renderer (`renderer`)

Device type: `urn:schemas-upnp-org:device:MediaRenderer:1`

Services from `description.xml`:

| Service | ServiceType |
|---|---|
| AVTransport | `urn:schemas-upnp-org:service:AVTransport:1` |
| RenderingControl | `urn:schemas-upnp-org:service:RenderingControl:1` |
| ConnectionManager | `urn:schemas-upnp-org:service:ConnectionManager:1` |
| RaumfeldGenerator | `urn:schemas-raumfeld-com:service:RaumfeldGenerator:1` |

Non-standard AVTransport actions in `avtransport.xml`:

| Action | Arguments | Notes |
|---|---|---|
| `SetNextStartTriggerTime` | `InstanceID`, `TimeService`, `StartTime` | Schedule synchronized playback start at a future wall clock time |
| `Rewind` | `InstanceID` → `Position` | Seek to beginning, returns new position |
| `FastForward` | `InstanceID` → `Position` | Fast-forward |

**`RaumfeldGenerator`** (`urn:schemas-raumfeld-com:service:RaumfeldGenerator:1`): proprietary eventing-only service. SCPD exposes one evented state variable `TransportControlButtons` (string). The service notifies control points of physical button presses, allowing the app to respond without polling the device.

### 6.3 ContentDirectory (`meta-server`)

Standard UPnP ContentDirectory 1.0 (Browse, Search, GetSearchCapabilities, GetSortCapabilities). Serves the media library from the hub's attached storage. Device description in `meta-server/xml/DeviceDescription.xml`.

### 6.4 Config Service (`config-service`)

`urn:schemas-upnp-org:service:ConfigService:1` (Raumfeld extension)

Key actions:

| Action | Description |
|---|---|
| `GetPublicKey` | Returns device's RSA public key (PEM) |
| `GetRevision` | Current config revision number |
| `GetPreferences(PublicKey)` | Returns full preference tree as JSON (encrypted to PublicKey) |
| `SetPreferences(Preferences, LeastCommonChangedNode, ExpectedRevision, OnConflict)` | Update preference subtree with conflict resolution |
| `GetDevice(Service)` | Look up the UDN of the device hosting a given service type |

The `ExpectedRevision` + `OnConflict` parameters implement optimistic concurrency: if the current revision differs from `ExpectedRevision`, the server resolves the conflict per the `OnConflict` policy. This is a distributed CRDT-like configuration store shared across all zone members.

### 6.5 Setup Service (`master-process`)

Raumfeld Setup REST API on port 48366 plus UPnP setup service (`setup-service.xml`). UPnP actions: `GetInfo`, `CheckForUpdate`, `GetUpdateInfo`, `DoUpdate`, `GetDevice`, `GetNetworkInfo`. Full REST API documented in `docs/reverse-engineering/device-exploration.md`.

---

## 7. Audio Pipeline and Multi-Room Synchronization

Dedicated documents cover these topics in full:

- **`docs/dsp/audio-pipeline.md`** — ALSA layer, proprietary PCM plugin (`Teufel::DspAlsaPlugin`), renderer and hardware DSP configs per model, crossover/EQ pipeline, line-in routing, `timestretcher` role
- **`docs/synchronization/sync-protocol.md`** — `SetNextStartTriggerTime`, `pickNextStartTriggerTime`, `ZoneObserverSetNextAndWaitForConnect`, `AudioLoop` continuous correction, `RoomStates`, `BendAVTransportURI`

Key binary strings that evidence the sync mechanism (from `renderer` and `stream-relay`):

```
TransportService::SetNextStartTriggerTime
AudioLoop: OUT OF SYNC, we are lagging behind the system clock (…)
AudioLoop: OUT OF SYNC, we are running ahead of the system clock (…)
Teufel::Zone::pickNextStartTriggerTime
Teufel::ZoneObserverSetNextAndWaitForConnect
Teufel::Zone::handleRoomStateChanges
```

---

## 8. Hardware Abstraction (`hardwared`)

`hardwared` runs on every device and provides:
- LED indication via `hw-cli set-indication <state>` (states include `initializing`, `playing`, etc.)
- Button event routing (hardware buttons → D-Bus → `master-process`)
- MCU serial communication (`/dev/ttyS1` on speakers) via `mcu-talk` / `mcu-flash`
- MCU emulation mode (`RAUMFELD_HARDWARED_RUNMODE=mcu-emulator`) for development

The MCU manages power, button matrix, and LED controller on speaker hardware. `component-flash` and `mcu-flash` update MCU firmware independently from the main Linux firmware.

---

## 9. Factory Certificates

`/factory/` contains model-specific device certificate templates for Google Cast (Chromecast Audio protocol):

| File | Device class |
|---|---|
| `TeufelOneS` | One S |
| `TeufelOneM` | One M |
| `TeufelStereoL` | Stereo L |
| `TeufelStereoM` | Stereo M |
| `TeufelConnector` | Connector |

These are X.509 certificates signed by **Lautsprecher Teufel GmbH Cast** CA (intermediary) chained to **StreamUnlimited Cast Audio Dev** root. The cert CN is a template placeholder (`<UNIQUE HARDWARE ID> AA:BB:CC:DD:EE:FF`); a per-device cert is presumably injected at manufacturing time, not present in this public firmware image.

`S41setup-gc-cert` reads `/factory/template.crt` and installs it for the `streamcastd` (Google Cast) daemon on startup.

`/usr/bin/raumfeld-key-creator` generates the device RSA keypair on first boot, used by `config-service` (`GetPublicKey`).

---

## 10. Shared Libraries

| Library | Purpose |
|---|---|
| `libraumfeld-1.0.so` | Core Raumfeld C library |
| `libraumfeldcpp-1.0.so` | C++ layer (Teufel:: namespace) |
| `libraumfelddiscovery.so` | UPnP/mDNS discovery |
| `libraumfeld-discovery-plugin.so` | Discovery plugin interface |
| `libraumfelddsp.so` | DSP processing library |
| `libraumfeldmessaging.so` | IPC / D-Bus messaging |
| `libraumfeldspotify.so` | Spotify Connect integration |
| `libraumfeldupnp.so` | UPnP client/server stack |
| `libasound_module_pcm_raumfeld.so` | Custom ALSA PCM plugin (DSP + sync) |

---

## 11. Relation to Observed Network Behavior

| Observed network behavior | Firmware source |
|---|---|
| UPnP discovery of two separate devices per speaker (zone + renderer) | `stream-relay` + `renderer` both advertise via Avahi |
| `urn:schemas-raumfeld-com:service:RaumfeldGenerator:1` in renderer SSDP | `renderer/xml/description.xml` |
| Button presses triggering `LastChange` events | `RaumfeldGenerator` `TransportControlButtons` evented state variable |
| Zone transport `BendAVTransportURI` seen in Wireshark | `stream-relay/xml/TransportService.xml` |
| All devices in a zone start audio simultaneously | `SetNextStartTriggerTime` → `timestretcher` → wall clock anchor |
| `ConfigService` SOAP calls with JSON bodies | `config-service` distributed preference store |
| HTTPS on port 48366 (`_https._tcp / RaumfeldSetup`) | `master-process` setup REST API |
| Firmware updates fetched from Azure Blob Storage | `DoUpdate` → hub fetches `GET /{sha256}` with model/version headers |

---

## 12. SSH Access Summary

| Device | SSH status | Condition |
|---|---|---|
| Raumfeld Expand (hub) | **Open** — passwordless root | `sshd_enabled` flag present in hub firmware |
| One S / Cinebar Lux | **Closed** — port 22 refused | `sshd_enabled` absent; no API to enable it |

Old USB unlock (AppleSingle file `48fab7623bce0c903d5fe53dd681bb163eba85ae`) was removed before version 2.21.0. The only remaining unauthenticated code execution path for speakers is `raumfeld-fetch-debugtools` (requires an existing shell) or a firmware flash via `testing/v1/updateLocations` on the setup REST API.

---

## 13. Scope Boundary

This document contains only:
- Filesystem paths and directory structure
- Init script logic and service startup order
- SCPD XML action/variable names
- Public binary string constants (log messages, symbol names)
- Configuration file contents
- Protocol constants derived from the above

Not included: private keys, certificate private halves, proprietary algorithm implementations, raw binary disassembly, or any content that would enable bypassing device authentication or firmware signing.
