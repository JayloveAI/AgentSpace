from __future__ import annotations

import os
from enum import Enum
from typing import Optional

from .base import BaseTunnel
from .cloudflare_impl import CloudflareTunnel
from .frp_impl import FrpTunnel
from .ngrok_impl import NgrokTunnel
from ..config import get_region, get_tunnel_provider


class TunnelProvider(Enum):
    FRP = "frp"
    CLOUDFLARE = "cloudflare"
    NGROK = "ngrok"


class TunnelManager:
    """Tunnel factory and lifecycle manager (strategy pattern)."""

    _strategies = {
        "ngrok": NgrokTunnel,
        "frp": FrpTunnel,
        "cloudflare": CloudflareTunnel,
    }

    @classmethod
    def create_from_env(cls) -> BaseTunnel:
        region = get_region()
        provider = get_tunnel_provider()

        if provider is None:
            provider = "frp" if region == "cn" else "ngrok"

        strategy_class = cls._strategies.get(provider, NgrokTunnel)

        if provider == "ngrok":
            return strategy_class(
                auth_token=os.getenv("NGROK_AUTHTOKEN"),
                region=os.getenv("NGROK_REGION", "us")
            )
        if provider == "frp":
            return strategy_class(
                server_addr=os.getenv("FRP_SERVER_ADDR", "127.0.0.1"),
                server_port=int(os.getenv("FRP_SERVER_PORT", "7000")),
                token=os.getenv("FRP_TOKEN"),
                frp_executable=os.getenv("FRP_EXECUTABLE"),
                agent_id=os.getenv("AGENT_ID")
            )
        return strategy_class()

    def __init__(
        self,
        port: Optional[int] = None,
        tunnel: Optional[BaseTunnel] = None,
        preferred_provider: Optional[TunnelProvider | str] = None,
    ):
        self._port = port
        if tunnel:
            self._tunnel = tunnel
        else:
            if preferred_provider:
                provider_value = (
                    preferred_provider.value
                    if isinstance(preferred_provider, TunnelProvider)
                    else str(preferred_provider)
                )
                strategy_class = self._strategies.get(provider_value, NgrokTunnel)
                if provider_value == "ngrok":
                    self._tunnel = strategy_class(
                        auth_token=os.getenv("NGROK_AUTHTOKEN"),
                        region=os.getenv("NGROK_REGION", "us")
                    )
                elif provider_value == "frp":
                    self._tunnel = strategy_class(
                        server_addr=os.getenv("FRP_SERVER_ADDR", "127.0.0.1"),
                        server_port=int(os.getenv("FRP_SERVER_PORT", "7000")),
                        token=os.getenv("FRP_TOKEN"),
                        frp_executable=os.getenv("FRP_EXECUTABLE"),
                        agent_id=os.getenv("AGENT_ID")
                    )
                else:
                    self._tunnel = strategy_class()
            else:
                self._tunnel = self.create_from_env()
        self._public_url: Optional[str] = None

    async def start(self, port: Optional[int] = None) -> str:
        use_port = port or self._port
        if use_port is None:
            raise ValueError("Port is required to start tunnel")
        self._public_url = await self._tunnel.start(use_port)
        return self._public_url

    async def stop(self) -> None:
        if self._tunnel:
            self._tunnel.stop()

    @property
    def public_url(self) -> Optional[str]:
        return self._public_url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import asyncio
        asyncio.run(self.stop())

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
