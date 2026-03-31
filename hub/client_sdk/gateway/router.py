from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from client_sdk.config import HUB_URL, API_V1_PREFIX
from client_sdk.webhook.sender import P2PSender
from .demand_generator import DemandGenerator, DemandTicket
from .skill_executor import LocalSkillExecutor, SkillExecutionError
from .task_cache import TaskCache
from .openclaw_bridge import OpenClawBridge


def _get_agent_id() -> str | None:
    """
    读取本地 agent_id（网络层身份，上云用）

    agent_id 存储在 ~/.agentspace/.agent_id，用于云端匹配和 P2P 通信。
    与 user_id（业务层身份，仅本地）区分。
    """
    agent_id_file = Path.home() / ".agentspace" / ".agent_id"
    try:
        return agent_id_file.read_text(encoding="utf-8").strip()
    except Exception:
        return None


class UniversalResourceGateway:
    """
    Inside-Out ReAct loop with event-driven wakeup.

    Strategy:
    1) Local skills
    2) Local MCP servers
    3) Global bounty via Hub + async wait
    """

    def __init__(self, config_path: Path | None = None):
        self.config = self._load_agentspace_config(config_path)
        self._delivery_events: dict[str, asyncio.Event] = {}
        self._delivery_results: dict[str, str] = {}
        self._sender = P2PSender()
        self._skill_executor = LocalSkillExecutor(config_path)
        self._task_cache = TaskCache()
        self._bridge = OpenClawBridge()
        self._background_tasks = set()  # Prevent GC of background tasks
        # 👈 [新增] 从配置中获取公网隧道 URL
        self.public_base_url = self.config.get("public_tunnel_url") if self.config else None

    async def resolve_resource(self, error: Any) -> Any:
        """Legacy blocking resolve method (for backward compatibility)."""
        context = {
            "resource_type": getattr(error, "resource_type", "resource"),
            "description": getattr(error, "description", ""),
            "local_skills": self.config.get("local_skills", []),
        }

        result = await self._try_local_skills(context)
        if result is not None:
            return result

        return await self._try_global_bounty(context)

    async def publish_bounty_in_background(self, error: Any, original_task: str, user_id: str = "default_user") -> str:
        """
        Fire & Forget mode: Publish bounty in background and return immediately.

        This is the new non-blocking method that enables async workflow:
        1. Try local skills first
        2. Publish to Hub if no local skill available
        3. Spawn background task to wait for delivery
        4. Return demand_id immediately

        V1.6.3 更新：
        - user_id: 业务层身份，仅存本地 TaskCache（用于跨时空唤醒）
        - seeker_id: 网络层身份（agent_id），上云用于匹配和 P2P 通信

        Args:
            error: The ResourceMissingError that triggered this.
            original_task: The original task context for wake-up notification.
            user_id: 用户 ID（仅存本地，不上云）

        Returns:
            The demand_id of the published bounty.
        """
        print("[DEBUG-PUBLISH] >>> ENTER publish_bounty_in_background")
        print(f"[DEBUG-PUBLISH] error: {error}")
        print(f"[DEBUG-PUBLISH] original_task: {original_task}")
        print(f"[DEBUG-PUBLISH] user_id: {user_id}")

        # V1.6.3: 获取 agent_id 作为 seeker_id（网络层身份，上云）
        agent_id = _get_agent_id()
        print(f"[DEBUG-PUBLISH] agent_id (seeker_id for cloud): {agent_id}")

        context = {
            "resource_type": getattr(error, "resource_type", "resource"),
            "description": getattr(error, "description", ""),
            "original_task": original_task,
            "user_id": user_id,        # V1.6: 存入本地缓存（业务层）
            "seeker_id": agent_id,     # V1.6.3: 上云用（网络层 = agent_id）
            "local_skills": self.config.get("local_skills", []),
        }

        print(f"[DEBUG-PUBLISH] context: {context}")

        # 1. Try local skills first
        print("[DEBUG-PUBLISH] Checking local skills...")
        result = await self._try_local_skills(context)
        if result is not None:
            print(f"[DEBUG-PUBLISH] Local skill handled: {result}")
            return f"本地技能已处理: {result}"
        print("[DEBUG-PUBLISH] No local skill found, publishing to Hub...")

        # 2. Generate and publish ticket
        generator = DemandGenerator()
        ticket = await generator.generate_ticket(context)

        # 3. Save task context for cross-temporal wake-up
        self._task_cache.save_task(ticket.demand_id, context)

        # 4. Publish to Hub
        await self._publish_to_hub(ticket)

        # 5. Spawn background task to wait for delivery
        task = asyncio.create_task(
            self._wait_for_delivery_async(ticket.demand_id, original_task)
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return ticket.demand_id

    async def _wait_for_delivery_async(self, demand_id: str, original_task: str) -> None:
        """
        Background task that waits for delivery and triggers wake-up notification.

        This runs in the background after the bounty is published.
        When delivery arrives, it notifies OpenClaw with the original task context.

        Args:
            demand_id: The demand ID to wait for.
            original_task: The original task context for the wake-up message.
        """
        delivery_event = asyncio.Event()
        self._delivery_events[demand_id] = delivery_event

        # Wait for delivery (could be minutes or hours)
        await delivery_event.wait()

        file_path = self._delivery_results.get(demand_id)

        # Clean up
        self._delivery_events.pop(demand_id, None)
        self._delivery_results.pop(demand_id, None)

        if file_path:
            # Update task cache
            task_ctx = self._task_cache.get_task(demand_id)
            if task_ctx:
                self._task_cache.update_status(
                    demand_id,
                    "completed",
                    result_file=file_path,
                    provider_id="unknown",  # Will be updated by webhook
                )

            # Trigger wake-up notification to OpenClaw
            await self._bridge.notify_delivery(
                demand_id=demand_id,
                file_path=file_path,
                provider_id=task_ctx.provider_id if task_ctx else "unknown",
                resource_type=task_ctx.resource_type if task_ctx else "resource",
            )
        else:
            # No delivery received (timeout or error)
            if task_ctx := self._task_cache.get_task(demand_id):
                await self._bridge.notify_error(
                    demand_id=demand_id,
                    error_message="未在规定时间内收到交付",
                    resource_type=task_ctx.resource_type,
                )
                self._task_cache.update_status(demand_id, "failed")

    async def _try_local_skills(self, context: dict) -> Any:
        """
        Try to resolve using local Python skills.

        Skills are loaded dynamically from the config snapshot.
        """
        skills = self.config.get("local_skills", [])
        if not skills:
            return None

        resource_type = context.get("resource_type", "")
        description = context.get("description", "")

        # Find a matching skill based on resource type or description
        for skill_config in skills:
            skill_name = skill_config.get("name", "")
            skill_path = skill_config.get("path", "")
            skill_desc = skill_config.get("description", "").lower()

            # Simple matching: check if skill name or description relates to need
            if (resource_type.lower() in skill_name.lower() or
                resource_type.lower() in skill_desc or
                any(keyword in skill_desc for keyword in description.lower().split()[:3])):

                try:
                    # Execute the skill
                    result = self._skill_executor.execute(
                        skill_name,
                        skill_path,
                        description=description,
                        resource_type=resource_type,
                    )
                    return result
                except SkillExecutionError:
                    # Skill failed or not applicable, continue to next
                    continue
                except Exception:
                    # Unexpected error, continue
                    continue

        return None

    async def _try_global_bounty(self, context: dict) -> Any:
        generator = DemandGenerator()
        ticket = await generator.generate_ticket(context)

        delivery_event = asyncio.Event()
        self._delivery_events[ticket.demand_id] = delivery_event

        await self._publish_to_hub(ticket)

        await delivery_event.wait()
        file_path = self._delivery_results.get(ticket.demand_id)

        self._delivery_events.pop(ticket.demand_id, None)
        self._delivery_results.pop(ticket.demand_id, None)

        return file_path

    async def _publish_to_hub(self, ticket: DemandTicket) -> None:
        """Best-effort publish of a demand ticket to Hub."""
        print("[DEBUG-PUBLISH] >>> ENTER _publish_to_hub")
        url = f"{HUB_URL}{API_V1_PREFIX}/pending_demands"
        print(f"[DEBUG-PUBLISH] HUB_URL: {HUB_URL}")
        print(f"[DEBUG-PUBLISH] API_V1_PREFIX: {API_V1_PREFIX}")
        print(f"[DEBUG-PUBLISH] Final URL: {url}")

        # 👈 [核心变更] 组装绝对公网收货地址
        if self.public_base_url:
            webhook_url = f"{self.public_base_url}/api/webhook/delivery"
        else:
            webhook_url = ""  # 兜底：空字符串

        print(f"[DEBUG-PUBLISH] public_base_url: {self.public_base_url}")
        print(f"[DEBUG-PUBLISH] webhook_url: {webhook_url}")

        payload = {
            "demand_id": ticket.demand_id,
            "resource_type": ticket.resource_type,
            "description": ticket.description,
            "tags": ticket.tags,
            "seeker_id": ticket.seeker_id,
            "seeker_webhook_url": webhook_url,  # 👈 [新增] 随订单提交
            "created_at": ticket.created_at,
        }
        print(f"[DEBUG-PUBLISH] payload: {payload}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                print(f"[DEBUG-PUBLISH] Response status code: {response.status_code}")
                print(f"[DEBUG-PUBLISH] Response body: {response.text}")
        except Exception as e:
            # Hub may not support pending_demands yet; ignore for now
            print(f"[DEBUG-PUBLISH] Exception occurred: {e}")
            import traceback
            traceback.print_exc()
            pass

    def trigger_delivery(self, demand_id: str, file_path: str) -> None:
        if demand_id in self._delivery_events:
            self._delivery_results[demand_id] = file_path
            self._delivery_events[demand_id].set()

    def _load_agentspace_config(self, config_path: Path | None) -> dict:
        """Load config from agentspace_config.yaml or .env file."""
        config = {}

        # Try YAML/JSON config first
        yaml_path = config_path or (Path.home() / ".agentspace" / "agentspace_config.yaml")
        if yaml_path.exists():
            try:
                text = yaml_path.read_text(encoding="utf-8")
                config = json.loads(text)
            except Exception:
                pass

        # Also load from .env file (supports PUBLIC_TUNNEL_URL)
        env_path = Path.home() / ".agentspace" / ".env"
        if env_path.exists():
            try:
                env_text = env_path.read_text(encoding="utf-8")
                for line in env_text.strip().split("\n"):
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        # Map .env keys to config keys
                        if key == "PUBLIC_TUNNEL_URL":
                            config["public_tunnel_url"] = value
                        elif key == "AGENT_ID":
                            config["agent_id"] = value
                        elif key == "HUB_URL":
                            config["hub_url"] = value
            except Exception:
                pass

        return config
