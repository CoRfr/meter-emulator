from meter_emulator.backends.base import Backend
from meter_emulator.backends.envoy import EnvoyBackend

_BACKENDS: dict[str, type[Backend]] = {
    "envoy": EnvoyBackend,
}


def create_backend(backend_type: str, config: dict) -> Backend:
    """Create a backend instance by type name."""
    cls = _BACKENDS.get(backend_type)
    if cls is None:
        raise ValueError(
            f"Unknown backend type: {backend_type!r}. Available: {', '.join(_BACKENDS)}"
        )
    return cls(config)
