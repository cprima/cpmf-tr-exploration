# Raumfeld Firmware — Service Inventory

Extracted from `~/fw_work/` by `scripts/service_inventory.py`.
Each section covers one firmware image's rootfs (`_pass2_0`).

## base — Gen 1 – Base Station
Rootfs: `_pass2_0`

### Boot / init scripts
| Script | Purpose |
|---|---|
| `S20urandom` | Seed /dev/urandom entropy |
| `S40network` | Network interface bringup |
| `rcK` | Shutdown entry point |
| `rcS` | Sysinit entry point |

### D-Bus policy files
- `/etc/dbus-1/system.d/com.raumfeld.hardwared.conf`

---

## base2 — Gen 2 – Base Station
Rootfs: `_pass2_0`

### Boot / init scripts
| Script | Purpose |
|---|---|
| `S05avahi-setup.sh` | Avahi/mDNS early setup |
| `S20urandom` | Seed /dev/urandom entropy |
| `S30dbus` | Start D-Bus system daemon |
| `S40network` | Network interface bringup |
| `rcK` | Shutdown entry point |
| `rcS` | Sysinit entry point |

### D-Bus policy files
- `/etc/dbus-1/system.d/com.raumfeld.hardwared.conf`

### Raumfeld binaries
- `/usr/bin/raumfeld-key-creator`
- `/usr/bin/raumfeld-platform`
- `/usr/bin/raumfeld-prefs`
- `/usr/bin/raumfeld-prefs-storage`
- `/usr/bin/raumfeld-syslogd`
- `/usr/bin/raumfeld-update`
- `/usr/bin/raumfeld-updates-server`
- `/usr/bin/start-raumfeld-syslogd.sh`

### Raumfeld shared libraries
- `libraumfeld-1.0.so`
- `libraumfeldcpp-1.0.so`
- `libraumfelddsp.so`
- `libraumfeldmessaging.so`

### Cloud API endpoints (`usr/share/raumfeld-1.0/services`)
```
features.json = "https://api.raumfeld.com/features.json"

discovery/v1/rfos/controller = "https://api.raumfeld.com/discovery/v1/rfos/controller"
systems/v1/rfos = "https://api.raumfeld.com/systems/v1/rfos"

timezone/info.json = "http://time.raumfeld.com/info.json"
timezone = "https://time.raumfeld.com/zone"
timezone/timezones.json = "https://time.raumfeld.com/timezones.json"

usages = "https://stats.raumfeld.com/usages"
gc4a = "https://updates.raumfeld.com/streamcastd-2.12"
auth = "https://auth.raumfeld.com"

reports/upload = "https://reports.raumfeld.com/upload/firmware"
```

### DSP / hardware profiles (`raumfeld/hardwared/dsp-config/`)
- `development-pc`
- `raumfeld-connector-2`
- `raumfeld-one-m-2`
- `raumfeld-one-s`
- `raumfeld-soundbar`
- `raumfeld-sounddeck`
- `raumfeld-stereo-cubes`
- `raumfeld-stereo-l-2`
- `raumfeld-stereo-m-2`
- `teufel-cinebar-lux`
- `teufel-rosenthal`
- `teufel-streamer`
- `teufel-third-gen`

---

## connect — Gen 1 – Connector
Rootfs: `_pass2_0`

### Boot / init scripts
| Script | Purpose |
|---|---|
| `S20urandom` | Seed /dev/urandom entropy |
| `S40network` | Network interface bringup |
| `rcK` | Shutdown entry point |
| `rcS` | Sysinit entry point |

### D-Bus policy files
- `/etc/dbus-1/system.d/com.raumfeld.hardwared.conf`

---

## connect2 — Gen 2 – Connector
Rootfs: `_pass2_0`

### Boot / init scripts
| Script | Purpose |
|---|---|
| `S05avahi-setup.sh` | Avahi/mDNS early setup |
| `S20urandom` | Seed /dev/urandom entropy |
| `S30dbus` | Start D-Bus system daemon |
| `S40network` | Network interface bringup |
| `rcK` | Shutdown entry point |
| `rcS` | Sysinit entry point |

### D-Bus policy files
- `/etc/dbus-1/system.d/com.raumfeld.hardwared.conf`

### Raumfeld binaries
- `/usr/bin/raumfeld-key-creator`
- `/usr/bin/raumfeld-platform`
- `/usr/bin/raumfeld-prefs`
- `/usr/bin/raumfeld-prefs-storage`
- `/usr/bin/raumfeld-syslogd`
- `/usr/bin/raumfeld-update`
- `/usr/bin/raumfeld-updates-server`
- `/usr/bin/start-raumfeld-syslogd.sh`

### Raumfeld shared libraries
- `libraumfeld-1.0.so`
- `libraumfeldcpp-1.0.so`
- `libraumfelddsp.so`
- `libraumfeldmessaging.so`

### Cloud API endpoints (`usr/share/raumfeld-1.0/services`)
```
features.json = "https://api.raumfeld.com/features.json"

discovery/v1/rfos/controller = "https://api.raumfeld.com/discovery/v1/rfos/controller"
systems/v1/rfos = "https://api.raumfeld.com/systems/v1/rfos"

timezone/info.json = "http://time.raumfeld.com/info.json"
timezone = "https://time.raumfeld.com/zone"
timezone/timezones.json = "https://time.raumfeld.com/timezones.json"

usages = "https://stats.raumfeld.com/usages"
gc4a = "https://updates.raumfeld.com/streamcastd-2.12"
auth = "https://auth.raumfeld.com"

reports/upload = "https://reports.raumfeld.com/upload/firmware"
```

### DSP / hardware profiles (`raumfeld/hardwared/dsp-config/`)
- `development-pc`
- `raumfeld-connector-2`
- `raumfeld-one-m-2`
- `raumfeld-one-s`
- `raumfeld-soundbar`
- `raumfeld-sounddeck`
- `raumfeld-stereo-cubes`
- `raumfeld-stereo-l-2`
- `raumfeld-stereo-m-2`
- `teufel-cinebar-lux`
- `teufel-rosenthal`
- `teufel-streamer`
- `teufel-third-gen`

---

## connect3 — Gen 3 – Connector
Rootfs: `_pass2_0`

### Boot / init scripts
| Script | Purpose |
|---|---|
| `S05avahi-setup.sh` | Avahi/mDNS early setup |
| `S10udev` | udev device manager |
| `S20urandom` | Seed /dev/urandom entropy |
| `S30dbus` | Start D-Bus system daemon |
| `S40network` | Network interface bringup |
| `S50dropbear` | SSH daemon (dropbear) |
| `S80dhcp-relay` | DHCP relay agent |
| `S80dhcp-server` | DHCP server |
| `rcK` | Shutdown entry point |
| `rcS` | Sysinit entry point |

### D-Bus policy files
- `/etc/dbus-1/system.d/com.raumfeld.hardwared.conf`
- `/etc/dbus-1/system.d/wpa_supplicant.conf`

### Raumfeld binaries
- `/usr/bin/raumfeld-key-creator`
- `/usr/bin/raumfeld-platform`
- `/usr/bin/raumfeld-prefs`
- `/usr/bin/raumfeld-prefs-storage`
- `/usr/bin/raumfeld-syslogd`
- `/usr/bin/raumfeld-update`
- `/usr/bin/raumfeld-updates-server`
- `/usr/bin/start-raumfeld-syslogd.sh`

### Raumfeld shared libraries
- `libraumfeld-1.0.so`
- `libraumfeldcpp-1.0.so`
- `libraumfelddsp.so`
- `libraumfeldmessaging.so`

### Cloud API endpoints (`usr/share/raumfeld-1.0/services`)
```
features.json = "https://api.raumfeld.com/features.json"

discovery/v1/rfos/controller = "https://api.raumfeld.com/discovery/v1/rfos/controller"
systems/v1/rfos = "https://api.raumfeld.com/systems/v1/rfos"

timezone/info.json = "http://time.raumfeld.com/info.json"
timezone = "https://time.raumfeld.com/zone"
timezone/timezones.json = "https://time.raumfeld.com/timezones.json"

usages = "https://stats.raumfeld.com/usages"
gc4a = "https://updates.raumfeld.com/streamcastd-2.12"
auth = "https://auth.raumfeld.com"

reports/upload = "https://reports.raumfeld.com/upload/firmware"
```

### DSP / hardware profiles (`raumfeld/hardwared/dsp-config/`)
- `development-pc`
- `raumfeld-connector-2`
- `raumfeld-one-m-2`
- `raumfeld-one-s`
- `raumfeld-soundbar`
- `raumfeld-sounddeck`
- `raumfeld-stereo-cubes`
- `raumfeld-stereo-l-2`
- `raumfeld-stereo-m-2`
- `teufel-cinebar-lux`
- `teufel-rosenthal`
- `teufel-streamer`
- `teufel-third-gen`

---

## speaker — Gen 1 – Speaker
Rootfs: `_pass2_0`

### Boot / init scripts
| Script | Purpose |
|---|---|
| `S20urandom` | Seed /dev/urandom entropy |
| `S40network` | Network interface bringup |
| `rcK` | Shutdown entry point |
| `rcS` | Sysinit entry point |

### D-Bus policy files
- `/etc/dbus-1/system.d/com.raumfeld.hardwared.conf`

---

## speaker2 — Gen 2 – Speaker
Rootfs: `_pass2_0`

### Boot / init scripts
| Script | Purpose |
|---|---|
| `S05avahi-setup.sh` | Avahi/mDNS early setup |
| `S20urandom` | Seed /dev/urandom entropy |
| `S30dbus` | Start D-Bus system daemon |
| `S40network` | Network interface bringup |
| `rcK` | Shutdown entry point |
| `rcS` | Sysinit entry point |

### D-Bus policy files
- `/etc/dbus-1/system.d/com.raumfeld.hardwared.conf`

### Raumfeld binaries
- `/usr/bin/raumfeld-key-creator`
- `/usr/bin/raumfeld-platform`
- `/usr/bin/raumfeld-prefs`
- `/usr/bin/raumfeld-prefs-storage`
- `/usr/bin/raumfeld-syslogd`
- `/usr/bin/raumfeld-update`
- `/usr/bin/raumfeld-updates-server`
- `/usr/bin/start-raumfeld-syslogd.sh`

### Raumfeld shared libraries
- `libraumfeld-1.0.so`
- `libraumfeldcpp-1.0.so`
- `libraumfelddsp.so`
- `libraumfeldmessaging.so`

### Cloud API endpoints (`usr/share/raumfeld-1.0/services`)
```
features.json = "https://api.raumfeld.com/features.json"

discovery/v1/rfos/controller = "https://api.raumfeld.com/discovery/v1/rfos/controller"
systems/v1/rfos = "https://api.raumfeld.com/systems/v1/rfos"

timezone/info.json = "http://time.raumfeld.com/info.json"
timezone = "https://time.raumfeld.com/zone"
timezone/timezones.json = "https://time.raumfeld.com/timezones.json"

usages = "https://stats.raumfeld.com/usages"
gc4a = "https://updates.raumfeld.com/streamcastd-2.12"
auth = "https://auth.raumfeld.com"

reports/upload = "https://reports.raumfeld.com/upload/firmware"
```

### DSP / hardware profiles (`raumfeld/hardwared/dsp-config/`)
- `development-pc`
- `raumfeld-connector-2`
- `raumfeld-one-m-2`
- `raumfeld-one-s`
- `raumfeld-soundbar`
- `raumfeld-sounddeck`
- `raumfeld-stereo-cubes`
- `raumfeld-stereo-l-2`
- `raumfeld-stereo-m-2`
- `teufel-cinebar-lux`
- `teufel-rosenthal`
- `teufel-streamer`
- `teufel-third-gen`

---

## speaker3 — Gen 3 – Speaker
Rootfs: `_pass2_0`

### Boot / init scripts
| Script | Purpose |
|---|---|
| `S05avahi-setup.sh` | Avahi/mDNS early setup |
| `S10udev` | udev device manager |
| `S20urandom` | Seed /dev/urandom entropy |
| `S30dbus` | Start D-Bus system daemon |
| `S40network` | Network interface bringup |
| `S50dropbear` | SSH daemon (dropbear) |
| `S80dhcp-relay` | DHCP relay agent |
| `S80dhcp-server` | DHCP server |
| `rcK` | Shutdown entry point |
| `rcS` | Sysinit entry point |

### D-Bus policy files
- `/etc/dbus-1/system.d/com.raumfeld.hardwared.conf`
- `/etc/dbus-1/system.d/wpa_supplicant.conf`

### Raumfeld binaries
- `/usr/bin/raumfeld-key-creator`
- `/usr/bin/raumfeld-platform`
- `/usr/bin/raumfeld-prefs`
- `/usr/bin/raumfeld-prefs-storage`
- `/usr/bin/raumfeld-syslogd`
- `/usr/bin/raumfeld-update`
- `/usr/bin/raumfeld-updates-server`
- `/usr/bin/start-raumfeld-syslogd.sh`

### Raumfeld shared libraries
- `libraumfeld-1.0.so`
- `libraumfeldcpp-1.0.so`
- `libraumfelddsp.so`
- `libraumfeldmessaging.so`

### Cloud API endpoints (`usr/share/raumfeld-1.0/services`)
```
features.json = "https://api.raumfeld.com/features.json"

discovery/v1/rfos/controller = "https://api.raumfeld.com/discovery/v1/rfos/controller"
systems/v1/rfos = "https://api.raumfeld.com/systems/v1/rfos"

timezone/info.json = "http://time.raumfeld.com/info.json"
timezone = "https://time.raumfeld.com/zone"
timezone/timezones.json = "https://time.raumfeld.com/timezones.json"

usages = "https://stats.raumfeld.com/usages"
gc4a = "https://updates.raumfeld.com/streamcastd-2.12"
auth = "https://auth.raumfeld.com"

reports/upload = "https://reports.raumfeld.com/upload/firmware"
```

### DSP / hardware profiles (`raumfeld/hardwared/dsp-config/`)
- `development-pc`
- `raumfeld-connector-2`
- `raumfeld-one-m-2`
- `raumfeld-one-s`
- `raumfeld-soundbar`
- `raumfeld-sounddeck`
- `raumfeld-stereo-cubes`
- `raumfeld-stereo-l-2`
- `raumfeld-stereo-m-2`
- `teufel-cinebar-lux`
- `teufel-rosenthal`
- `teufel-streamer`
- `teufel-third-gen`

---

