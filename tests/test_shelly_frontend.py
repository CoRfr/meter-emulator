"""Tests for Shelly frontend API endpoints."""

from meter_emulator.backends.base import MeterData, PhaseData
from tests.conftest import TEST_MAC


def test_shelly_info(client):
    resp = client.get("/shelly")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mac"] == TEST_MAC
    assert data["id"] == f"shellypro3em-{TEST_MAC.lower()}"
    assert data["model"] == "SPEM-003CEBEU"
    assert data["gen"] == 2
    assert data["app"] == "Pro3EM"
    assert data["auth_en"] is False


def test_get_device_info(client):
    resp = client.get("/rpc/Shelly.GetDeviceInfo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mac"] == TEST_MAC
    assert data["app"] == "Pro3EM"


def test_em_get_status(client):
    resp = client.get("/rpc/EM.GetStatus?id=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 0
    assert data["a_act_power"] == 500.0
    assert data["a_voltage"] == 230.5
    assert data["a_current"] == 4.2
    assert data["a_aprt_power"] == 520.0
    assert data["a_pf"] == 0.96
    assert data["a_freq"] == 50.0
    assert data["total_act_power"] == 500.0
    assert data["total_aprt_power"] == 520.0
    assert data["total_current"] == 4.2
    # Phases b and c should be zero-filled
    assert data["b_act_power"] == 0.0
    assert data["c_act_power"] == 0.0


def test_emdata_get_status(client):
    resp = client.get("/rpc/EMData.GetStatus?id=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 0
    assert data["a_total_act_energy"] == 12345.67
    assert data["a_total_act_ret_energy"] == 6789.01
    assert data["total_act"] == 12345.67
    assert data["total_act_ret"] == 6789.01
    # Zero-filled phases
    assert data["b_total_act_energy"] == 0.0
    assert data["c_total_act_ret_energy"] == 0.0


def test_shelly_get_status(client):
    resp = client.get("/rpc/Shelly.GetStatus")
    assert resp.status_code == 200
    data = resp.json()
    assert "sys" in data
    assert data["sys"]["mac"] == TEST_MAC
    assert "em:0" in data
    assert data["em:0"]["total_act_power"] == 500.0
    assert "emdata:0" in data
    assert data["emdata:0"]["total_act"] == 12345.67


def test_em_get_status_negative_power(client, mock_backend):
    """Test that negative power (export) is correctly represented."""
    phase = PhaseData(
        voltage=230.0,
        current=3.0,
        act_power=-700.0,
        aprt_power=700.0,
        pf=-0.99,
        freq=50.0,
        total_act_energy=1000.0,
        total_act_ret_energy=5000.0,
    )
    mock_backend.set_data(
        MeterData(
            phases=[phase],
            total_act_power=-700.0,
            total_aprt_power=700.0,
            total_current=3.0,
            total_act_energy=1000.0,
            total_act_ret_energy=5000.0,
        )
    )

    resp = client.get("/rpc/EM.GetStatus?id=0")
    data = resp.json()
    assert data["a_act_power"] == -700.0
    assert data["total_act_power"] == -700.0


def test_three_phase_data(client, mock_backend):
    """Test 3-phase data is correctly mapped."""
    phases = [
        PhaseData(
            voltage=230.0,
            current=2.0,
            act_power=400.0,
            aprt_power=420.0,
            pf=0.95,
            freq=50.0,
            total_act_energy=1000.0,
            total_act_ret_energy=500.0,
        ),
        PhaseData(
            voltage=231.0,
            current=3.0,
            act_power=600.0,
            aprt_power=630.0,
            pf=0.95,
            freq=50.0,
            total_act_energy=2000.0,
            total_act_ret_energy=1000.0,
        ),
        PhaseData(
            voltage=229.0,
            current=1.0,
            act_power=200.0,
            aprt_power=210.0,
            pf=0.95,
            freq=50.0,
            total_act_energy=3000.0,
            total_act_ret_energy=1500.0,
        ),
    ]
    mock_backend.set_data(
        MeterData(
            phases=phases,
            total_act_power=1200.0,
            total_aprt_power=1260.0,
            total_current=6.0,
            total_act_energy=6000.0,
            total_act_ret_energy=3000.0,
        )
    )

    resp = client.get("/rpc/EM.GetStatus?id=0")
    data = resp.json()
    assert data["a_act_power"] == 400.0
    assert data["b_act_power"] == 600.0
    assert data["c_act_power"] == 200.0
    assert data["total_act_power"] == 1200.0
