"""
P2P Sender - 向其他 Agent 发送任务
==================================
携带 JWT 门票发起 P2P 请求

V1.5: 集成自动大文件处理 - 超过阈值的 payload 自动上传到外部存储
V1.5: 新增全球 HTTP 直邮功能 - send_file_to_seeker
"""
import base64
import httpx
import os
from typing import Any, Callable
from hub_server.api.contracts import P2PTaskEnvelope, P2PAckResponse
from client_sdk.core.payload_handler import prepare_outbound_payload


class P2PSender:
    """
    P2P 任务发送器
    
    负责：
    1. 携带 JWT 门票发送任务
    2. 按用户指定的顺序尝试
    3. 遇到首个 200 OK 后停止
    4. 处理异步回调
    """
    
    def __init__(self):
        self._http_client: httpx.AsyncClient | None = None
    
    @property
    def http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=300.0)  # 5分钟超时
        return self._http_client
    
    async def send_task(
        self,
        sender_id: str,
        target_url: str,
        match_token: str,
        task_type: str,
        task_context: dict,
        reply_callback: Callable[[dict], None] | None = None
    ) -> bool:
        """
        发送 P2P 任务

        Args:
            sender_id: 发送方 Agent ID
            target_url: 目标 Agent 的 Webhook 地址
            match_token: Hub 颁发的 JWT 门票
            task_type: 任务类型
            task_context: 任务数据
            reply_callback: 回调处理函数

        Returns:
            是否成功发送
        """
        # V1.5: 自动处理大文件
        processed_context = prepare_outbound_payload(task_context)

        envelope = P2PTaskEnvelope(
            sender_id=sender_id,
            task_type=task_type,
            reply_to="",  # TODO: 本地回调地址
            task_context=processed_context
        )
        
        try:
            response = await self.http_client.post(
                target_url,
                json=envelope.model_dump(),
                headers={
                    "X-Match-Token": match_token,
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                ack = P2PAckResponse(**response.json())
                print(f"[OK] 任务已被接收: {target_url}")
                if ack.estimated_completion_minutes:
                    print(f"[INFO] 预计 {ack.estimated_completion_minutes} 分钟后完成")
                return True
            else:
                print(f"[WARN] 任务发送失败: HTTP {response.status_code}")
                return False

        except httpx.HTTPError as e:
            print(f"[ERROR] 网络错误: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] 发送失败: {e}")
            return False
    
    async def try_candidates(
        self,
        sender_id: str,
        candidates: list[dict],
        task_type: str,
        task_context: dict
    ) -> tuple[bool, dict | None]:
        """
        按顺序尝试多个候选 Agent
        
        Args:
            sender_id: 发送方 ID
            candidates: 候选列表，每个包含 contact_endpoint 和 match_token
            task_type: 任务类型
            task_context: 任务数据
        
        Returns:
            (是否成功, 成功的候选信息)
        """
        for i, candidate in enumerate(candidates, 1):
            print(f"[INFO] 尝试候选 {i}/{len(candidates)}: {candidate.get('agent_id')}")

            success = await self.send_task(
                sender_id=sender_id,
                target_url=candidate["contact_endpoint"],
                match_token=candidate["match_token"],
                task_type=task_type,
                task_context=task_context
            )

            if success:
                return True, candidate

            print(f"[INFO] 候选 {i} 不可用，尝试下一个...")

        print("[WARN] 所有候选均不可用")
        return False, None
    
    async def close(self):
        """关闭 HTTP 客户端"""
        if self._http_client:
            await self._http_client.aclose()

    async def send_file_to_seeker(
        self,
        matched_demand: dict,
        file_path: str,
        provider_id: str
    ) -> bool:
        """
        全球 HTTP 直邮：向 Seeker 的公网地址直接投递文件

        无论 Seeker 是通过 FRP(http) 还是 Ngrok(https) 暴露的，
        直接向其 seeker_webhook_url 发送标准 HTTP POST 请求。

        ⚠️ 注意：接收端使用 P2PDeliveryRequest (JSON 格式)，
        文件内容需要 base64 编码。

        Args:
            matched_demand: 从 Hub 获取的匹配需求，包含 seeker_webhook_url
            file_path: 要发送的文件路径
            provider_id: 提供方 ID

        Returns:
            是否成功投递
        """
        target_url = matched_demand.get("seeker_webhook_url")
        if not target_url:
            print(f"[ERROR] 订单 {matched_demand.get('demand_id')} 缺少收货地址！")
            return False

        print(f"[INFO] 正在通过全球公网向 {target_url} 投递文件...")

        try:
            # 读取文件内容
            with open(file_path, "rb") as f:
                file_content = f.read()

            # ⚠️ 构造符合 P2PDeliveryRequest 的 JSON 请求体
            payload = {
                "demand_id": matched_demand["demand_id"],
                "provider_id": provider_id,
                "files": [{
                    "filename": os.path.basename(file_path),
                    "content": base64.b64encode(file_content).decode("utf-8")  # base64 编码
                }]
            }

            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    target_url,
                    json=payload,  # 👈 使用 json= 而非 files=
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    print(f"[OK] 文件成功跨域投递给需求方！")
                    return True
                else:
                    print(f"[WARN] 投递失败: HTTP {response.status_code} - {response.text}")
                    return False

        except httpx.HTTPError as e:
            print(f"[ERROR] 网络错误: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] 发送失败: {e}")
            return False
