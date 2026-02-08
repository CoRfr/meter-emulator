"""Shared test fixtures."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from meter_emulator.backends.base import Backend, MeterData, PhaseData
from meter_emulator.frontends.shelly import ShellyFrontend


class MockBackend(Backend):
    """A backend that returns configurable test data."""

    def __init__(self, data: MeterData | None = None) -> None:
        self._data = data or self._default_data()

    @staticmethod
    def _default_data() -> MeterData:
        phase = PhaseData(
            voltage=230.5,
            current=4.2,
            act_power=500.0,
            aprt_power=520.0,
            pf=0.96,
            freq=50.0,
            total_act_energy=12345.67,
            total_act_ret_energy=6789.01,
        )
        return MeterData(
            phases=[phase],
            total_act_power=500.0,
            total_aprt_power=520.0,
            total_current=4.2,
            total_act_energy=12345.67,
            total_act_ret_energy=6789.01,
        )

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def get_meter_data(self) -> MeterData:
        return self._data

    def set_data(self, data: MeterData) -> None:
        self._data = data


TEST_MAC = "AABBCCDDEEFF"


@pytest.fixture
def mock_backend():
    return MockBackend()


@pytest.fixture
def client(mock_backend):
    """FastAPI test client with a Shelly frontend (no lifespan)."""
    frontend = ShellyFrontend(mock_backend, {"mac": TEST_MAC, "phases": 1, "mdns": False})
    test_app = FastAPI()
    test_app.include_router(frontend.get_router())
    with TestClient(test_app) as c:
        yield c
