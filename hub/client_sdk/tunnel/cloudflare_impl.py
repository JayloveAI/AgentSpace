from __future__ import annotations

from .base import BaseTunnel
from .ngrok_impl import NgrokTunnel


class CloudflareTunnel(BaseTunnel):
    """Cloudflare Tunnel via trycloudflare (zero-config)."""

    def __init__(self):
        self._tunnel = None

    async def start(self, port: int) -> str:
        try:
            from trycloudflare import tunnel
            self._tunnel = await tunnel(port)
            return self._tunnel
        except ImportError:
            # Fallback to Ngrok if trycloudflare isn't available
            return await NgrokTunnel().start(port)

    def stop(self) -> None:
        self._tunnel = None

    @property
    def is_active(self) -> bool:
        return self._tunnel is not None
