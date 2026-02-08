"""Tests for Envoy backend data parsing."""

import pytest

from meter_emulator.backends.envoy import parse_envoy_response

ENVOY_RESPONSE_SINGLE_PHASE = {
    "production": [
        {
            "type": "inverters",
            "activeCount": 10,
            "readingTime": 1700000000,
            "wNow": 2500.0,
            "whLifetime": 50000.0,
        },
        {
            "type": "eim",
            "activeCount": 1,
            "measurementType": "production",
            "readingTime": 1700000000,
            "wNow": 2480.0,
            "whLifetime": 49000.0,
            "rmsVoltage": 231.5,
            "rmsCurrent": 10.7,
            "apprntPwr": 2490.0,
            "pwrFactor": 0.99,
        },
    ],
    "consumption": [
        {
            "type": "eim",
            "activeCount": 1,
            "measurementType": "total-consumption",
            "readingTime": 1700000000,
            "wNow": 3000.0,
            "whLifetime": 80000.0,
            "rmsVoltage": 231.5,
            "rmsCurrent": 13.0,
            "apprntPwr": 3010.0,
            "pwrFactor": 0.99,
        },
        {
            "type": "eim",
            "activeCount": 1,
            "measurementType": "net-consumption",
            "readingTime": 1700000000,
            "wNow": 520.0,
            "whLifetime": 35000.0,
            "rmsVoltage": 231.0,
            "rmsCurrent": 2.3,
            "apprntPwr": 530.0,
            "pwrFactor": 0.98,
        },
    ],
}


def test_parse_single_phase():
    data = parse_envoy_response(ENVOY_RESPONSE_SINGLE_PHASE, phases=1)

    assert len(data.phases) == 1
    phase = data.phases[0]

    # Values should come from net-consumption
    assert phase.act_power == 520.0
    assert phase.voltage == 231.0
    assert phase.current == 2.3
    assert phase.aprt_power == 530.0
    assert phase.pf == 0.98
    assert phase.freq == 50.0
    assert phase.total_act_energy == 35000.0

    # Return energy: production(50000) - total_consumption(80000) + net_consumption(35000) = 5000
    assert phase.total_act_ret_energy == 5000.0

    # Totals
    assert data.total_act_power == 520.0
    assert data.total_current == 2.3


def test_parse_negative_power():
    """When solar exceeds consumption, net-consumption wNow is negative (exporting)."""
    response = {
        "production": [
            {"type": "inverters", "wNow": 3000.0, "whLifetime": 50000.0},
        ],
        "consumption": [
            {
                "type": "eim",
                "measurementType": "total-consumption",
                "wNow": 1000.0,
                "whLifetime": 80000.0,
                "rmsVoltage": 230.0,
                "rmsCurrent": 4.3,
                "apprntPwr": 1000.0,
                "pwrFactor": 1.0,
            },
            {
                "type": "eim",
                "measurementType": "net-consumption",
                "wNow": -2000.0,
                "whLifetime": 10000.0,
                "rmsVoltage": 230.0,
                "rmsCurrent": 8.7,
                "apprntPwr": 2000.0,
                "pwrFactor": -1.0,
            },
        ],
    }

    data = parse_envoy_response(response, phases=1)
    assert data.phases[0].act_power == -2000.0
    assert data.total_act_power == -2000.0


def test_parse_empty_response():
    """Handle missing data gracefully."""
    data = parse_envoy_response({}, phases=1)
    assert data.total_act_power == 0.0
    assert len(data.phases) == 1


ENVOY_RESPONSE_THREE_PHASE = {
    "production": [
        {
            "type": "inverters",
            "wNow": 5000.0,
            "whLifetime": 100000.0,
            "lines": [
                {"wNow": 1700.0, "whLifetime": 34000.0},
                {"wNow": 1700.0, "whLifetime": 33000.0},
                {"wNow": 1600.0, "whLifetime": 33000.0},
            ],
        },
    ],
    "consumption": [
        {
            "type": "eim",
            "measurementType": "total-consumption",
            "wNow": 6000.0,
            "whLifetime": 150000.0,
            "rmsVoltage": 230.0,
            "rmsCurrent": 26.0,
            "apprntPwr": 6000.0,
            "pwrFactor": 1.0,
            "lines": [
                {
                    "wNow": 2000.0,
                    "whLifetime": 50000.0,
                    "rmsVoltage": 230.0,
                    "rmsCurrent": 8.7,
                    "apprntPwr": 2000.0,
                    "pwrFactor": 1.0,
                },
                {
                    "wNow": 2200.0,
                    "whLifetime": 52000.0,
                    "rmsVoltage": 231.0,
                    "rmsCurrent": 9.5,
                    "apprntPwr": 2200.0,
                    "pwrFactor": 1.0,
                },
                {
                    "wNow": 1800.0,
                    "whLifetime": 48000.0,
                    "rmsVoltage": 229.0,
                    "rmsCurrent": 7.8,
                    "apprntPwr": 1800.0,
                    "pwrFactor": 1.0,
                },
            ],
        },
        {
            "type": "eim",
            "measurementType": "net-consumption",
            "wNow": 1000.0,
            "whLifetime": 60000.0,
            "rmsVoltage": 230.0,
            "rmsCurrent": 4.3,
            "apprntPwr": 1000.0,
            "pwrFactor": 1.0,
            "lines": [
                {
                    "wNow": 300.0,
                    "whLifetime": 20000.0,
                    "rmsVoltage": 230.0,
                    "rmsCurrent": 1.3,
                    "apprntPwr": 300.0,
                    "pwrFactor": 1.0,
                },
                {
                    "wNow": 500.0,
                    "whLifetime": 22000.0,
                    "rmsVoltage": 231.0,
                    "rmsCurrent": 2.2,
                    "apprntPwr": 500.0,
                    "pwrFactor": 1.0,
                },
                {
                    "wNow": 200.0,
                    "whLifetime": 18000.0,
                    "rmsVoltage": 229.0,
                    "rmsCurrent": 0.9,
                    "apprntPwr": 200.0,
                    "pwrFactor": 1.0,
                },
            ],
        },
    ],
}


def test_parse_three_phase():
    data = parse_envoy_response(ENVOY_RESPONSE_THREE_PHASE, phases=3)

    assert len(data.phases) == 3

    # Phase A: values from net-consumption lines[0]
    assert data.phases[0].act_power == 300.0
    assert data.phases[0].voltage == 230.0
    assert data.phases[0].current == 1.3
    assert data.phases[0].total_act_energy == 20000.0
    # Return energy A: prod(34000) - cons(50000) + net(20000) = 4000
    assert data.phases[0].total_act_ret_energy == 4000.0

    # Phase B
    assert data.phases[1].act_power == 500.0
    assert data.phases[1].voltage == 231.0
    # Return energy B: prod(33000) - cons(52000) + net(22000) = 3000
    assert data.phases[1].total_act_ret_energy == 3000.0

    # Phase C
    assert data.phases[2].act_power == 200.0
    assert data.phases[2].voltage == 229.0
    # Return energy C: prod(33000) - cons(48000) + net(18000) = 3000
    assert data.phases[2].total_act_ret_energy == 3000.0

    # Totals
    assert data.total_act_power == 1000.0
    assert data.total_current == pytest.approx(1.3 + 2.2 + 0.9, abs=0.01)


def test_parse_no_net_consumption_falls_back():
    """If net-consumption is missing, fall back to total-consumption."""
    response = {
        "production": [
            {"type": "inverters", "wNow": 1000.0, "whLifetime": 10000.0},
        ],
        "consumption": [
            {
                "type": "eim",
                "measurementType": "total-consumption",
                "wNow": 1500.0,
                "whLifetime": 20000.0,
                "rmsVoltage": 230.0,
                "rmsCurrent": 6.5,
                "apprntPwr": 1500.0,
                "pwrFactor": 1.0,
            },
        ],
    }

    data = parse_envoy_response(response, phases=1)
    # Falls back to total-consumption
    assert data.phases[0].act_power == 1500.0
    assert data.total_act_power == 1500.0
