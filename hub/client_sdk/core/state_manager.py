"""
StateManager - 节点状态持久化管理器
==================================
解决节点重启后状态丢失问题
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import threading


@dataclass
class SupplyRecord:
    """供应项记录"""
    id: str
    filename: str
    tags: List[str]
    declared_at: str
    file_hash: str
    file_size: int
    local_path: str


@dataclass
class RuntimeState:
    """运行时状态"""
    agent_id: str
    registered_at: str
    public_url: Optional[str] = None
    last_heartbeat: Optional[str] = None
    tunnel_active: bool = False
    remote_port: Optional[int] = None


class StateManager:
    """
    节点状态持久化管理器

    功能：
    - 持久化已声明的供应项
    - 记录运行时状态
    - 重启后自动恢复
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.state_dir = workspace / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self._supplies_file = self.state_dir / "supplies.json"
        self._runtime_file = self.state_dir / "runtime.json"
        self._pending_file = self.state_dir / "pending_tasks.json"

        self._lock = threading.Lock()

        # 内存缓存
        self._supplies: Dict[str, SupplyRecord] = {}
        self._runtime: Optional[RuntimeState] = None
        self._pending_tasks: List[Dict[str, Any]] = []

        # 启动时加载状态
        self._load_all()

    def _load_all(self):
        """加载所有持久化状态"""
        self._load_supplies()
        self._load_runtime()
        self._load_pending_tasks()

    def _load_supplies(self):
        """加载供应项记录"""
        if self._supplies_file.exists():
            try:
                data = json.loads(self._supplies_file.read_text(encoding="utf-8"))
                self._supplies = {
                    k: SupplyRecord(**v) for k, v in data.get("supplies", {}).items()
                }
            except (json.JSONDecodeError, KeyError):
                self._supplies = {}

    def _load_runtime(self):
        """加载运行时状态"""
        if self._runtime_file.exists():
            try:
                data = json.loads(self._runtime_file.read_text(encoding="utf-8"))
                self._runtime = RuntimeState(**data)
            except (json.JSONDecodeError, KeyError):
                self._runtime = None

    def _load_pending_tasks(self):
        """加载待处理任务"""
        if self._pending_file.exists():
            try:
                data = json.loads(self._pending_file.read_text(encoding="utf-8"))
                self._pending_tasks = data.get("tasks", [])
            except json.JSONDecodeError:
                self._pending_tasks = []

    def _save_supplies(self):
        """保存供应项记录"""
        data = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "supplies": {k: asdict(v) for k, v in self._supplies.items()}
        }
        self._supplies_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _save_runtime(self):
        """保存运行时状态"""
        if self._runtime:
            data = asdict(self._runtime)
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._runtime_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

    def _save_pending_tasks(self):
        """保存待处理任务"""
        data = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tasks": self._pending_tasks
        }
        self._pending_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # === 供应项管理 ===

    def add_supply(self, supply: SupplyRecord):
        """添加供应项记录"""
        with self._lock:
            self._supplies[supply.id] = supply
            self._save_supplies()

    def remove_supply(self, supply_id: str):
        """移除供应项记录"""
        with self._lock:
            if supply_id in self._supplies:
                del self._supplies[supply_id]
                self._save_supplies()

    def get_supplies(self) -> List[SupplyRecord]:
        """获取所有供应项"""
        return list(self._supplies.values())

    def get_supply_by_id(self, supply_id: str) -> Optional[SupplyRecord]:
        """根据 ID 获取供应项"""
        return self._supplies.get(supply_id)

    # === 运行时状态管理 ===

    def init_runtime(self, agent_id: str):
        """初始化运行时状态"""
        with self._lock:
            self._runtime = RuntimeState(
                agent_id=agent_id,
                registered_at=datetime.now(timezone.utc).isoformat(),
                tunnel_active=False
            )
            self._save_runtime()

    def update_runtime(self, **kwargs):
        """更新运行时状态"""
        with self._lock:
            if self._runtime:
                for key, value in kwargs.items():
                    if hasattr(self._runtime, key):
                        setattr(self._runtime, key, value)
                self._save_runtime()

    def get_runtime(self) -> Optional[RuntimeState]:
        """获取运行时状态"""
        return self._runtime

    def update_heartbeat(self):
        """更新心跳时间"""
        self.update_runtime(
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
            tunnel_active=True
        )

    # === 待处理任务管理 ===

    def add_pending_task(self, task: Dict[str, Any]):
        """添加待处理任务"""
        with self._lock:
            self._pending_tasks.append(task)
            self._save_pending_tasks()

    def remove_pending_task(self, task_id: str):
        """移除待处理任务"""
        with self._lock:
            self._pending_tasks = [
                t for t in self._pending_tasks if t.get("id") != task_id
            ]
            self._save_pending_tasks()

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取待处理任务"""
        return self._pending_tasks.copy()

    # === 恢复接口 ===

    def needs_recovery(self) -> bool:
        """检查是否需要恢复状态"""
        return bool(self._supplies) or bool(self._pending_tasks)

    def get_recovery_info(self) -> Dict[str, Any]:
        """获取恢复信息"""
        return {
            "has_supplies": len(self._supplies) > 0,
            "supplies_count": len(self._supplies),
            "has_pending_tasks": len(self._pending_tasks) > 0,
            "pending_count": len(self._pending_tasks),
            "last_runtime": asdict(self._runtime) if self._runtime else None
        }

    def clear_all(self):
        """清除所有状态（用于完全重置）"""
        with self._lock:
            self._supplies.clear()
            self._pending_tasks.clear()
            self._runtime = None

            # 删除文件
            for f in [self._supplies_file, self._runtime_file, self._pending_file]:
                if f.exists():
                    f.unlink()
