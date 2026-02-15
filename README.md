# Meter Emulator

A pluggable energy meter emulator with configurable frontends and backends. Currently implements a Shelly Pro 3EM frontend with an Enphase Envoy backend, allowing devices like the Marstek Venus-E battery (which require a Shelly meter) to work with Enphase systems.

## How It Works

```
Enphase Envoy ──(poll /production.json)──> Meter Emulator ──(Shelly HTTP API)──> Marstek Venus-E
```

The emulator polls a backend data source at a configurable interval, translates the data into the selected frontend's format, and serves it over HTTP. The Shelly frontend advertises itself via mDNS using both `_http._tcp` and `_shelly._tcp` service types (matching real Shelly Gen2 devices) so compatible devices can discover it automatically.

## Shelly API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /shelly` | Device info |
| `GET /rpc/Shelly.GetDeviceInfo` | Device info (RPC) |
| `GET /rpc/EM.GetStatus?id=0` | Real-time per-phase power data |
| `GET /rpc/EMData.GetStatus?id=0` | Cumulative energy totals |
| `GET /rpc/Shelly.GetStatus` | Full device status |

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit:

```yaml
server:
  host: "0.0.0.0"
  port: 80

frontend:
  type: shelly
  shelly:
    mac: "AABBCCDDEEFF"   # Auto-generated if omitted
    phases: 1              # 1 or 3
    mdns: true

backend:
  type: envoy
  envoy:
    host: "192.168.1.100"
    token: "${ENVOY_TOKEN}"   # Supports env var substitution
    poll_interval: 2.0
    verify_ssl: false
    # Optional: Enlighten credentials for automatic token refresh
    # username: "your-enphase-email@example.com"
    # password: "${ENPHASE_PASSWORD}"
    # serial: "123456789012"
```

### Envoy Authentication

Firmware >= 7.0 requires a JWT token for authentication. There are two options:

- **Automatic (recommended):** Provide your Enlighten Cloud credentials (`username`, `password`, `serial`). The token is obtained and refreshed automatically via pyenphase, so you never need to manually replace expired tokens.
- **Manual:** Obtain a JWT from [Enphase Entrez](https://entrez.enphaseenergy.com/) or via the Envoy's local API and pass it via the `ENVOY_TOKEN` environment variable or directly in the config. Note that installer tokens from Entrez are only valid for 12 hours.

## Development

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest -v

# Run linter
poetry run ruff check .

# Start the emulator
poetry run meter-emulator -c config.yaml
```

### Pre-commit Hooks

```bash
poetry run pre-commit install
```

This sets up ruff (linting + formatting) and basic file checks on every commit.

## Docker

```bash
docker build -t meter-emulator .
docker run -p 80:80 -v $(pwd)/config.yaml:/app/config.yaml meter-emulator
```

## Architecture

The project uses pluggable frontends and backends. New frontends (meter protocols) or backends (data sources) can be added by implementing the corresponding abstract base class.

```
src/meter_emulator/
├── main.py           # FastAPI app + lifespan
├── config.py         # YAML config loading + validation
├── frontends/
│   ├── base.py       # Abstract Frontend class
│   └── shelly.py     # Shelly Pro 3EM (routes + models + mDNS)
└── backends/
    ├── base.py       # Abstract Backend + MeterData
    └── envoy.py      # Enphase Envoy backend
```
