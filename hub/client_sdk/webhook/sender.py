"""
P2P Sender - 向其他 Agent 发送任务
==================================
携带 JWT 门票发起 P2P 请求

V1.5: 集成自动大文件处理 - 超过阈值的 payload 自动上传到外部存储
V1.5: 新增全球 HTTP 直邮功能 - send_file_to_seeker
V1.6.7: 三策略自动分流 — base64 / stream / R2 中转
"""
import base64
import gzip
import hashlib
import os
import secrets
import uuid
from pathlib import Path
from typing import Any, Callable, AsyncGenerator

import httpx

from hub_server.api.contracts import P2PTaskEnvelope, P2PAckResponse
from client_sdk.core.payload_handler import prepare_outbound_payload
from client_sdk.core.transfer_strategy import (
    select_strategy,
    is_compressible,
    generate_aes_key,
    aes_key_to_bytes,
    compute_sha256,
    TransferProgress,
    CHUNK_SIZE,
    SMALL_FILE_THRESHOLD,
    LARGE_FILE_THRESHOLD,
)


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

    # ================================================================
    # V1.6.7: 三策略自动分流
    # ================================================================

    async def deliver_file(
        self,
        matched_demand: dict,
        file_path: str,
        provider_id: str,
    ) -> bool:
        """智能投递：自动选择 base64 / stream / R2 策略"""
        strategy = select_strategy(file_path)
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        print(f"[TRANSFER] Strategy={strategy} for {file_name} ({file_size / (1024*1024):.1f} MB)")

        if strategy == "base64":
            return await self.send_file_to_seeker(matched_demand, file_path, provider_id)
        elif strategy == "stream":
            return await self.send_file_streaming(matched_demand, file_path, provider_id)
        else:
            return await self.send_file_via_r2(matched_demand, file_path, provider_id)

    async def send_file_streaming(
        self,
        matched_demand: dict,
        file_path: str,
        provider_id: str,
    ) -> bool:
        """Strategy B: 分块流式传输（10-100MB），异步生成器避免内存泄漏"""
        target_url = matched_demand.get("seeker_webhook_url")
        if not target_url:
            print("[ERROR] 订单缺少收货地址")
            return False

        demand_id = matched_demand["demand_id"]
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        boundary = f"----AgentBoundary{secrets.token_hex(8)}"

        print(f"[STREAM] Sending {file_name} ({file_size/1024/1024:.1f}MB)")

        async def _gen():
            yield (f"--{boundary}\r\n"
                   f'Content-Disposition: form-data; name="demand_id"\r\n\r\n'
                   f"{demand_id}\r\n").encode()
            yield (f"--{boundary}\r\n"
                   f'Content-Disposition: form-data; name="provider_id"\r\n\r\n'
                   f"{provider_id}\r\n").encode()
            yield (f"--{boundary}\r\n"
                   f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
                   f"Content-Type: application/octet-stream\r\n\r\n").encode()

            progress = TransferProgress(file_size, "Upload")
            with open(file_path, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    progress.update(len(chunk))
                    yield chunk

            yield f"\r\n--{boundary}--\r\n".encode()

        try:
            timeout = httpx.Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    target_url.replace("/delivery", "/delivery/stream"),
                    content=_gen(),
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                )
                if resp.status_code == 200:
                    print(f"[OK] Stream complete: {file_name}")
                    return True
                elif resp.status_code == 404:
                    print("[FALLBACK] No /stream endpoint, using base64")
                    return await self.send_file_to_seeker(matched_demand, file_path, provider_id)
                else:
                    print(f"[WARN] Stream failed: HTTP {resp.status_code}")
                    return False
        except Exception as e:
            print(f"[ERROR] Stream send failed: {e}")
            return False

    async def send_file_via_r2(
        self,
        matched_demand: dict,
        file_path: str,
        provider_id: str,
    ) -> bool:
        """Strategy C: R2 中转 + AES 加密（> 100MB）"""
        from client_sdk.core.r2_storage import get_r2_storage

        r2 = get_r2_storage()
        if not r2.is_configured():
            print("[FALLBACK] R2 not configured, using stream")
            return await self.send_file_streaming(matched_demand, file_path, provider_id)

        target_url = matched_demand.get("seeker_webhook_url")
        if not target_url:
            print("[ERROR] 订单缺少收货地址")
            return False

        demand_id = matched_demand["demand_id"]
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        aes_key_b64 = generate_aes_key()
        aes_key_bytes = aes_key_to_bytes(aes_key_b64)
        sha256 = compute_sha256(file_path)

        print(f"[R2] Encrypting & uploading {file_name} ({file_size/1024/1024:.1f}MB)")

        try:
            enc_tmp = Path(file_path).with_suffix(Path(file_path).suffix + ".enc.tmp")
            try:
                self._encrypt_file(file_path, enc_tmp, aes_key_bytes)
                key = f"{uuid.uuid4()}/{file_name}.enc"
                download_url, _ = r2.upload_file(enc_tmp, key)
            finally:
                if enc_tmp.exists():
                    enc_tmp.unlink()

            payload = {
                "demand_id": demand_id,
                "provider_id": provider_id,
                "filename": file_name,
                "download_url": download_url,
                "file_size": file_size,
                "checksum_sha256": sha256,
                "aes_key": aes_key_b64,
                "encrypted": True,
            }

            link_url = target_url.replace("/delivery", "/delivery/link")
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(link_url, json=payload)
                if resp.status_code in (200, 202):
                    print(f"[OK] R2 link sent, receiver downloading in background")
                    return True
                elif resp.status_code == 404:
                    return await self.send_file_streaming(matched_demand, file_path, provider_id)
                else:
                    print(f"[WARN] R2 link failed: HTTP {resp.status_code}")
                    return False
        except Exception as e:
            print(f"[ERROR] R2 delivery failed: {e}")
            return False

    @staticmethod
    def _encrypt_file(src_path: str, dest_path: Path, key: bytes) -> None:
        """流式 AES-CTR 加密（4MB 分块，内存恒定）"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        nonce = secrets.token_bytes(12)
        cipher = Cipher(algorithms.AES(key), modes.CTR(nonce + (0).to_bytes(4, "big")))
        encryptor = cipher.encryptor()

        with open(src_path, "rb") as fin, open(dest_path, "wb") as fout:
            fout.write(nonce)
            while chunk := fin.read(CHUNK_SIZE):
                fout.write(encryptor.update(chunk))
            final = encryptor.finalize()
            if final:
                fout.write(final)
