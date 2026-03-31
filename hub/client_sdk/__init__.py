"""Agent Universal Hub - Client SDK."""

from .core.connector import HubConnector
from .webhook.server import WebhookServer
from .webhook.sender import P2PSender
from .tunnel.manager import TunnelManager
from .gateway import UniversalResourceGateway, auto_catch_and_route, ResourceMissingError
from .discovery.skill import skill
from .discovery.radar import DiscoveryRadar
from .gateway.skill_executor import LocalSkillExecutor, SkillExecutionError
from .openclaw_integration import (
    auto_catch,
    ResourceMissing,
    check_local_resource,
    get_received_files,
    wait_for_delivery,
)
from .auto_setup import enable_auto_setup, patch_openclaw

__version__ = "1.5.1"
__all__ = [
    # Core components
    "HubConnector",
    "WebhookServer",
    "P2PSender",
    "TunnelManager",
    # Gateway
    "UniversalResourceGateway",
    "auto_catch_and_route",
    "ResourceMissingError",
    # OpenClaw integration (simplified)
    "auto_catch",
    "ResourceMissing",
    "check_local_resource",
    "get_received_files",
    "wait_for_delivery",
    # Auto setup (zero-config)
    "enable_auto_setup",
    "patch_openclaw",
    # Zero-Config discovery
    "skill",
    "DiscoveryRadar",
    "LocalSkillExecutor",
    "SkillExecutionError",
]


async def quick_start(agent_id: str, hub_url: str = "http://localhost:8000") -> HubConnector:
    connector = HubConnector(agent_id=agent_id, hub_url=hub_url)
    await connector.start_and_listen()
    return connector
