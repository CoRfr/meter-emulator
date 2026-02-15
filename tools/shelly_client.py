#!/usr/bin/env python3
"""Test client for the Shelly Pro 3EM emulator using aioshelly.

Usage:
    poetry run python tools/shelly_client.py [HOST] [PORT]
    poetry run python tools/shelly_client.py -f [HOST] [PORT]
    poetry run python tools/shelly_client.py -v [HOST] [PORT]

Options:
    -f, --follow    Keep the connection open and print push updates
    -v, --verbose   Show raw WebSocket frames (sent/received JSON)

Defaults to localhost:8080. Requires aioshelly:
    poetry run pip install aioshelly
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime

import aiohttp
from aioshelly.common import ConnectionOptions
from aioshelly.rpc_device import RpcDevice, RpcUpdateType


def print_em_status(status: dict) -> None:
    """Print EM and EMData status from a device status dict."""
    if "em:0" in status:
        em = status["em:0"]
        parts = []
        for phase in ("a", "b", "c"):
            power = em.get(f"{phase}_act_power", 0.0)
            voltage = em.get(f"{phase}_voltage", 0.0)
            current = em.get(f"{phase}_current", 0.0)
            if voltage > 0 or power != 0:
                parts.append(f"{phase.upper()}:{power:>7.1f}W {voltage:.0f}V {current:.2f}A")
        total = em.get("total_act_power", 0.0)
        parts.append(f"Total:{total:>7.1f}W")
        print(f"  EM  | {' | '.join(parts)}")

    if "emdata:0" in status:
        emd = status["emdata:0"]
        total = emd.get("total_act", 0.0)
        ret = emd.get("total_act_ret", 0.0)
        print(f"  EMD | total={total:.2f} Wh  ret={ret:.2f} Wh")


def setup_verbose_logging() -> None:
    """Enable DEBUG logging on aioshelly to show raw WebSocket frames."""
    fmt = logging.Formatter("  %(name)s %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)

    for name in ("aioshelly.rpc_device.wsrpc", "aioshelly.rpc_device.device"):
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG)
        log.addHandler(handler)


async def main(host: str, port: int, follow: bool, verbose: bool) -> None:
    if verbose:
        setup_verbose_logging()

    print(f"Connecting to {host}:{port}...")
    options = ConnectionOptions(host, port=port)

    async with aiohttp.ClientSession() as session:
        update_event = asyncio.Event()

        def on_update(device: RpcDevice, update_type: RpcUpdateType) -> None:
            update_event.set()

        device = RpcDevice(None, session, options)
        device.subscribe_updates(on_update)
        await device.initialize()

        info = device.shelly
        print()
        print("=== Device Info ===")
        for key in ("name", "id", "mac", "model", "gen", "ver", "app", "profile", "auth_en"):
            print(f"  {key:12s} {json.dumps(info.get(key))}")

        print()
        print("=== Config ===")
        print(json.dumps(device.config, indent=2))

        print()
        print("=== Status ===")
        print(json.dumps(device.status, indent=2))

        print()
        print("=== Summary ===")
        print_em_status(device.status)

        if not follow:
            await device.shutdown()
            print()
            print("OK — emulator responds correctly to aioshelly RpcDevice")
            return

        print()
        print("=== Following updates (Ctrl+C to stop) ===", flush=True)
        try:
            while True:
                update_event.clear()
                await update_event.wait()
                ts = datetime.now().strftime("%H:%M:%S")
                if verbose:
                    print(f"[{ts}] Raw status:")
                    print(json.dumps(device.status, indent=2), flush=True)
                else:
                    print(f"[{ts}] Update received:", flush=True)
                    print_em_status(device.status)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await device.shutdown()
            print("\nDisconnected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shelly Pro 3EM emulator test client")
    parser.add_argument("host", nargs="?", default="localhost", help="Emulator host")
    parser.add_argument("port", nargs="?", type=int, default=8080, help="Emulator port")
    parser.add_argument(
        "-f", "--follow", action="store_true", help="Keep connection and print push updates"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show raw WebSocket frames")
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.follow, args.verbose))
