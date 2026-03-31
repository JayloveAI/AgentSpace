"""
Payload Handler - V1.5 Automatic Large File Handling
====================================================
自动检测大文件并转换为外部链接，避免传输超时

Features:
- 自动检测 payload 大小
- 超过阈值自动上传到外部存储
- 生成临时访问链接
- 接收方自动下载还原
"""
import json
import os
import uuid
from typing import Any, Dict, List, Optional
from pathlib import Path
import httpx


class PayloadConfig:
    """Payload 处理配置"""

    # Payload 大小阈值 (字节)
    SIZE_THRESHOLD = 1024 * 100  # 100KB

    # 支持的外部存储
    STORAGE_PROVIDERS = {
        "s3": "https://s3.amazonaws.com",
        "oss": "https://oss-cn-hangzhou.aliyuncs.com",
        "temp": "https://temp.sh",  # 临时文件服务
        "local": "http://localhost:9000"  # 本地 MinIO
    }

    # 默认存储提供商
    DEFAULT_PROVIDER = "temp"


class PayloadHandler:
    """
    Payload 处理器 - 自动处理大文件

    使用示例:
        handler = PayloadHandler(size_threshold=1024*500)  # 500KB

        # 发送方：自动处理大文件
        processed_payload = handler.prepare_payload(large_payload)

        # 接收方：自动还原
        original_payload = handler.restore_payload(processed_payload)
    """

    def __init__(
        self,
        size_threshold: int = PayloadConfig.SIZE_THRESHOLD,
        storage_provider: str = PayloadConfig.DEFAULT_PROVIDER,
        storage_config: Optional[Dict] = None
    ):
        self.size_threshold = size_threshold
        self.storage_provider = storage_provider
        self.storage_config = storage_config or {}

    def prepare_payload(self, payload: Any) -> Dict[str, Any]:
        """
        准备 Payload - 自动检测并处理大文件

        发送方调用此方法处理要发送的 payload

        Args:
            payload: 原始 payload 数据

        Returns:
            处理后的 payload，大文件已被替换为 data_links
        """
        # 1. 序列化为 JSON 检查大小
        payload_json = json.dumps(payload, ensure_ascii=False)
        payload_size = len(payload_json.encode('utf-8'))

        # 2. 如果未超过阈值，直接返回
        if payload_size <= self.size_threshold:
            return {"data": payload}

        # 3. 超过阈值，提取大文件字段
        result = {
            "_metadata": {
                "original_size": payload_size,
                "compressed": True,
                "storage_provider": self.storage_provider
            },
            "data_links": [],
            "schema": self._extract_schema(payload)
        }

        # 4. 遍历 payload，找出大字段
        large_fields = self._find_large_fields(payload, self.size_threshold // 2)

        # 5. 上传大字段到外部存储
        for field_path, field_value in large_fields:
            upload_url = self._upload_field(field_value, field_path)
            result["data_links"].append({
                "field": field_path,
                "url": upload_url,
                "size": len(json.dumps(field_value).encode('utf-8'))
            })

        # 6. 保留小字段的原始数据
        result["small_data"] = self._remove_large_fields(payload, large_fields)

        return result

    def restore_payload(self, processed_payload: Dict[str, Any]) -> Any:
        """
        还原 Payload - 自动下载外部链接

        接收方调用此方法还原收到的 payload

        Args:
            processed_payload: 处理后的 payload（包含 data_links）

        Returns:
            原始 payload 数据
        """
        # 1. 如果是简单格式，直接返回
        if "data" in processed_payload:
            return processed_payload["data"]

        # 2. 如果包含 data_links，需要还原
        if "data_links" not in processed_payload:
            raise ValueError("Invalid payload format: missing data_links")

        result = processed_payload.get("small_data", {})

        # 3. 下载大字段并合并
        for link in processed_payload["data_links"]:
            field_value = self._download_field(link["url"])
            self._set_nested_field(result, link["field"], field_value)

        return result

    def _extract_schema(self, payload: Any) -> Dict:
        """提取 payload 结构信息（不含实际数据）"""
        if isinstance(payload, dict):
            return {k: type(v).__name__ for k, v in payload.items()}
        return {"type": type(payload).__name__}

    def _find_large_fields(
        self,
        payload: Any,
        threshold: int
    ) -> List[tuple]:
        """
        递归查找大字段

        Returns:
            [(field_path, field_value), ...]
            例如: [("task_context.source_texts", ["large", "data"])]
        """
        large_fields = []

        def _traverse(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    size = len(json.dumps(value).encode('utf-8'))
                    if size > threshold:
                        large_fields.append((new_path, value))
                    elif isinstance(value, (dict, list)):
                        _traverse(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]"
                    size = len(json.dumps(item).encode('utf-8'))
                    if size > threshold:
                        large_fields.append((new_path, item))
                    elif isinstance(item, (dict, list)):
                        _traverse(item, new_path)

        _traverse(payload)
        return large_fields

    def _remove_large_fields(
        self,
        payload: Any,
        large_fields: List[tuple]
    ) -> Any:
        """从 payload 中移除大字段"""
        if isinstance(payload, dict):
            result = payload.copy()
            for field_path, _ in large_fields:
                self._delete_nested_field(result, field_path)
            return result
        return payload

    def _upload_field(self, field_value: Any, field_path: str) -> str:
        """
        上传字段到外部存储

        Returns:
            上传后的访问 URL
        """
        # 序列化数据
        data = json.dumps(field_value, ensure_ascii=False)
        filename = f"{uuid.uuid4()}_{field_path.replace('.', '_')}.json"

        # 根据存储提供商选择上传方式
        if self.storage_provider == "temp":
            return self._upload_to_temp(data, filename)
        elif self.storage_provider == "s3":
            return self._upload_to_s3(data, filename)
        elif self.storage_provider == "local":
            return self._upload_to_local(data, filename)
        else:
            # 默认：内联存储（base64编码）
            import base64
            return f"data:application/json;base64,{base64.b64encode(data.encode()).decode()}"

    def _upload_to_temp(self, data: str, filename: str) -> str:
        """上传到临时文件服务 (https://temp.sh)"""
        response = httpx.post(
            "https://temp.sh/documents",
            content=data.encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        result = response.json()
        return f"https://temp.sh/{result['key']}"

    def _upload_to_s3(self, data: str, filename: str) -> str:
        """上传到 AWS S3"""
        # TODO: 实现 S3 上传
        # 需要安装 boto3: pip install boto3
        import boto3
        s3 = boto3.client('s3', **self.storage_config)
        s3.put_object(
            Bucket=self.storage_config.get('bucket', 'agent-hub-payloads'),
            Key=filename,
            Body=data.encode('utf-8'),
            ContentType='application/json'
        )
        return f"https://{self.storage_config['bucket']}.s3.amazonaws.com/{filename}"

    def _upload_to_local(self, data: str, filename: str) -> str:
        """上传到本地存储"""
        upload_dir = Path("/tmp/agent_hub_uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / filename
        file_path.write_text(data, encoding='utf-8')

        # 假设本地有 HTTP 服务
        return f"http://localhost:9000/uploads/{filename}"

    def _download_field(self, url: str) -> Any:
        """从外部存储下载字段"""
        if url.startswith("data:"):
            # Base64 内联数据
            import base64
            _, data = url.split(",", 1)
            decoded = base64.b64decode(data).decode('utf-8')
            return json.loads(decoded)
        else:
            # HTTP 下载
            response = httpx.get(url, timeout=30.0)
            return response.json()

    def _set_nested_field(self, obj: dict, field_path: str, value: Any):
        """设置嵌套字段的值"""
        parts = field_path.split('.')
        current = obj
        for part in parts[:-1]:
            if '[' in part:
                key, idx = part.split('[')
                idx = int(idx.rstrip(']'))
                current = current.setdefault(key, [])
                while len(current) <= idx:
                    current.append({})
                current = current[idx]
            else:
                current = current.setdefault(part, {})

        last_part = parts[-1]
        if '[' in last_part:
            key, idx = last_part.split('[')
            idx = int(idx.rstrip(']'))
            if key not in current:
                current[key] = []
            current[key][idx] = value
        else:
            current[last_part] = value

    def _delete_nested_field(self, obj: dict, field_path: str):
        """删除嵌套字段"""
        parts = field_path.split('.')
        current = obj
        for part in parts[:-1]:
            if '[' in part:
                key, idx = part.split('[')
                idx = int(idx.rstrip(']'))
                current = current[key][idx]
            else:
                current = current.get(part, {})

        last_part = parts[-1]
        if '[' in last_part:
            key, idx = last_part.split('[')
            idx = int(idx.rstrip(']'))
            del current[key][idx]
        else:
            current.pop(last_part, None)


# ============================================================================
# 便捷函数
# ============================================================================

# 全局默认处理器
_default_handler: Optional[PayloadHandler] = None


def get_payload_handler() -> PayloadHandler:
    """获取全局 Payload 处理器"""
    global _default_handler
    if _default_handler is None:
        _default_handler = PayloadHandler()
    return _default_handler


def prepare_outbound_payload(payload: Any) -> Dict[str, Any]:
    """
    发送方：准备 Payload（自动处理大文件）

    使用示例:
        from client_sdk.core.payload_handler import prepare_outbound_payload

        # 原始 payload 可能包含大文件
        original_payload = {
            "task_type": "process_large_dataset",
            "task_context": {
                "data": [ ... ] * 10000  # 大数据集
            }
        }

        # 自动处理
        processed = prepare_outbound_payload(original_payload)
        # 结果: {"_metadata": {...}, "data_links": [...], "small_data": {...}}
    """
    return get_payload_handler().prepare_payload(payload)


def restore_inbound_payload(processed_payload: Dict[str, Any]) -> Any:
    """
    接收方：还原 Payload（自动下载大文件）

    使用示例:
        from client_sdk.core.payload_handler import restore_inbound_payload

        # 收到的处理后的 payload
        received = {
            "_metadata": {...},
            "data_links": [{"field": "task_context.data", "url": "https://..."}],
            "small_data": {"task_type": "process_large_dataset"}
        }

        # 自动还原
        original = restore_inbound_payload(received)
    """
    return get_payload_handler().restore_payload(processed_payload)


# ============================================================================
# 装饰器 - 自动处理 P2P 消息的 Payload
# ============================================================================

def auto_handle_payload(size_threshold: int = 1024 * 100):
    """
    装饰器：自动处理 Agent 任务回调中的大文件

    使用示例:
        @auto_handle_payload(size_threshold=1024*500)  # 500KB
        async def my_task_handler(task_type: str, task_context: dict):
            # task_context 已自动还原大文件
            large_data = task_context.get("data")  # 自动下载完成
            return {"result": "success"}
    """
    def decorator(func):
        async def wrapper(task_type: str, task_context: dict):
            # 还原可能的 data_links
            if "data_links" in task_context or "_metadata" in task_context:
                task_context = restore_inbound_payload(task_context)
            return await func(task_type, task_context)
        return wrapper
    return decorator
