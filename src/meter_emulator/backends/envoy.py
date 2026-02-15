import asyncio
import logging
import time
from typing import Any

import httpx

from meter_emulator.backends.base import Backend, MeterData, PhaseData

logger = logging.getLogger(__name__)


def _find_measurement(
    production: list[dict[str, Any]], measurement_type: str
) -> dict[str, Any] | None:
    """Find a measurement block by type in the Envoy production array."""
    for entry in production:
        if (
            entry.get("measurementType") == measurement_type
            or entry.get("type") == measurement_type
        ):
            return entry
    return None


def parse_envoy_response(data: dict[str, Any], phases: int) -> MeterData:
    """Parse Envoy /production.json response into MeterData.

    Args:
        data: Parsed JSON from /production.json?details=1
        phases: Number of phases to map (1 or 3)
    """
    production_list = data.get("production", [])
    consumption_list = data.get("consumption", [])

    # Find the measurement blocks we need
    net_consumption = _find_measurement(consumption_list, "total-consumption")
    # Try "net-consumption" first — that's the grid meter reading
    net_meter = _find_measurement(consumption_list, "net-consumption")
    production_inverters = _find_measurement(production_list, "inverters")

    # Use net-consumption if available, else fall back to total-consumption
    grid = net_meter or net_consumption

    if grid is None:
        logger.warning("No consumption data found in Envoy response")
        return MeterData()

    if phases == 1:
        phase = PhaseData(
            voltage=grid.get("rmsVoltage", 0.0),
            current=grid.get("rmsCurrent", 0.0),
            act_power=grid.get("wNow", 0.0),
            aprt_power=grid.get("apprntPwr", 0.0),
            pf=grid.get("pwrFactor", 0.0),
            freq=50.0,
            total_act_energy=grid.get("whLifetime", 0.0),
            total_act_ret_energy=_calc_ret_energy(production_inverters, net_consumption, net_meter),
        )
        return MeterData(
            phases=[phase],
            total_act_power=phase.act_power,
            total_aprt_power=phase.aprt_power,
            total_current=phase.current,
            total_act_energy=phase.total_act_energy,
            total_act_ret_energy=phase.total_act_ret_energy,
        )
    else:
        # 3-phase: map per-line data from Envoy "lines" array
        lines = grid.get("lines", [])
        prod_lines = production_inverters.get("lines", []) if production_inverters else []
        cons_lines = net_consumption.get("lines", []) if net_consumption else []
        net_lines = net_meter.get("lines", []) if net_meter else []

        phase_data_list: list[PhaseData] = []
        for i in range(3):
            line = lines[i] if i < len(lines) else {}
            phase = PhaseData(
                voltage=line.get("rmsVoltage", 0.0),
                current=line.get("rmsCurrent", 0.0),
                act_power=line.get("wNow", 0.0),
                aprt_power=line.get("apprntPwr", 0.0),
                pf=line.get("pwrFactor", 0.0),
                freq=50.0,
                total_act_energy=line.get("whLifetime", 0.0),
                total_act_ret_energy=_calc_ret_energy_line(prod_lines, cons_lines, net_lines, i),
            )
            phase_data_list.append(phase)

        total_power = sum(p.act_power for p in phase_data_list)
        total_aprt = sum(p.aprt_power for p in phase_data_list)
        total_curr = sum(p.current for p in phase_data_list)
        total_energy = sum(p.total_act_energy for p in phase_data_list)
        total_ret = sum(p.total_act_ret_energy for p in phase_data_list)

        return MeterData(
            phases=phase_data_list,
            total_act_power=total_power,
            total_aprt_power=total_aprt,
            total_current=total_curr,
            total_act_energy=total_energy,
            total_act_ret_energy=total_ret,
        )


def _calc_ret_energy(
    production: dict[str, Any] | None,
    total_consumption: dict[str, Any] | None,
    net_consumption: dict[str, Any] | None,
) -> float:
    """Calculate return (export) energy from Envoy lifetime counters.

    Formula: production_lifetime - total_consumption_lifetime + net_consumption_lifetime
    """
    prod_wh = production.get("whLifetime", 0.0) if production else 0.0
    cons_wh = total_consumption.get("whLifetime", 0.0) if total_consumption else 0.0
    net_wh = net_consumption.get("whLifetime", 0.0) if net_consumption else 0.0
    return max(0.0, prod_wh - cons_wh + net_wh)


def _calc_ret_energy_line(
    prod_lines: list[dict],
    cons_lines: list[dict],
    net_lines: list[dict],
    index: int,
) -> float:
    """Calculate return energy for a specific phase line."""
    prod_wh = prod_lines[index].get("whLifetime", 0.0) if index < len(prod_lines) else 0.0
    cons_wh = cons_lines[index].get("whLifetime", 0.0) if index < len(cons_lines) else 0.0
    net_wh = net_lines[index].get("whLifetime", 0.0) if index < len(net_lines) else 0.0
    return max(0.0, prod_wh - cons_wh + net_wh)


# Refresh token if it expires within 30 days (same threshold as HA integration)
_TOKEN_REFRESH_THRESHOLD_SECONDS = 30 * 24 * 3600
# Check token expiry once per day
_TOKEN_CHECK_INTERVAL_SECONDS = 24 * 3600


class EnvoyBackend(Backend):
    """Backend that polls an Enphase Envoy for production data."""

    def __init__(self, config: dict) -> None:
        self._host = config["host"]
        self._token: str | None = config.get("token")
        self._poll_interval = config.get("poll_interval", 2.0)
        self._verify_ssl = config.get("verify_ssl", False)
        self._phases = config.get("phases", 1)
        self._username: str | None = config.get("username")
        self._password: str | None = config.get("password")
        self._serial: str | None = config.get("serial")
        self._data = MeterData()
        self._poll_task: asyncio.Task | None = None
        self._refresh_task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None
        self._token_auth: Any = None  # EnvoyTokenAuth instance when credentials are provided
        self._aiohttp_session: Any = None  # aiohttp session for pyenphase token auth

    @property
    def _has_credentials(self) -> bool:
        return all([self._username, self._password, self._serial])

    async def _init_token_auth(self) -> None:
        """Initialize pyenphase token auth and obtain/refresh the token."""
        import aiohttp
        from pyenphase.auth import EnvoyTokenAuth

        self._token_auth = EnvoyTokenAuth(
            self._host,
            cloud_username=self._username,
            cloud_password=self._password,
            envoy_serial=self._serial,
            token=self._token,
        )
        if self._aiohttp_session is None:
            self._aiohttp_session = aiohttp.ClientSession()
        await self._token_auth.setup(self._aiohttp_session)
        self._token = self._token_auth.token
        logger.info(
            "Token obtained via Enlighten (type=%s, expires=%s)",
            self._token_auth.token_type,
            time.strftime("%Y-%m-%d %H:%M", time.localtime(self._token_auth.expire_timestamp)),
        )

    async def _refresh_token(self) -> None:
        """Refresh the token using stored credentials."""
        if self._token_auth is None:
            await self._init_token_auth()
            return
        await self._token_auth.refresh()
        self._token = self._token_auth.token
        logger.info(
            "Token refreshed (expires=%s)",
            time.strftime("%Y-%m-%d %H:%M", time.localtime(self._token_auth.expire_timestamp)),
        )

    async def start(self) -> None:
        self._client = httpx.AsyncClient(verify=self._verify_ssl)

        if self._has_credentials:
            try:
                await self._init_token_auth()
            except Exception:
                logger.exception("Failed to obtain token via Enlighten, will retry on 401")
                if not self._token:
                    logger.warning("No static token — polls will fail until refresh works")

            self._refresh_task = asyncio.create_task(self._token_check_loop())

        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(
            "Envoy backend started — polling %s every %.1fs (auto-refresh=%s)",
            self._host,
            self._poll_interval,
            self._has_credentials,
        )

    async def stop(self) -> None:
        for task in (self._poll_task, self._refresh_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self._client is not None:
            await self._client.aclose()
        if self._aiohttp_session is not None:
            await self._aiohttp_session.close()
        logger.info("Envoy backend stopped")

    def get_meter_data(self) -> MeterData:
        return self._data

    async def _token_check_loop(self) -> None:
        """Periodically check token expiry and refresh if needed."""
        while True:
            await asyncio.sleep(_TOKEN_CHECK_INTERVAL_SECONDS)
            try:
                if self._token_auth is not None:
                    remaining = self._token_auth.expire_timestamp - time.time()
                    if remaining < _TOKEN_REFRESH_THRESHOLD_SECONDS:
                        logger.info(
                            "Token expires in %.1f days, refreshing proactively",
                            remaining / 86400,
                        )
                        await self._refresh_token()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduled token refresh failed")

    async def _poll_loop(self) -> None:
        url = f"https://{self._host}/production.json?details=1"

        while True:
            try:
                if not self._token:
                    logger.warning("No token available, skipping poll")
                    await asyncio.sleep(self._poll_interval)
                    continue

                assert self._client is not None
                headers = {"Authorization": f"Bearer {self._token}"}
                resp = await self._client.get(url, headers=headers, timeout=10.0)

                if resp.status_code == 401 and self._has_credentials:
                    logger.warning("Got 401 from Envoy, refreshing token")
                    try:
                        await self._refresh_token()
                        headers = {"Authorization": f"Bearer {self._token}"}
                        resp = await self._client.get(url, headers=headers, timeout=10.0)
                    except Exception:
                        logger.exception("Token refresh after 401 failed")

                resp.raise_for_status()
                data = resp.json()
                self._data = parse_envoy_response(data, self._phases)
                logger.debug("Envoy poll OK: total_power=%.1f W", self._data.total_act_power)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Envoy poll failed")

            await asyncio.sleep(self._poll_interval)
