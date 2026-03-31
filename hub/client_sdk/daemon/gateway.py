"""Local Gateway Daemon - interactive CLI or code API mode."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Optional, List, Any

import httpx
from rich.console import Console
from rich.panel import Panel

from ..config import HUB_URL, API_V1_PREFIX
from ..core.connector import HubConnector
from ..tunnel.manager import TunnelManager
from ..webhook.server import WebhookServer, set_gateway_instance


console = Console(force_terminal=True)


class LocalGatewayDaemon:
    def __init__(
        self,
        agent_id: str,
        local_port: int = 8000,
        hub_url: str = HUB_URL,
        identity_path: str = "identity.md",
        gateway_instance: Optional[object] = None,
    ):
        self.agent_id = agent_id
        self.local_port = local_port
        self.hub_url = hub_url
        self.identity_path = identity_path

        self.connector = HubConnector(
            agent_id=agent_id,
            local_port=local_port,
            hub_url=hub_url,
            identity_path=identity_path,
        )

        self.webhook_server = WebhookServer(
            port=local_port,
            task_handler=self._handle_incoming_task,
        )

        if gateway_instance is not None:
            set_gateway_instance(gateway_instance)

        self.tunnel_manager = TunnelManager(port=local_port)

        self._webhook_task: Optional[asyncio.Task] = None
        self._running = False
        self._public_url: Optional[str] = None

    async def _start_webhook_background(self):
        self._running = True
        import uvicorn
        config = uvicorn.Config(
            self.webhook_server.app,
            host="0.0.0.0",
            port=self.local_port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    def _handle_incoming_task(self, task_type: str, task_context: dict) -> Optional[dict]:
        console.print(f"\n[yellow]Incoming Task:[/yellow] {task_type}")
        console.print(f"Context: {task_context}")
        return {"status": "received", "note": "Implement custom handler"}

    async def _initialize_and_connect(self) -> str:
        self._webhook_task = asyncio.create_task(self._start_webhook_background())
        await asyncio.sleep(1)

        console.print("[cyan]Starting tunnel...[/cyan]")
        self._public_url = await self.tunnel_manager.start(self.local_port)
        console.print(f"[green]Tunnel established:[/green] {self._public_url}")

        await self.connector._load_identity()
        await self.connector.publish(contact_endpoint=f"{self._public_url}/api/webhook")

        console.print(f"[green]Agent '{self.agent_id}' registered with Hub[/green]")
        return self._public_url

    async def interactive_cli_mode(self):
        await self._initialize_and_connect()

        welcome_panel = Panel(
            f"[bold green]AgentHub V1.5 Daemon[/bold green]\n\n"
            f"Agent ID: {self.agent_id}\n"
            f"Public URL: {self._public_url}\n"
            f"Status: [green]Online[/green]",
            title="[bold blue]Welcome[/bold blue]",
            border_style="blue",
        )
        console.print(welcome_panel)

        console.print("\n[dim]Available commands:[/dim]")
        console.print("  /search <query>  - Search for collaborators")
        console.print("  /status          - Show current status")
        console.print("  /help            - Show this help")
        console.print("  /quit            - Shutdown daemon\n")

        while self._running:
            try:
                user_input = await console.input("\n[bold cyan]>>[/bold cyan] ")
                await self._handle_cli_command(user_input.strip())
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]Shutting down...[/yellow]")
                break
            except Exception as exc:
                console.print(f"[red]Error:[/red] {exc}")

        await self._shutdown()

    async def _handle_cli_command(self, command: str):
        if not command:
            return

        if command in {"/quit", "/exit"}:
            self._running = False
            return

        if command == "/help":
            console.print("\n[bold]Available commands:[/bold]")
            console.print("  /search <query>  - Search for collaborators")
            console.print("  /status          - Show current status")
            console.print("  /help            - Show this help")
            console.print("  /quit            - Shutdown daemon")
            return

        if command == "/status":
            console.print("\n[bold]Agent Status:[/bold]")
            console.print(f"  ID: {self.agent_id}")
            console.print(f"  URL: {self._public_url}")
            console.print("  State: [green]Running[/green]")
            return

        if command.startswith("/search "):
            query = command[8:].strip()
            console.print(f"\n[cyan]Searching:[/cyan] {query}")
            matches = await self.connector.search(query=query)
            if matches:
                from ..cli.prompts import match_prompt_rich
                await match_prompt_rich(matches)
            else:
                console.print("[yellow]No matches found[/yellow]")
            return

        console.print(f"[red]Unknown command:[/red] {command}")
        console.print("Type /help for available commands")

    async def _shutdown(self):
        console.print("\n[yellow]Shutting down daemon...[/yellow]")
        if self._webhook_task and not self._webhook_task.done():
            self._webhook_task.cancel()
            try:
                await self._webhook_task
            except asyncio.CancelledError:
                pass

        await self.tunnel_manager.stop()
        await self.connector.close()
        console.print("[green]Daemon stopped[/green]")

    async def code_api_mode(
        self,
        task_callback: Callable[[str, dict], Any],
        human_in_the_loop: Optional[Callable[[List[dict]], List[int]]] = None,
    ):
        self.webhook_server.task_handler = task_callback
        await self._initialize_and_connect()
        console.print("[green]Daemon running in API mode[/green]")
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self._shutdown()

    async def update_status(self, node_status: str, live_broadcast: Optional[str] = None):
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.hub_url}{API_V1_PREFIX}/status",
                json={
                    "agent_id": self.agent_id,
                    "node_status": node_status,
                    "live_broadcast": live_broadcast,
                },
            )
            response.raise_for_status()
            return response.json()

    async def search_collaborators(self, query: str, domain: Optional[str] = None):
        return await self.connector.search(query=query, domain=domain)


async def start_interactive_daemon(
    agent_id: str,
    hub_url: str = HUB_URL,
    identity_path: str = "identity.md",
):
    daemon = LocalGatewayDaemon(
        agent_id=agent_id,
        hub_url=hub_url,
        identity_path=identity_path,
    )
    await daemon.interactive_cli_mode()
