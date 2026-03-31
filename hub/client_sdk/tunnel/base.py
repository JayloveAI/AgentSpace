from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTunnel(ABC):
    """Tunnel strategy interface."""

    @abstractmethod
    async def start(self, port: int) -> str:
        """Start tunnel and return public HTTPS URL."""

    @abstractmethod
    def stop(self) -> None:
        """Stop tunnel and release resources."""

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Return whether the tunnel is active."""
