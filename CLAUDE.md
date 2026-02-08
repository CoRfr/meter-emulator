# Meter Emulator

Pluggable energy meter emulator. Polls a backend data source and exposes it via an emulated meter HTTP API. Currently: Shelly Pro 3EM frontend + Enphase Envoy backend.

## Development

```bash
poetry install
poetry run pytest -v        # 19 tests
poetry run ruff check .     # lint
poetry run meter-emulator -c config.yaml
```

Pre-commit hooks (ruff + formatting) run on every commit.

## Project Structure

```
src/meter_emulator/
├── main.py              # FastAPI app, lifespan, CLI entry point
├── config.py            # YAML config loading, env var substitution, Pydantic models
├── frontends/
│   ├── __init__.py      # Frontend registry + create_frontend() factory
│   ├── base.py          # Frontend ABC (get_router, start, stop)
│   └── shelly.py        # Shelly Pro 3EM: routes, response models, mDNS
└── backends/
    ├── __init__.py      # Backend registry + create_backend() factory
    ├── base.py          # Backend ABC + PhaseData/MeterData dataclasses
    └── envoy.py         # Enphase Envoy poller + response parser

tests/
├── conftest.py              # MockBackend, TEST_MAC, client fixture
├── test_config.py           # Config loading and validation
├── test_envoy_backend.py    # Envoy response parsing
└── test_shelly_frontend.py  # Shelly HTTP endpoint responses

meter-emulator/              # Home Assistant add-on
├── config.yaml              # Add-on metadata, options schema
├── DOCS.md                  # Documentation tab content
└── translations/en.yaml     # UI labels and descriptions
```

## Architecture

- **Backends** produce `MeterData` (list of `PhaseData` + totals). Abstract base in `backends/base.py`.
- **Frontends** consume `MeterData` via `backend.get_meter_data()` and serve HTTP endpoints. Abstract base in `frontends/base.py`.
- Both use a factory pattern: `create_backend(type, config)` / `create_frontend(type, backend, config)`.
- Frontend receives the backend at init and builds an `APIRouter` with closures capturing the backend reference.
- `main.py` lifespan: load config → create backend → start backend → create frontend → mount router → start frontend → yield → stop both.

## Config Format

```yaml
server:
  host: "0.0.0.0"
  port: 80
frontend:
  type: shelly
  shelly:
    mac: "AABBCCDDEEFF"  # optional, auto-generated
    phases: 1             # 1 or 3
    mdns: true
backend:
  type: envoy
  envoy:
    host: "192.168.1.100"
    token: "${ENVOY_TOKEN}"  # env var substitution supported
    poll_interval: 2.0
    verify_ssl: false
```

## Docker & HA Add-on

- `Dockerfile`: multi-stage build, smart `entrypoint.sh` detects HA mode (`/data/options.json`) vs standalone.
- `repository.yaml` + `meter-emulator/`: makes this repo an HA add-on repository.
- CI (`.github/workflows/docker.yml`): tests → multi-arch build (amd64 + arm64) → push to `ghcr.io/corfr/meter-emulator`.
- HA add-on `config.yaml` version must match the git tag (e.g., `v0.1.1` → `version: "0.1.1"`).

## Versioning

When releasing: bump version in both `pyproject.toml` and `meter-emulator/config.yaml`, then `git tag v<version>`. CI builds and pushes the Docker image with that tag. HA pulls the image matching the add-on version.
