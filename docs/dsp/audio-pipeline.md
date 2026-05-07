# Raumfeld DSP Audio Pipeline

Source: static analysis of firmware 2.21.0 (`/raumfeld/renderer/dsp-config/` and `/raumfeld/hardwared/dsp-config/`). See `docs/firmware/firmware-analysis.md` §7 for ALSA layer context.

---

## 1. Two-Layer Architecture

Raumfeld uses two independent DSP layers between the network stream and the loudspeaker:

```
Network stream
  └── renderer/dsp-config/*.xml     (renderer layer — decoding, sync, line-in routing)
        └── ALSA raumfeld PCM plugin
              └── hardwared/dsp-config/*-alsa.xml  (hardware layer — crossover, EQ, gain)
                    └── DAC → driver units
```

The renderer layer runs in the `renderer` process and handles codec-agnostic signal routing. The hardware layer runs in `hardwared` and implements the loudspeaker-specific signal processing.

---

## 2. Renderer DSP Layer

Config files: `/raumfeld/renderer/dsp-config/<model>.xml`

Module types seen across models:

| Module type | Function |
|---|---|
| `input` | Decoded audio source (`stream-decoder` or `line-in`) |
| `timestretcher` | Rate-adaptive playback (see §4); always stereo |
| `signal-detector` | Level-triggered line-in detection with configurable threshold |
| `switch` | 2-way crossfade between two stereo sources |
| `gain` | Fixed or variable gain stage |
| `flac-encoder` | Encodes line-in to FLAC for network relay (Connector only) |
| `output` | DAC output; `interleave-pattern` controls channel mapping |

### 2.1 One S / One M — network-only path

```
stream-decoder → timestretcher → output[01]
```

The simplest topology: decode, time-stretch for sync, emit stereo.

### 2.2 Cinebar Lux — network + auto line-in

```
line-in ──→ signal-detector (threshold −72 dBFS)
              └── (controls switch)
line-in[0] ──→ switch[0]          ↘
timestretcher[0] → switch[1]  →  output[0]
line-in[1] ──→ switch[2]          ↗
timestretcher[1] → switch[3]  →  output[1]
```

`signal-detector` monitors the line-in for signal above −72 dBFS and flips `switch` from the network stream to line-in. This implements the automatic line-in priority behavior visible in the Cinebar Lux app settings.

### 2.3 Connector — line-in relay (network source)

```
line-in → signal-detector (threshold −60 dBFS)
line-in → line-in-gain → line-in-timestretcher → flac-encoder → (zone relay)
stream-decoder → timestretcher → switch → output[01]
```

The Connector encodes line-in audio to FLAC and streams it to the zone, making analogue inputs available as a Raumfeld network source. `line-in-timestretcher` synchronizes the analogue capture clock to the zone wall clock before encoding.

---

## 3. Hardware (ALSA) DSP Layer

Config files: `/raumfeld/hardwared/dsp-config/<model>-alsa.xml`

Module types:

| Module type | Function |
|---|---|
| `input` | Entry point from the ALSA plugin |
| `sounds` | System sounds mixer (alerts, tones) |
| `patchbay` | Stereo/mono routing; `routing` ∈ {`mono`, `stereo-l-r`, `stereo-r-l`} |
| `equalizer` | Parametric EQ bank; `gain-correction` normalizes for inserted gain |
| `adaptive-biquad` | Volume-dependent biquad; gain spec is `vol_dB=gain_dB,...` lookup table |
| `biquad` | Fixed biquad filter; types: `hipass`, `lopass`, `peak`, `hishelf`, `loshelf` |
| `gain` | Fixed gain in dB |
| `delay` | Fractional-sample delay (inter-driver alignment) |
| `phase-invert` | 180° phase flip |
| `output` | DAC write; `interleave-pattern` = channel order |

### 3.1 One S — 2-way active crossover

```
input → system-sounds → patchbay → user-eq → bass-boost (70 Hz, Q=2.4, vol-dep) → bass-boost2 (50 Hz, Q=2, vol-dep) → sumshelf (hishelf 3 kHz, −10 dB)
  │
  ├── woofer: subsonic1 (hipass 45 Hz Q=0.71) → subsonic2 (hipass 45 Hz Q=0.8)
  │           → lo-pass (2400 Hz Q=0.707)
  │           → EQ: peak 1800 Hz −3 dB → peak 1500 Hz −2 dB → loshelf 500 Hz +5 dB
  │           → gain −17.5 dB → output[0]
  │
  └── tweeter: hi-pass (4000 Hz Q=1.2)
               → EQ: peak 1600 Hz −23 dB → peak 5440 Hz −5 dB → peak 7200 Hz −2.5 dB
                   → peak 3800 Hz −2 dB → hishelf 7500 Hz +1 dB
               → phase-invert → delay 0 → gain +9 dB → output[1]
```

Crossover frequencies: woofer low-pass 2400 Hz, tweeter high-pass 4000 Hz (Linkwitz–Riley–adjacent with phase invert).

The `adaptive-biquad` bass-boost modules apply more bass at low volumes and shelve it off at high volumes — this is the loudness curve baked into the speaker DSP.

---

## 4. Synchronization Role of `timestretcher`

The `timestretcher` module is the continuous-sync mechanism in multi-room playback. It resamples audio at a rate slightly above or below nominal to track the zone wall clock:

- Wall clock reference: `/raumfeld/timeserver/timeserver` (NTP-derived, runs on zone host)
- Scheduled start: `SetNextStartTriggerTime` UPnP action sets a future wall-clock timestamp
- Continuous correction: renderer `AudioLoop` compares `clock_gettime()` against expected playback position; `timestretcher` adjusts rate to close the gap
- Log evidence: `"AudioLoop: OUT OF SYNC, we are lagging/running ahead of the system clock"`

The `hw_delay_ms` parameter in `/etc/asound.conf` feeds the measured DAC hardware latency back into the synchronization calculation so that the timestretcher targets the wall clock at the moment of actual sound emission, not at the software write.

See `docs/synchronization/sync-protocol.md` for the full multi-device coordination protocol.

---

## 5. Model Coverage

| Model | Renderer DSP | Notable features |
|---|---|---|
| One S | `raumfeld-one-s.xml` | stream-decoder → timestretcher → output |
| One M | `raumfeld-one-m-2.xml` | same topology as One S |
| Cinebar Lux | `teufel-cinebar-lux.xml` | auto line-in switch (−72 dBFS threshold) |
| Connector | `raumfeld-connector-2.xml` | line-in → FLAC encode → zone relay |
| Stereo L/M/S | `raumfeld-stereo-*.xml` | stereo pair variants |
| Soundbar | `raumfeld-soundbar.xml` | multi-channel output |
| Sounddeck | `raumfeld-sounddeck.xml` | soundbar companion |

Hardware DSP configs mirror this model list with speaker-specific crossover and EQ per driver.
