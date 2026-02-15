#!/usr/bin/env python3
"""Test client for the Shelly Pro 3EM emulator using aioshelly.

Usage:
    poetry run python tools/shelly_client.py [HOST] [PORT]
    poetry run python tools/shelly_client.py -f [HOST] [PORT]

Options:
    -f, --follow    Keep the connection open and print push updates

Defaults to localhost:8080. Requires aioshelly:
    poetry run pip install aioshelly
"""

import argparse
import asyncio
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


async def main(host: str, port: int, follow: bool) -> None:
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
        print(f"  Name:     {info.get('name')}")
        print(f"  ID:       {info.get('id')}")
        print(f"  MAC:      {info.get('mac')}")
        print(f"  Model:    {info.get('model')}")
        print(f"  Gen:      {info.get('gen')}")
        print(f"  Firmware: {info.get('ver')}")
        print(f"  App:      {info.get('app')}")
        print(f"  Profile:  {info.get('profile')}")
        print(f"  Auth:     {info.get('auth_en')}")

        print()
        print("=== Initial Status ===")
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
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.follow))
