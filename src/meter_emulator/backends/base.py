from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PhaseData:
    """Electrical measurements for a single phase."""

    voltage: float = 0.0
    current: float = 0.0
    act_power: float = 0.0  # Active power (W) — positive=import, negative=export
    aprt_power: float = 0.0  # Apparent power (VA)
    pf: float = 0.0  # Power factor
    freq: float = 50.0  # Grid frequency (Hz)
    total_act_energy: float = 0.0  # Cumulative import energy (Wh)
    total_act_ret_energy: float = 0.0  # Cumulative export energy (Wh)


@dataclass
class MeterData:
    """Normalized meter data produced by backends, consumed by frontends."""

    phases: list[PhaseData] = field(default_factory=lambda: [PhaseData()])
    total_act_power: float = 0.0
    total_aprt_power: float = 0.0
    total_current: float = 0.0
    total_act_energy: float = 0.0
    total_act_ret_energy: float = 0.0


class Backend(ABC):
    """Abstract base class for meter data backends."""

    @abstractmethod
    async def start(self) -> None:
        """Start the backend (e.g., begin polling)."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the backend and clean up resources."""

    @abstractmethod
    def get_meter_data(self) -> MeterData:
        """Return the latest meter data snapshot."""
