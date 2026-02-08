# Meter Emulator

A pluggable energy meter emulator. It polls a backend data source and exposes
the data via an emulated meter HTTP API. Currently supports emulating a
**Shelly Pro 3EM** using data from an **Enphase Envoy** solar gateway.

## Use case

Devices like the **Marstek Venus-E** battery require a Shelly Pro 3EM energy
meter to read grid consumption. If you have an Enphase Envoy instead, this
add-on bridges the gap — the Marstek sees a Shelly meter, but the data comes
from the Envoy.

```
Enphase Envoy ──(poll)──> Meter Emulator ──(Shelly HTTP API)──> Marstek Venus-E
```

## Getting an Envoy token

Enphase Envoy firmware >= 7.0 requires a JWT token for local API access.

1. Go to <https://entrez.enphaseenergy.com/>
2. Log in with your Enphase account
3. Select your gateway's serial number
4. Copy the generated JWT token
5. Paste it into the **Envoy token** field in the add-on configuration

The token expires periodically — you will need to repeat this process when it
does (typically every few months).

## Configuration

| Option | Description |
|--------|-------------|
| **Frontend type** | Meter protocol to emulate (`shelly` = Shelly Pro 3EM) |
| **MAC address** | Fake device MAC (auto-generated if empty) |
| **Number of phases** | `1` for single-phase, `3` for three-phase |
| **mDNS discovery** | Advertise the meter on the local network via mDNS |
| **Backend type** | Data source (`envoy` = Enphase Envoy) |
| **Envoy host** | IP address of your Envoy gateway |
| **Envoy token** | JWT token (see above) |
| **Poll interval** | How often to fetch data from the Envoy (seconds) |
| **Verify SSL** | Check the Envoy's TLS certificate (usually off — self-signed) |

## Shelly API endpoints

The following Shelly Pro 3EM endpoints are emulated:

| Endpoint | Description |
|----------|-------------|
| `GET /shelly` | Device info |
| `GET /rpc/Shelly.GetDeviceInfo` | Device info (RPC) |
| `GET /rpc/EM.GetStatus?id=0` | Real-time per-phase power data |
| `GET /rpc/EMData.GetStatus?id=0` | Cumulative energy totals |
| `GET /rpc/Shelly.GetStatus` | Full device status |

## Network

This add-on runs with **host networking** so that mDNS advertisement works
and devices on the local network can discover and reach it on port 80.
