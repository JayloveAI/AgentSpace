"""
ClawHub OpenClaw Integration Helper
====================================
简化的 OpenClaw 集成模块

使用方法:
    from clawhub_openclaw import auto_catch, ResourceMissing

    @auto_catch
    def my_function(agent, query):
        if not has_resource(query):
            raise ResourceMissing("pdf", f"需要 {query} 的报告")
        return process(query)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

# 重新导出核心组件，简化导入路径
from .gateway.auto_catcher import (
    auto_catch_and_route as auto_catch,
    ResourceMissingError as ResourceMissing,
)

from .gateway.openclaw_bridge import OpenClawBridge


def check_local_resource(topic: str, resource_type: Optional[str] = None) -> bool:
    """
    检查本地是否有相关资源

    Args:
        topic: 主题关键词
        resource_type: 资源类型 (可选，如 "pdf", "json")

    Returns:
        True 如果本地有匹配的资源
    """
    supply_dir = Path.home() / ".clawhub" / "supply_provided"

    if not supply_dir.exists():
        return False

    # 搜索匹配的文件
    pattern = f"*{topic}*"
    if resource_type:
        pattern += f".{resource_type}"

    return len(list(supply_dir.glob(pattern))) > 0


def get_received_files(demand_id: Optional[str] = None) -> List[Path]:
    """
    获取收到的投递文件

    Args:
        demand_id: 可选，指定需求 ID

    Returns:
        文件路径列表
    """
    inbox = Path.home() / ".clawhub" / "demand_inbox"

    if not inbox.exists():
        return []

    if demand_id:
        # 查找特定需求的文件
        meta_file = inbox / f"task_{demand_id}_meta.json"
        if meta_file.exists():
            import json
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                file_path = meta.get("file_path", "")
                if file_path and Path(file_path).exists():
                    return [Path(file_path)]
        return []

    # 返回所有文件（排除元数据文件）
    return [f for f in inbox.iterdir() if f.is_file() and not f.name.startswith("task_")]


def wait_for_delivery(demand_id: str, timeout: float = 300.0) -> Optional[Path]:
    """
    等待特定需求的文件投递

    Args:
        demand_id: 需求 ID
        timeout: 超时时间（秒），默认 5 分钟

    Returns:
        投递的文件路径，超时返回 None
    """
    import time

    inbox = Path.home() / ".clawhub" / "demand_inbox"
    meta_file = inbox / f"task_{demand_id}_meta.json"

    start_time = time.time()
    while time.time() - start_time < timeout:
        if meta_file.exists():
            import json
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                file_path = meta.get("file_path", "")
                if file_path and Path(file_path).exists():
                    return Path(file_path)

        time.sleep(2)

    return None


__all__ = [
    "auto_catch",
    "ResourceMissing",
    "OpenClawBridge",
    "check_local_resource",
    "get_received_files",
    "wait_for_delivery",
]
