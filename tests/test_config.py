"""Tests for configuration loading."""

import textwrap

import pytest

from meter_emulator.config import EnvoyConfig, load_config


def test_load_full_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        server:
          host: "127.0.0.1"
          port: 8080
        frontend:
          type: shelly
          shelly:
            mac: "112233445566"
            phases: 1
            mdns: false
        backend:
          type: envoy
          envoy:
            host: "10.0.0.1"
            token: "test-token"
            poll_interval: 5.0
            verify_ssl: true
    """)
    )

    config = load_config(config_file)
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 8080
    assert config.frontend.type == "shelly"
    assert config.frontend.shelly.mac == "112233445566"
    assert config.frontend.shelly.phases == 1
    assert config.frontend.shelly.mdns is False
    assert config.backend.type == "envoy"
    assert config.backend.envoy is not None
    assert config.backend.envoy.host == "10.0.0.1"
    assert config.backend.envoy.token == "test-token"
    assert config.backend.envoy.poll_interval == 5.0
    assert config.backend.envoy.verify_ssl is True


def test_load_minimal_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        backend:
          type: envoy
          envoy:
            host: "10.0.0.1"
            token: "tok"
    """)
    )

    config = load_config(config_file)
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 80
    assert config.frontend.type == "shelly"
    assert config.frontend.shelly.mdns is True
    assert len(config.frontend.shelly.mac) == 12


def test_env_var_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_ENVOY_TOKEN", "my-jwt-token-123")

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        backend:
          type: envoy
          envoy:
            host: "10.0.0.1"
            token: "${TEST_ENVOY_TOKEN}"
    """)
    )

    config = load_config(config_file)
    assert config.backend.envoy.token == "my-jwt-token-123"


def test_env_var_missing_raises(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        backend:
          type: envoy
          envoy:
            host: "10.0.0.1"
            token: "${NONEXISTENT_VAR_12345}"
    """)
    )

    with pytest.raises(ValueError, match="NONEXISTENT_VAR_12345"):
        load_config(config_file)


def test_invalid_phases(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        frontend:
          shelly:
            phases: 2
        backend:
          type: envoy
          envoy:
            host: "10.0.0.1"
            token: "tok"
    """)
    )

    with pytest.raises(Exception, match="phases must be 1 or 3"):
        load_config(config_file)


def test_invalid_mac(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        frontend:
          shelly:
            mac: "ZZZZZZZZZZZZ"
        backend:
          type: envoy
          envoy:
            host: "10.0.0.1"
            token: "tok"
    """)
    )

    with pytest.raises(Exception, match="12 hex characters"):
        load_config(config_file)


def test_mac_normalization(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        frontend:
          shelly:
            mac: "aa:bb:cc:dd:ee:ff"
        backend:
          type: envoy
          envoy:
            host: "10.0.0.1"
            token: "tok"
    """)
    )

    config = load_config(config_file)
    assert config.frontend.shelly.mac == "AABBCCDDEEFF"


def test_envoy_config_with_credentials(tmp_path):
    """Envoy config accepts credentials for auto token refresh."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent("""\
        backend:
          type: envoy
          envoy:
            host: "10.0.0.1"
            username: "user@example.com"
            password: "secret"
            serial: "123456789012"
    """)
    )

    config = load_config(config_file)
    assert config.backend.envoy.username == "user@example.com"
    assert config.backend.envoy.token is None
    assert config.backend.envoy.has_credentials is True


def test_envoy_config_requires_token_or_credentials():
    """EnvoyConfig requires either token or full credentials."""
    with pytest.raises(ValueError, match="token.*username.*password.*serial"):
        EnvoyConfig(host="10.0.0.1")


def test_envoy_config_partial_credentials_require_token():
    """Partial credentials (missing serial) still require a token."""
    with pytest.raises(ValueError, match="token.*username.*password.*serial"):
        EnvoyConfig(host="10.0.0.1", username="user@example.com", password="secret")
