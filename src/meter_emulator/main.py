"""FastAPI application for the meter emulator."""

import argparse
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from meter_emulator.backends import create_backend
from meter_emulator.config import load_config
from meter_emulator.frontends import create_frontend

logger = logging.getLogger("meter_emulator")

# Module-level config path, set before app creation
_config_path: str = "/app/config.yaml"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config(_config_path)

    # Create and start backend
    backend_type = config.backend.type
    backend_conf = {}
    if backend_type == "envoy" and config.backend.envoy:
        backend_conf = config.backend.envoy.model_dump()
        backend_conf["phases"] = config.frontend.shelly.phases

    backend = create_backend(backend_type, backend_conf)
    logger.info("Starting backend (%s)...", backend_type)
    await backend.start()
    logger.info("Backend started")

    # Create and start frontend
    frontend_type = config.frontend.type
    frontend_conf = config.frontend.shelly.model_dump()
    frontend_conf["port"] = config.server.port

    frontend = create_frontend(frontend_type, backend, frontend_conf)
    app.include_router(frontend.get_router())
    logger.info("Starting frontend (%s)...", frontend_type)
    await frontend.start()
    logger.info("Frontend started")

    logger.info(
        "Meter emulator ready — frontend=%s, backend=%s",
        frontend_type,
        backend_type,
    )

    yield

    # Shutdown
    await frontend.stop()
    await backend.stop()


app = FastAPI(title="Meter Emulator", lifespan=lifespan)


def run() -> None:
    """CLI entry point."""
    global _config_path

    parser = argparse.ArgumentParser(description="Meter Emulator")
    parser.add_argument(
        "-c",
        "--config",
        default="/app/config.yaml",
        help="Path to config YAML file",
    )
    args = parser.parse_args()

    _config_path = args.config
    config = load_config(_config_path)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run(app, host=config.server.host, port=config.server.port)
