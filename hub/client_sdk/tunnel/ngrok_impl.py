from __future__ import annotations

from .base import BaseTunnel


class NgrokTunnel(BaseTunnel):
    """Ngrok-based tunnel (global)."""

    def __init__(self, auth_token: str | None = None, region: str = "us"):
        self.auth_token = auth_token
        self.region = region
        self._tunnel = None

    async def start(self, port: int) -> str:
        from pyngrok import ngrok, conf

        if self.auth_token:
            conf.set_default_auth_token(self.auth_token)

        self._tunnel = ngrok.connect(
            addr=port,
            proto="http",
            bind_tls=True,
            options={"region": self.region}
        )

        url = self._tunnel.public_url
        return url.replace("http://", "https://")

    def stop(self) -> None:
        if self._tunnel:
            from pyngrok import ngrok
            ngrok.disconnect(self._tunnel)
            ngrok.kill()
            self._tunnel = None

    @property
    def is_active(self) -> bool:
        return self._tunnel is not None
