"""Frontend registry and factory."""

from meter_emulator.backends.base import Backend
from meter_emulator.frontends.base import Frontend
from meter_emulator.frontends.shelly import ShellyFrontend

_FRONTENDS: dict[str, type[Frontend]] = {
    "shelly": ShellyFrontend,
}


def create_frontend(frontend_type: str, backend: Backend, config: dict) -> Frontend:
    """Create a frontend instance by type name."""
    cls = _FRONTENDS.get(frontend_type)
    if cls is None:
        raise ValueError(
            f"Unknown frontend type: {frontend_type!r}. Available: {', '.join(_FRONTENDS)}"
        )
    return cls(backend, config)
