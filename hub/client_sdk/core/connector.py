"""HubConnector - SDK bridge to AgentHub."""

from __future__ import annotations

import httpx
from typing import Optional

from ..config import HUB_URL, API_V1_PREFIX
from ..cli.prompts import onboarding_prompt, match_prompt


class HubConnector:
    def __init__(
        self,
        agent_id: str,
        local_port: int = 8000,
        hub_url: str = HUB_URL,
        identity_path: str = "identity.md",
    ):
        self.agent_id = agent_id
        self.local_port = local_port
        self.hub_url = hub_url.rstrip("/")
        self.identity_path = identity_path
        self._http_client: Optional[httpx.AsyncClient] = None
        self._public_url: Optional[str] = None
        self._identity_data: Optional[dict] = None

    @property
    def http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=f"{self.hub_url}{API_V1_PREFIX}",
                timeout=30.0,
            )
        return self._http_client

    async def start_and_listen(self):
        from ..tunnel.manager import TunnelManager

        tunnel_mgr = TunnelManager(port=self.local_port)
        self._public_url = await tunnel_mgr.start(self.local_port)
        print(f"[Tunnel] Public URL: {self._public_url}")

        await self._load_identity()
        confirmed = await onboarding_prompt(self._identity_data)
        if not confirmed:
            print("Cancelled by user")
            return

        await self.publish(contact_endpoint=f"{self._public_url}/api/webhook")
        print(f"Agent '{self.agent_id}' registered")

    async def _load_identity(self) -> dict:
        from pathlib import Path

        identity_path = Path(self.identity_path)
        if not identity_path.exists():
            default_content = f"""# {self.agent_id}

Describe what this agent can do.
"""
            identity_path.write_text(default_content, encoding="utf-8")

        content = identity_path.read_text(encoding="utf-8")
        self._identity_data = {
            "description": content,
            "domain": self._infer_domain(content),
            "intent_type": "ask",
        }
        return self._identity_data

    def _infer_domain(self, description: str) -> str:
        desc_lower = description.lower()
        domain_keywords = {
            "finance": ["股票", "基金", "etf", "债券", "期货"],
            "education": ["教育", "课程", "k-12", "题目"],
            "media": ["视频", "音频", "媒体"],
            "data": ["数据", "数据集", "csv", "json"],
        }
        for domain, keywords in domain_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                return domain
        return "general"

    async def publish(self, contact_endpoint: str, domain: Optional[str] = None, intent_type: str = "ask"):
        payload = {
            "agent_id": self.agent_id,
            "domain": domain or self._identity_data.get("domain", "general"),
            "intent_type": intent_type,
            "contact_endpoint": contact_endpoint,
            "description": self._identity_data["description"],
        }
        response = await self.http_client.post("/publish", json=payload)
        response.raise_for_status()
        return response.json()

    async def search(self, query: str, domain: Optional[str] = None) -> list[dict]:
        payload = {"query": query, "domain": domain}
        response = await self.http_client.post("/search", json=payload)
        response.raise_for_status()
        result = response.json()
        matches = result.get("matches", [])
        if not matches:
            print("[Search] No matches")
            return []
        sorted_indices = await match_prompt(matches)
        return [matches[i] for i in sorted_indices]

    async def report_completed(self, match_token: str):
        response = await self.http_client.post("/task_completed", json={"match_token": match_token})
        response.raise_for_status()
        return response.json()

    async def update_status(self, node_status: str, live_broadcast: Optional[str] = None):
        response = await self.http_client.patch(
            "/status",
            json={
                "agent_id": self.agent_id,
                "node_status": node_status,
                "live_broadcast": live_broadcast,
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        if self._http_client:
            await self._http_client.aclose()
