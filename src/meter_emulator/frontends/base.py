"""Abstract base class for meter emulator frontends."""

from abc import ABC, abstractmethod

from fastapi import APIRouter

from meter_emulator.backends.base import Backend


class Frontend(ABC):
    """A frontend exposes meter data over a specific protocol/API."""

    def __init__(self, backend: Backend, config: dict) -> None:
        self._backend = backend

    @abstractmethod
    def get_router(self) -> APIRouter:
        """Return the APIRouter with this frontend's HTTP endpoints."""

    @abstractmethod
    async def start(self) -> None:
        """Start frontend services (mDNS, etc.)."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop frontend services."""
