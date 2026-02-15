"""Shelly Pro 3EM frontend — HTTP API, response models, and mDNS advertisement."""

import asyncio
import logging
import socket
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

from meter_emulator.backends.base import Backend, MeterData
from meter_emulator.frontends.base import Frontend

logger = logging.getLogger(__name__)

# ── Shelly device constants ──────────────────────────────────────────

SHELLY_MODEL = "SPEM-003CEBEU"
SHELLY_GEN = 2
SHELLY_APP = "Pro3EM"
SHELLY_FW_VER = "1.4.4-g6d2a586"
SHELLY_FW_ID = "20241011-114455/1.4.4-g6d2a586"


# ── Response builders ────────────────────────────────────────────────


def device_info(mac: str) -> dict[str, Any]:
    """Build Shelly device info response."""
    device_id = f"shellypro3em-{mac.lower()}"
    return {
        "name": "Shelly Pro 3EM Emulator",
        "id": device_id,
        "mac": mac,
        "slot": 0,
        "model": SHELLY_MODEL,
        "gen": SHELLY_GEN,
        "fw_id": SHELLY_FW_ID,
        "ver": SHELLY_FW_VER,
        "app": SHELLY_APP,
        "profile": "triphase",
        "auth_en": False,
        "auth_domain": None,
    }


def _phase_key(index: int) -> str:
    """Return phase letter for index: 0->a, 1->b, 2->c."""
    return chr(ord("a") + index)


def em_get_status(data: MeterData) -> dict[str, Any]:
    """Build EM.GetStatus response (real-time power)."""
    result: dict[str, Any] = {"id": 0}

    for i, phase in enumerate(data.phases):
        key = _phase_key(i)
        result[f"{key}_current"] = round(phase.current, 3)
        result[f"{key}_voltage"] = round(phase.voltage, 1)
        result[f"{key}_act_power"] = round(phase.act_power, 1)
        result[f"{key}_aprt_power"] = round(phase.aprt_power, 1)
        result[f"{key}_pf"] = round(phase.pf, 2)
        result[f"{key}_freq"] = round(phase.freq, 1)

    # Fill missing phases with zeros for a proper 3EM response
    for i in range(len(data.phases), 3):
        key = _phase_key(i)
        result[f"{key}_current"] = 0.0
        result[f"{key}_voltage"] = 0.0
        result[f"{key}_act_power"] = 0.0
        result[f"{key}_aprt_power"] = 0.0
        result[f"{key}_pf"] = 0.0
        result[f"{key}_freq"] = 0.0

    result["n_current"] = 0.0
    result["total_current"] = round(data.total_current, 3)
    result["total_act_power"] = round(data.total_act_power, 1)
    result["total_aprt_power"] = round(data.total_aprt_power, 1)
    result["user_calibrated_phase"] = []

    return result


def emdata_get_status(data: MeterData) -> dict[str, Any]:
    """Build EMData.GetStatus response (cumulative energy)."""
    result: dict[str, Any] = {"id": 0}

    for i, phase in enumerate(data.phases):
        key = _phase_key(i)
        result[f"{key}_total_act_energy"] = round(phase.total_act_energy, 2)
        result[f"{key}_total_act_ret_energy"] = round(phase.total_act_ret_energy, 2)

    for i in range(len(data.phases), 3):
        key = _phase_key(i)
        result[f"{key}_total_act_energy"] = 0.0
        result[f"{key}_total_act_ret_energy"] = 0.0

    result["total_act"] = round(data.total_act_energy, 2)
    result["total_act_ret"] = round(data.total_act_ret_energy, 2)

    return result


def shelly_get_config(mac: str) -> dict[str, Any]:
    """Build Shelly.GetConfig response."""
    return {
        "em:0": {
            "id": 0,
            "name": None,
            "blink_mode_selector": "active_energy",
            "ct_type": "120A",
            "monitor_phase_sequence": False,
            "phase_selector": "all",
            "reverse": {},
        },
        "emdata:0": {},
        "sys": {
            "device": {
                "mac": mac,
                "name": "Shelly Pro 3EM Emulator",
                "fw_id": SHELLY_FW_ID,
                "profile": "triphase",
                "discoverable": True,
                "eco_mode": False,
                "addon_type": None,
            },
        },
    }


def shelly_get_status(data: MeterData, mac: str) -> dict[str, Any]:
    """Build Shelly.GetStatus response (full device status)."""
    return {
        "sys": {
            "mac": mac,
            "restart_required": False,
            "available_updates": {},
        },
        "em:0": em_get_status(data),
        "emdata:0": emdata_get_status(data),
    }


# ── mDNS advertiser ─────────────────────────────────────────────────


class _MdnsAdvertiser:
    """Advertises the emulator as a Shelly device via mDNS."""

    def __init__(self, mac: str, port: int) -> None:
        self._mac = mac
        self._port = port
        self._aiozc: AsyncZeroconf | None = None
        self._services: list[ServiceInfo] = []

    async def start(self) -> None:
        device_id = f"shellypro3em-{self._mac.lower()}"
        hostname = socket.gethostname()

        # Resolve local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()

        properties = {
            "id": device_id,
            "mac": self._mac,
            "arch": "esp32",
            "gen": "2",
            "app": "Pro3EM",
        }
        common = {
            "addresses": [socket.inet_aton(local_ip)],
            "port": self._port,
            "properties": properties,
            "server": f"{hostname}.local.",
        }

        # Real Shelly Gen2 devices advertise both _http._tcp and _shelly._tcp
        self._services = [
            ServiceInfo("_http._tcp.local.", f"{device_id}._http._tcp.local.", **common),
            ServiceInfo("_shelly._tcp.local.", f"{device_id}._shelly._tcp.local.", **common),
        ]

        logger.info("mDNS: creating AsyncZeroconf...")
        self._aiozc = AsyncZeroconf()
        for svc in self._services:
            logger.info("mDNS: registering %s...", svc.type)
            await asyncio.wait_for(self._aiozc.async_register_service(svc), timeout=10)
        logger.info("mDNS: registered %s at %s:%d", device_id, local_ip, self._port)

    async def stop(self) -> None:
        if self._aiozc and self._services:
            for svc in self._services:
                await self._aiozc.async_unregister_service(svc)
            await self._aiozc.async_close()
            logger.info("mDNS: unregistered services")


# ── Frontend ─────────────────────────────────────────────────────────


def _generate_mac() -> str:
    """Generate a stable MAC from the hostname.

    Using the hostname ensures the same MAC across restarts, avoiding
    orphaned mDNS entries from previously random MACs.
    """
    import hashlib

    return hashlib.md5(socket.gethostname().encode()).hexdigest()[:12].upper()


class ShellyFrontend(Frontend):
    """Shelly Pro 3EM frontend — serves the Shelly HTTP API and advertises via mDNS."""

    def __init__(self, backend: Backend, config: dict) -> None:
        super().__init__(backend, config)
        self._mac: str = config.get("mac") or _generate_mac()
        self._phases: int = config.get("phases", 1)
        self._mdns_enabled: bool = config.get("mdns", True)
        self._port: int = config.get("port", 80)
        self._router = self._build_router()
        self._mdns: _MdnsAdvertiser | None = None

    def get_router(self) -> APIRouter:
        return self._router

    async def start(self) -> None:
        if self._mdns_enabled:
            self._mdns = _MdnsAdvertiser(self._mac, self._port)
            await self._mdns.start()

    async def stop(self) -> None:
        if self._mdns:
            await self._mdns.stop()

    @property
    def mac(self) -> str:
        return self._mac

    def _build_router(self) -> APIRouter:
        router = APIRouter()
        backend = self._backend
        mac = self._mac

        @router.get("/shelly")
        async def shelly_info():
            """Device info endpoint."""
            return device_info(mac)

        @router.get("/rpc/Shelly.GetDeviceInfo")
        async def get_device_info():
            """RPC device info endpoint."""
            return device_info(mac)

        @router.get("/rpc/EM.GetStatus")
        async def em_status(id: int = 0):
            """Real-time per-phase power data."""
            data = backend.get_meter_data()
            return em_get_status(data)

        @router.get("/rpc/EMData.GetStatus")
        async def emdata_status(id: int = 0):
            """Cumulative energy totals."""
            data = backend.get_meter_data()
            return emdata_get_status(data)

        @router.get("/rpc/Shelly.GetStatus")
        async def shelly_status():
            """Full device status."""
            data = backend.get_meter_data()
            return shelly_get_status(data, mac)

        # Method dispatch table for JSON-RPC
        device_id = f"shellypro3em-{mac.lower()}"

        def _handle_rpc_method(method: str, params: dict[str, Any] | None) -> Any:
            """Dispatch an RPC method and return the result."""
            data = backend.get_meter_data()
            if method == "Shelly.GetDeviceInfo":
                return device_info(mac)
            if method == "Shelly.GetStatus":
                return shelly_get_status(data, mac)
            if method == "EM.GetStatus":
                return em_get_status(data)
            if method == "EMData.GetStatus":
                return emdata_get_status(data)
            if method == "Shelly.GetConfig":
                return shelly_get_config(mac)
            if method == "Shelly.GetComponents":
                return {"components": [], "cfg_rev": 0, "offset": 0, "total": 0}
            return None

        @router.websocket("/rpc")
        async def websocket_rpc(ws: WebSocket):
            """Shelly Gen2 JSON-RPC 2.0 over WebSocket."""
            await ws.accept()
            logger.info("WebSocket /rpc: client connected")
            try:
                while True:
                    msg = await ws.receive_json()
                    method = msg.get("method", "")
                    params = msg.get("params")
                    msg_id = msg.get("id")
                    src = msg.get("src", "")

                    logger.info("WebSocket RPC: method=%s id=%s src=%s", method, msg_id, src)

                    result = _handle_rpc_method(method, params)
                    if result is not None:
                        response = {
                            "id": msg_id,
                            "src": device_id,
                            "dst": src,
                            "result": result,
                        }
                    else:
                        response = {
                            "id": msg_id,
                            "src": device_id,
                            "dst": src,
                            "error": {
                                "code": -114,
                                "message": f"Method {method} failed: Method not found!",
                            },
                        }
                    await ws.send_json(response)
            except WebSocketDisconnect:
                logger.info("WebSocket /rpc: client disconnected")

        return router
