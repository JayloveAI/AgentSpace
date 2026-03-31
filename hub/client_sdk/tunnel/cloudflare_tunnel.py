"""
Cloudflare Tunnel Support for AgentHub V1.5
============================================
Zero-config tunneling using trycloudflare

Requirements:
- pip install trycloudflare

Usage:
    from client_sdk.tunnel.cloudflare_tunnel import start_cloudflare_tunnel

    url = await start_cloudflare_tunnel(8000)
    print(f"Public URL: {url}")
"""
import asyncio
from typing import Optional


async def start_cloudflare_tunnel(
    port: int = 8000,
    max_retries: int = 3
) -> str:
    """
    Start Cloudflare Tunnel using trycloudflare

    Args:
        port: Local port to expose
        max_retries: Maximum retry attempts

    Returns:
        Public URL (https://xxx.trycloudflare.com)

    Raises:
        ImportError: If trycloudflare is not installed
        RuntimeError: If tunnel fails to start after retries
    """
    try:
        from trycloudflare import tunnel
    except ImportError:
        raise ImportError(
            "trycloudflare is not installed. "
            "Install it with: pip install trycloudflare"
        )

    for attempt in range(max_retries):
        try:
            # Start tunnel (this is a blocking call in trycloudflare)
            # We run it in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                None,
                lambda: tunnel(port)
            )
            return url

        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"Failed to start Cloudflare Tunnel after {max_retries} attempts: {e}"
                )
            await asyncio.sleep(2 ** attempt)  # Exponential backoff


async def check_cloudflare_availability() -> bool:
    """
    Check if Cloudflare Tunnel (trycloudflare) is available

    Returns:
        True if trycloudflare can be imported and used
    """
    try:
        import trycloudflare
        return True
    except ImportError:
        return False


class CloudflareTunnelManager:
    """
    Cloudflare Tunnel Manager with lifecycle management

    Example:
        manager = CloudflareTunnelManager(port=8000)
        url = await manager.start()
        print(f"Tunnel URL: {url}")

        # ... use tunnel ...

        await manager.stop()
    """

    def __init__(self, port: int = 8000):
        self.port = port
        self._url: Optional[str] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> str:
        """
        Start Cloudflare Tunnel

        Returns:
            Public URL
        """
        if self._url:
            return self._url

        self._url = await start_cloudflare_tunnel(self.port)
        return self._url

    async def stop(self):
        """
        Stop Cloudflare Tunnel

        Note: trycloudflare tunnels are automatically stopped
        when the process exits. This method clears the state.
        """
        self._url = None
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    @property
    def url(self) -> Optional[str]:
        """Get current tunnel URL"""
        return self._url

    def is_active(self) -> bool:
        """Check if tunnel is active"""
        return self._url is not None


# Convenience function for quick start
async def quick_start(port: int = 8000) -> str:
    """
    Quick start Cloudflare Tunnel

    Example:
        from client_sdk.tunnel.cloudflare_tunnel import quick_start

        url = await quick_start(8000)
        print(f"Public URL: {url}")
    """
    return await start_cloudflare_tunnel(port)
