"""Webhook Server - P2P task receiver and file delivery endpoints."""

from __future__ import annotations

import asyncio
import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Callable

import jwt
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..config import HUB_JWT_SECRET, HUB_URL, API_V1_PREFIX
from hub_server.api.contracts import (
    P2PTaskEnvelope,
    P2PAckResponse,
    P2PAddressRequest,
    P2PDeliveryRequest,
)
from client_sdk.core.payload_handler import restore_inbound_payload
from ..security.file_whitelist import FileExtensionWhitelist
from ..gateway.task_cache import TaskCache
from ..gateway.openclaw_bridge import OpenClawBridge
from ..gateway.router import UniversalResourceGateway
from ..gateway.auto_catcher import ResourceMissingError


TaskHandler = Callable[[str, dict], dict | None]

_gateway_instance = None


def set_gateway_instance(gateway):
    global _gateway_instance
    _gateway_instance = gateway


def _generate_local_token() -> str:
    """生成动态 Token 并写入文件"""
    token = secrets.token_hex(32)
    token_file = Path.home() / ".agentspace" / ".local_token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token)
    return token


class WebhookServer:
    def __init__(self, port: int = 8000, task_handler: TaskHandler | None = None):
        self.port = port
        self.task_handler = task_handler
        self.app = FastAPI(title="Agent Webhook Receiver")
        self._task_cache = TaskCache()
        self._bridge = OpenClawBridge()
        self._local_token = _generate_local_token()  # 启动时生成 Token
        self._setup_routes()
        self._setup_middleware()

    def _setup_middleware(self):
        @self.app.middleware("http")
        async def jwt_middleware(request: Request, call_next):
            # 本地端点跳过 JWT 验证（使用动态 Token）
            if request.url.path == "/api/local/trigger_demand":
                return await call_next(request)
            if request.url.path.startswith("/api/local/demand/"):
                return await call_next(request)

            # 信令端点不需要 JWT 验证
            if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json", "/api/webhook/signal"]:
                return await call_next(request)

            if request.url.path == "/api/webhook":
                token = request.headers.get("X-Match-Token")
                if not token:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": "MissingTokenError",
                            "message": "Missing X-Match-Token",
                        },
                    )

                try:
                    payload = jwt.decode(token, HUB_JWT_SECRET, algorithms=["HS256"])
                    request.state.jwt_payload = payload
                except jwt.ExpiredSignatureError:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"error": "TokenExpiredError", "message": "JWT expired"},
                    )
                except jwt.InvalidTokenError as exc:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"error": "InvalidTokenError", "message": str(exc)},
                    )

            return await call_next(request)

    def _setup_routes(self):
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "service": "agent-webhook"}

        # ==========================================
        # 本地 API 端点（供 Node.js OpenClaw 调用）
        # ==========================================

        @self.app.post("/api/local/trigger_demand")
        async def trigger_demand_local(request: Request):
            """本地接单接口 - 供 OpenClaw (Node.js) 调用"""
            # Token 验证
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing token")

            token = auth_header[7:]
            if token != self._local_token:
                raise HTTPException(status_code=403, detail="Invalid token")

            # ⚠️ [V1.6 优化] 强制 UTF-8 解码，避免中文乱码
            try:
                body_bytes = await request.body()
                body = json.loads(body_bytes.decode('utf-8'))
            except UnicodeDecodeError:
                # 回退到标准解析
                body = await request.json()
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

            user_id = body.get("user_id", "default_user")
            original_task = body.get("original_task", "")

            gateway = _gateway_instance or UniversalResourceGateway()
            demand_id = await gateway.publish_bounty_in_background(
                error=ResourceMissingError(
                    resource_type=body.get("resource_type", "resource"),
                    description=body.get("description", "")
                ),
                original_task=original_task,
                user_id=user_id
            )

            return {
                "status": "published",
                "demand_id": demand_id,
                "original_task": original_task
            }

        @self.app.delete("/api/local/demand/{demand_id}")
        async def cancel_demand(demand_id: str, request: Request):
            """用户主动取消需求"""
            # Token 验证
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[7:] != self._local_token:
                raise HTTPException(status_code=403, detail="Invalid token")

            task_ctx = self._task_cache.get_task(demand_id)

            if task_ctx:
                # 1. 删除本地缓存
                self._task_cache.delete_task(demand_id)

                # 2. 通知 Hub 删除云端需求
                asyncio.create_task(self._cancel_hub_demand(demand_id))

            return {"status": "cancelled", "demand_id": demand_id}

        # ==========================================
        # 原有端点
        # ==========================================

        @self.app.post("/api/webhook")
        async def receive_task(envelope: P2PTaskEnvelope, request: Request):
            jwt_payload = request.state.jwt_payload
            if envelope.sender_id != jwt_payload.get("seeker"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Sender ID does not match JWT seeker",
                )

            restored_context = restore_inbound_payload(envelope.task_context)

            if self.task_handler:
                try:
                    self.task_handler(envelope.task_type, restored_context)
                except Exception as exc:
                    print(f"Task handler error: {exc}")
            else:
                print("No task handler configured")

            return P2PAckResponse(acknowledged=True)

        @self.app.post("/api/p2p/address")
        async def p2p_address_request(request: P2PAddressRequest):
            inventory_file = Path.home() / ".agentspace" / "inventory_map.json"
            if not inventory_file.exists():
                return {"matched_files": [], "total_count": 0}

            inventory = json.loads(inventory_file.read_text(encoding="utf-8"))
            requested_tags = set(request.tags)
            matched_files = []

            for file_entry in inventory.get("files", []):
                file_tags = set(file_entry.get("entity_tags", []))
                if requested_tags & file_tags:
                    matched_files.append({
                        "filename": file_entry.get("filename"),
                        "static_url": file_entry.get("static_url"),
                        "size_bytes": file_entry.get("size_bytes"),
                    })

            return {"matched_files": matched_files, "total_count": len(matched_files)}

        @self.app.post("/api/webhook/delivery")
        async def receive_p2p_delivery(request: P2PDeliveryRequest):
            """
            Receive P2P delivery from other agents.

            This endpoint:
            1. Saves the delivered file to demand_inbox/
            2. Updates the task cache with delivery info
            3. Triggers the gateway's delivery event
            4. Sends wake-up notification to OpenClaw (cross-temporal)

            ⚠️ V1.5 更新：支持 base64 编码的文件内容（全球 HTTP 直邮）
            ⚠️ V1.6 更新：支持中文文件名（URL-safe 编码）
            """
            import urllib.parse

            whitelist = FileExtensionWhitelist()
            inbox_dir = Path.home() / ".agentspace" / "demand_inbox"
            inbox_dir.mkdir(parents=True, exist_ok=True)

            demand_id = request.demand_id

            for file_info in request.files:
                # ⚠️ [V1.6 新增] 支持中文文件名（URL 解码）
                filename = file_info.filename
                try:
                    # 尝试 URL 解码（处理 %E4%B8%AD%E6%96%87 这类编码）
                    filename = urllib.parse.unquote(filename)
                except Exception:
                    pass  # 解码失败，使用原始文件名

                allowed, error = whitelist.validate_file(filename)
                if not allowed:
                    raise HTTPException(status_code=403, detail=error)

                content = file_info.content

                # ⚠️ [V1.5 新增] 支持 base64 编码的文件内容
                if isinstance(content, str):
                    # 如果是字符串，尝试 base64 解码
                    import base64
                    try:
                        content = base64.b64decode(content)
                    except Exception:
                        # 解码失败，可能是原始字节字符串
                        content = content.encode("utf-8")
                elif not isinstance(content, bytes):
                    # 既不是 str 也不是 bytes，转换
                    content = str(content).encode("utf-8")

                file_path = inbox_dir / filename
                with open(file_path, "wb") as f:
                    f.write(content)

                # Save metadata
                meta_file = inbox_dir / f"task_{demand_id}_meta.json"
                meta_content = {
                    "demand_id": demand_id,
                    "filename": filename,
                    "file_path": str(file_path),
                    "received_at": datetime.utcnow().isoformat(),
                    "provider_id": request.provider_id,
                    "file_size": len(content),
                }
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(meta_content, f, indent=2, ensure_ascii=False)

                # Update task cache with delivery info
                task_ctx = self._task_cache.get_task(demand_id)
                if task_ctx:
                    self._task_cache.update_status(
                        demand_id,
                        "completed",
                        result_file=str(file_path),
                        provider_id=request.provider_id,
                    )

                # Trigger gateway delivery event
                if _gateway_instance:
                    _gateway_instance.trigger_delivery(demand_id, str(file_path))

                # Send wake-up notification to OpenClaw (cross-temporal)
                resource_type = task_ctx.resource_type if task_ctx else "resource"
                await self._bridge.notify_delivery(
                    demand_id=demand_id,
                    file_path=str(file_path),
                    provider_id=request.provider_id,
                    resource_type=resource_type,
                )

            return {"status": "received", "demand_id": demand_id}

        @self.app.post("/api/webhook/signal")
        async def receive_hub_signal(signal_data: dict):
            """接收云端 Hub 发来的控制信令"""

            if signal_data.get("action") == "wake_up_delivery":
                demand_id = signal_data["demand_id"]
                new_seeker_url = signal_data["new_seeker_url"]

                print(f"[信令] 收到云端通知：需求方已上线！正在向新地址补发文件...")

                # 1. 组装临时 matched_demand
                matched_demand_mock = {
                    "demand_id": demand_id,
                    "seeker_webhook_url": new_seeker_url  # Hub 已拼接好完整 URL
                }

                # 2. 从本地找到要发送的文件
                supply_dir = Path.home() / ".agentspace" / "supply_provided"

                # ⚠️ 安全修正：根据 demand_id 推断 resource_type 并匹配文件
                # 简化实现：从 demand_id 提取资源类型，或使用默认值
                resource_type = "csv"  # 默认值
                if "_" in demand_id:
                    # 尝试从 demand_id 提取类型，如 "demand_csv_001" -> "csv"
                    parts = demand_id.split("_")
                    for part in parts:
                        if part in ["csv", "pdf", "json", "txt", "xlsx"]:
                            resource_type = part
                            break

                demand_info = {"resource_type": resource_type}
                file_path = self._find_file_for_demand_safe(supply_dir, demand_info)

                if file_path:
                    # 3. 异步触发补发
                    from ..sender import P2PSender
                    sender = P2PSender()
                    asyncio.create_task(
                        sender.send_file_to_seeker(
                            matched_demand=matched_demand_mock,
                            file_path=str(file_path),
                            provider_id="local_provider"
                        )
                    )
                else:
                    print(f"[WARNING] 无法找到匹配的文件，跳过自动发货")

            return {"status": "signal_received"}

    def _find_file_for_demand_safe(self, supply_dir: Path, demand_info: dict) -> Path | None:
        """
        安全的本地文件查找

        ⚠️ 防止发错文件：必须根据 resource_type 匹配文件后缀
        """
        if not supply_dir.exists():
            return None

        resource_type = demand_info.get("resource_type", "csv")
        expected_ext = f".{resource_type}"

        for file in supply_dir.iterdir():
            if file.is_file() and file.suffix == expected_ext:
                return file

        return None

    async def _cancel_hub_demand(self, demand_id: str):
        """通知 Hub 删除云端需求"""
        import httpx
        url = f"{HUB_URL}{API_V1_PREFIX}/pending_demands/{demand_id}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.delete(url)
        except Exception as e:
            print(f"[WARNING] 取消 Hub 需求失败: {e}")

    def run(self, host: str = "0.0.0.0"):
        import uvicorn
        uvicorn.run(self.app, host=host, port=self.port, log_level="info")

    async def run_async(self, host: str = "0.0.0.0"):
        import uvicorn
        config = uvicorn.Config(self.app, host=host, port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
