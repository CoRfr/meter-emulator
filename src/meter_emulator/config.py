import os
import re
import uuid
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


def _substitute_env_vars(value: str) -> str:
    """Replace ${ENV_VAR} patterns with environment variable values."""

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        env_val = os.environ.get(var_name)
        if env_val is None:
            raise ValueError(f"Environment variable {var_name!r} is not set")
        return env_val

    return re.sub(r"\$\{([^}]+)}", replacer, value)


def _walk_and_substitute(obj: object) -> object:
    """Recursively substitute env vars in all string values."""
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _walk_and_substitute(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_and_substitute(item) for item in obj]
    return obj


def _generate_mac() -> str:
    """Generate a deterministic-looking MAC from a random UUID."""
    return uuid.uuid4().hex[:12].upper()


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 80


class ShellyFrontendConfig(BaseModel):
    mac: str = Field(default_factory=_generate_mac)
    phases: int = 1
    mdns: bool = True

    @field_validator("phases")
    @classmethod
    def validate_phases(cls, v: int) -> int:
        if v not in (1, 3):
            raise ValueError("phases must be 1 or 3")
        return v

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        v = v.upper().replace(":", "").replace("-", "")
        if len(v) != 12 or not all(c in "0123456789ABCDEF" for c in v):
            raise ValueError("mac must be 12 hex characters")
        return v


class FrontendConfig(BaseModel):
    type: str = "shelly"
    shelly: ShellyFrontendConfig = Field(default_factory=ShellyFrontendConfig)


class EnvoyConfig(BaseModel):
    host: str
    token: str
    poll_interval: float = 2.0
    verify_ssl: bool = False


class BackendConfig(BaseModel):
    type: str = "envoy"
    envoy: EnvoyConfig | None = None


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    frontend: FrontendConfig = Field(default_factory=FrontendConfig)
    backend: BackendConfig = Field(default_factory=BackendConfig)


def load_config(path: str | Path) -> AppConfig:
    """Load and validate configuration from a YAML file."""
    path = Path(path)
    with path.open() as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raw = {}

    raw = _walk_and_substitute(raw)
    return AppConfig.model_validate(raw)
