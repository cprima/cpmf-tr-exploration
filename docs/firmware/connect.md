# connect.img

**Device**: Raumfeld Connector (1st gen, ≤2013, external antenna)  
**Source**: <https://updates.raumfeld.com/repair/connect.img>  
**Size**: 37.7 MB (39,565,312 bytes)  
**SHA-256**: `8672d13d7e1cf6183cd36b7859fa17ca9243f2d433f0fc7a3cba45c01877af1b`  
**Analysed**: 2026-05-07

## Image format

- **format**: `U-Boot uImage (legacy)`
- **magic**: `0x27051956`
- **name**: `ImpedanceMatcher (3rd stage)`
- **timestamp**: `2021-11-02T23:45:34+00:00`
- **data_size**: `4825364`
- **load_addr**: `0xa0008000`
- **entry_point**: `0xa0008000`
- **os**: `Linux`
- **arch**: `arm`
- **type**: `kernel`
- **compression**: `none`

## Versions found

- `VERSION=2016.11.3`
- `PRETTY_NAME="Buildroot 2016.11.3"`

## Capabilities detected

- Buildroot
- Raumfeld
- SSH

## Version / release files

### `etc/os-release`

```
NAME=Buildroot
VERSION=2016.11.3-04597-gcfb903d
ID=buildroot
VERSION_ID=2016.11.3
PRETTY_NAME="Buildroot 2016.11.3"
```

### `etc/raumfeld-version`

```
2.17.4
```

### `etc/hostname`

```
buildroot
```


## Interesting paths (up to 50)

- `_connect.img.extracted/com.raumfeld.hardwared.conf`
- `_connect.img.extracted/dropbear`
- `_connect.img.extracted/raumfeld-version`
