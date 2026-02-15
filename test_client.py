#!/usr/bin/env python3
"""Test client for the Shelly Pro 3EM emulator using aioshelly.

Usage:
    poetry run python test_client.py [HOST] [PORT]

Defaults to localhost:8080. Requires aioshelly:
    poetry run pip install aioshelly
"""

import asyncio
import sys

import aiohttp
from aioshelly.common import ConnectionOptions
from aioshelly.rpc_device import RpcDevice


async def main(host: str, port: int) -> None:
    print(f"Connecting to {host}:{port}...")
    options = ConnectionOptions(host, port=port)

    async with aiohttp.ClientSession() as session:
        device = RpcDevice(None, session, options)
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
        print(f"  Auth:     {info.get('auth_en')}")

        status = device.status

        if "em:0" in status:
            em = status["em:0"]
            print()
            print("=== EM Status (real-time power) ===")
            for phase in ("a", "b", "c"):
                power = em.get(f"{phase}_act_power", 0.0)
                voltage = em.get(f"{phase}_voltage", 0.0)
                current = em.get(f"{phase}_current", 0.0)
                pf = em.get(f"{phase}_pf", 0.0)
                if voltage > 0 or power != 0:
                    ph = phase.upper()
                    line = f"  Phase {ph}: {power:>8.1f} W  "
                    line += f"{voltage:>6.1f} V  {current:>.3f} A  PF {pf:.2f}"
                    print(line)
            print(f"  Total:   {em.get('total_act_power', 0.0):>8.1f} W")

        if "emdata:0" in status:
            emd = status["emdata:0"]
            print()
            print("=== EMData Status (cumulative energy) ===")
            for phase in ("a", "b", "c"):
                energy = emd.get(f"{phase}_total_act_energy", 0.0)
                ret = emd.get(f"{phase}_total_act_ret_energy", 0.0)
                if energy > 0 or ret > 0:
                    print(f"  Phase {phase.upper()}: {energy:>12.2f} Wh  (returned: {ret:.2f} Wh)")
            print(f"  Total:   {emd.get('total_act', 0.0):>12.2f} Wh")
            print(f"  Return:  {emd.get('total_act_ret', 0.0):>12.2f} Wh")

        await device.shutdown()
        print()
        print("OK — emulator responds correctly to aioshelly RpcDevice")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    asyncio.run(main(host, port))
