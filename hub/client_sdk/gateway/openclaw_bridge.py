"""OpenClaw bridge for cross-temporal active notification.

This module provides the bridge layer for notifying OpenClaw when resources
are delivered, enabling the "Fire & Forget" pattern with wake-up capability.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class OpenClawBridge:
    """
    OpenClaw local dialogue API bridge.

    Supports multiple notification methods:
    1. OpenClaw SDK (if installed)
    2. Local Webhook (if OpenClaw provides one)
    3. Filesystem signal (universal fallback)

    The bridge automatically detects available methods and uses the best option.
    """

    NOTIFICATION_DIR = Path.home() / ".agentspace" / "notifications"

    def __init__(self, notification_dir: Optional[Path] = None):
        """
        Initialize the OpenClaw bridge.

        Args:
            notification_dir: Custom directory for notification files.
        """
        self._notification_dir = notification_dir or self.NOTIFICATION_DIR
        self._notification_dir.mkdir(parents=True, exist_ok=True)
        self._openclaw_available = self._check_openclaw_sdk()
        self._webhook_url = self._detect_webhook_url()

    def _check_openclaw_sdk(self) -> bool:
        """
        Check if OpenClaw SDK is available.

        Returns:
            True if OpenClaw SDK can be imported.
        """
        try:
            import openclaw  # noqa: F401
            return True
        except ImportError:
            return False

    def _detect_webhook_url(self) -> Optional[str]:
        """
        Detect OpenClaw webhook URL from environment or config.

        Returns:
            Webhook URL if configured, None otherwise.
        """
        import os

        # Check environment variable
        webhook_url = os.getenv("OPENCLAW_WEBHOOK_URL")
        if webhook_url:
            return webhook_url

        # Check config file
        config_file = Path.home() / ".agentspace" / "config.yaml"
        if config_file.exists():
            try:
                import yaml

                with open(config_file, "r") as f:
                    config = yaml.safe_load(f)
                return config.get("openclaw_webhook_url")
            except Exception:
                pass

        return None

    async def notify_delivery(
        self,
        demand_id: str,
        file_path: str,
        provider_id: str,
        resource_type: str = "resource",
    ) -> bool:
        """
        Notify OpenClaw that a resource has been delivered.

        This triggers the "cross-temporal wake-up" - the user is notified
        that the resource they needed earlier has now arrived.

        V1.6 更新：从 TaskCache 读取 user_id 和 original_task
        V1.6 更新：支持中文文件名（ensure_ascii=False）

        Args:
            demand_id: Unique identifier for the demand.
            file_path: Path to the delivered file.
            provider_id: ID of the provider who delivered the resource.
            resource_type: Type of the delivered resource.

        Returns:
            True if notification was sent successfully, False otherwise.
        """
        # 从 TaskCache 读取 user_id 和 original_task
        from .task_cache import TaskCache
        task_cache = TaskCache()
        task_ctx = task_cache.get_task(demand_id)

        if not task_ctx:
            print(f"⚠️ 无主数据: {demand_id}")
            return False

        user_id = task_ctx.user_id
        original_task = task_ctx.original_task

        # ⚠️ [V1.6 新增] 提取文件名并确保编码正确
        filename = Path(file_path).name

        payload = {
            "type": "resource_delivery",
            "demand_id": demand_id,
            "file_path": file_path,
            "filename": filename,  # 新增：独立文件名字段
            "provider_id": provider_id,
            "resource_type": resource_type,
            "user_id": user_id,
            "original_task": original_task,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Try webhook first (Node.js 桥接层)
        if self._webhook_url:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(self._webhook_url, json=payload)
                    if response.status_code == 200:
                        return True
            except Exception:
                pass

        # Fallback to filesystem signal
        notification_file = self._notification_dir / f"{demand_id}.json"
        with open(notification_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        # Also write to "latest" for easy polling
        latest_file = self._notification_dir / "latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return True

    async def notify_expired(self, demand_id: str) -> bool:
        """
        通道二：Hub 过期通知

        当 Hub 判定需求过期时，调用此方法通知 Node.js 发送降级安抚消息。

        Args:
            demand_id: Unique identifier for the demand.

        Returns:
            True if notification was sent successfully, False otherwise.
        """
        from .task_cache import TaskCache
        task_cache = TaskCache()
        task_ctx = task_cache.get_task(demand_id)

        if not task_ctx:
            return False

        user_id = task_ctx.user_id
        original_task = task_ctx.original_task

        # 通知 Node.js 发降级安抚消息
        payload = {
            "type": "demand_expired",
            "demand_id": demand_id,
            "user_id": user_id,
            "original_task": original_task,
            "message": f"非常抱歉，您需要的【{original_task}】数据，情报网蹲守了很久依然没有找到。我先为您撤下该需求，有新线索随时叫我！",
            "timestamp": datetime.utcnow().isoformat()
        }

        # Try webhook first
        if self._webhook_url:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(self._webhook_url, json=payload)
                    if response.status_code == 200:
                        # 删除本地缓存
                        task_cache.delete_task(demand_id)
                        return True
            except Exception:
                pass

        # Fallback to filesystem
        notification_file = self._notification_dir / f"{demand_id}_expired.json"
        with open(notification_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        # 删除本地缓存
        task_cache.delete_task(demand_id)

        return True

    def _format_delivery_message(
        self,
        demand_id: str,
        file_path: str,
        provider_id: str,
        resource_type: str,
    ) -> str:
        """
        Format the delivery notification message.

        Args:
            demand_id: Unique identifier for the demand.
            file_path: Path to the delivered file.
            provider_id: ID of the provider.
            resource_type: Type of resource.

        Returns:
            Formatted message string.
        """
        file_name = Path(file_path).name

        return (
            f"🎉 资源已就绪!\n"
            f"需求 ID: {demand_id}\n"
            f"资源类型: {resource_type}\n"
            f"文件位置: {file_path}\n"
            f"文件名: {file_name}\n"
            f"提供方: {provider_id}\n"
            f"您现在可以使用该文件继续工作了。"
        )

    async def _notify_via_sdk(self, message: str) -> bool:
        """
        Notify via OpenClaw SDK.

        Args:
            message: The notification message.

        Returns:
            True if successful, False otherwise.
        """
        try:
            import openclaw

            # Assuming OpenClaw provides a system message API
            # This may need adjustment based on actual SDK
            if hasattr(openclaw, "send_system_message"):
                await openclaw.send_system_message(
                    role="system",
                    content=message,
                    source="agentspace",
                )
                return True
            elif hasattr(openclaw, "notify"):
                openclaw.notify(message)
                return True
        except Exception as e:
            # Silently fail and try next method
            pass

        return False

    async def _notify_via_webhook(self, message: str) -> bool:
        """
        Notify via OpenClaw webhook.

        Args:
            message: The notification message.

        Returns:
            True if successful, False otherwise.
        """
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    self._webhook_url,
                    json={
                        "type": "resource_delivery",
                        "source": "agentspace",
                        "message": message,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
                return response.status_code == 200
        except Exception:
            return False

    def _notify_via_filesystem(
        self,
        demand_id: str,
        file_path: str,
        provider_id: str,
        message: str,
        resource_type: str,
    ) -> None:
        """
        Notify via filesystem signal (fallback method).

        This writes a notification file that can be polled by OpenClaw
        or other systems. It's the most reliable method as it doesn't
        depend on external services.

        Args:
            demand_id: Unique identifier for the demand.
            file_path: Path to the delivered file.
            provider_id: ID of the provider.
            message: The notification message.
            resource_type: Type of resource.
        """
        notification = {
            "type": "resource_delivery",
            "demand_id": demand_id,
            "file_path": file_path,
            "provider_id": provider_id,
            "resource_type": resource_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Write notification file
        notification_file = self._notification_dir / f"{demand_id}.json"
        with open(notification_file, "w", encoding="utf-8") as f:
            json.dump(notification, f, indent=2, ensure_ascii=False)

        # Also write to "latest" for easy polling
        latest_file = self._notification_dir / "latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(notification, f, indent=2, ensure_ascii=False)

    async def notify_error(
        self,
        demand_id: str,
        error_message: str,
        resource_type: str = "resource",
    ) -> bool:
        """
        Notify OpenClaw that a demand failed.

        Args:
            demand_id: Unique identifier for the demand.
            error_message: Error description.
            resource_type: Type of resource that failed.

        Returns:
            True if notification was sent, False otherwise.
        """
        message = (
            f"⚠️ 资源获取失败\n"
            f"需求 ID: {demand_id}\n"
            f"资源类型: {resource_type}\n"
            f"错误信息: {error_message}\n"
            f"您可能需要手动提供该资源或重试。"
        )

        # Try available notification methods
        if self._openclaw_available:
            if await self._notify_via_sdk(message):
                return True

        if self._webhook_url:
            if await self._notify_via_webhook(message):
                return True

        # Fallback to filesystem
        notification = {
            "type": "demand_failed",
            "demand_id": demand_id,
            "resource_type": resource_type,
            "error_message": error_message,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        error_file = self._notification_dir / f"{demand_id}_error.json"
        with open(error_file, "w", encoding="utf-8") as f:
            json.dump(notification, f, indent=2, ensure_ascii=False)

        return True

    def get_latest_notification(self) -> Optional[dict]:
        """
        Get the latest notification from the filesystem.

        Useful for polling-based systems.

        Returns:
            The latest notification dict, or None if no notification exists.
        """
        latest_file = self._notification_dir / "latest.json"

        if not latest_file.exists():
            return None

        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def clear_notification(self, demand_id: str) -> None:
        """
        Clear a notification after it has been processed.

        Args:
            demand_id: The demand ID to clear.
        """
        notification_file = self._notification_dir / f"{demand_id}.json"

        if notification_file.exists():
            notification_file.unlink()


__all__ = ["OpenClawBridge"]
