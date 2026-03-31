"""Task memory cache for cross-temporal wake-up support.

This module manages background task context, enabling the system to remember
the original task when resources are delivered later, supporting the
"Fire & Forget" async pattern.

V1.6 更新：
- 添加 user_id 字段支持多用户
- 内存索引 O(1) 查询
- LRU 容量熔断（5000 上限）
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class TaskContext:
    """
    Context for a background task.

    Stores the original task information so that when resources are delivered,
    the system can properly notify the user with the correct context.
    """
    demand_id: str
    resource_type: str
    description: str
    original_task: str
    user_id: str = "default_user"  # V1.6: 支持多用户
    created_at: str = ""
    status: str = "pending"  # "pending", "processing", "completed", "failed"
    result_file: Optional[str] = None
    error_message: Optional[str] = None
    provider_id: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "demand_id": self.demand_id,
            "resource_type": self.resource_type,
            "description": self.description,
            "original_task": self.original_task,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "status": self.status,
            "result_file": self.result_file,
            "error_message": self.error_message,
            "provider_id": self.provider_id,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskContext":
        """Create from dictionary."""
        return cls(**data)


class TaskCache:
    """
    Local task cache manager with O(1) memory index and LRU eviction.

    Manages the lifecycle of background tasks, storing context to disk
    for cross-session persistence.

    Features:
    - Memory index for O(1) user task counting
    - LRU capacity eviction (5000 tasks per user)
    - user_id support for multi-user scenarios
    """

    CACHE_DIR = Path.home() / ".agentspace" / "task_cache"
    MAX_PENDING_TASKS = 5000  # 安全阀：每个用户最多 5000 个待处理

    # ⚠️ 内存索引：O(1) 查询，拒绝每次扫盘
    _user_task_index: dict = {}  # { user_id: [ (demand_id, created_time), ... ] }
    _is_initialized: bool = False

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize the task cache.

        Args:
            cache_dir: Custom cache directory. Defaults to ~/.agentspace/task_cache.
        """
        self._cache_dir = cache_dir or self.CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._build_index_once()

    @classmethod
    def _build_index_once(cls):
        """系统启动时只扫一次盘，构建内存索引"""
        if cls._is_initialized:
            return

        for file in cls.CACHE_DIR.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                uid = data.get("user_id", "default_user")
                did = data.get("demand_id")
                created = datetime.fromisoformat(data.get("created_at", ""))

                if uid not in cls._user_task_index:
                    cls._user_task_index[uid] = []
                cls._user_task_index[uid].append((did, created))
            except Exception:
                pass

        # 按时间排序
        for uid in cls._user_task_index:
            cls._user_task_index[uid].sort(key=lambda x: x[1])

        cls._is_initialized = True

    def save_task(self, demand_id: str, context: dict) -> TaskContext:
        """
        Save a new task context to the cache.

        Args:
            demand_id: Unique identifier for the demand.
            context: Task context dictionary with resource_type, description, user_id, etc.

        Returns:
            The created TaskContext instance.
        """
        user_id = context.get("user_id", "default_user")
        created_at = datetime.utcnow()

        # O(1) 内存查询容量
        user_tasks = self._user_task_index.get(user_id, [])
        if len(user_tasks) >= self.MAX_PENDING_TASKS:
            # 取出最老的一个 (队列首部)
            oldest_id, _ = user_tasks.pop(0)
            self.delete_task(oldest_id, update_index=False)
            print(f"⚠️ [安全阀] 用户 {user_id} 任务达上限，清理任务 {oldest_id}")

        task_ctx = TaskContext(
            demand_id=demand_id,
            resource_type=context.get("resource_type", ""),
            description=context.get("description", ""),
            original_task=context.get("original_task", ""),
            user_id=user_id,
            created_at=created_at.isoformat(),
            status="pending",
        )

        cache_file = self._cache_dir / f"{demand_id}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(task_ctx.to_dict(), f, indent=2, ensure_ascii=False)

        # 更新内存索引
        if user_id not in self._user_task_index:
            self._user_task_index[user_id] = []
        self._user_task_index[user_id].append((demand_id, created_at))

        return task_ctx

    def get_task(self, demand_id: str) -> Optional[TaskContext]:
        """
        Retrieve a task context from the cache.

        Args:
            demand_id: Unique identifier for the demand.

        Returns:
            The TaskContext if found, None otherwise.
        """
        cache_file = self._cache_dir / f"{demand_id}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return TaskContext.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def update_status(
        self,
        demand_id: str,
        status: str,
        result_file: Optional[str] = None,
        provider_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[TaskContext]:
        """
        Update the status of a task.

        Args:
            demand_id: Unique identifier for the demand.
            status: New status ("pending", "processing", "completed", "failed").
            result_file: Path to the result file (if completed).
            provider_id: ID of the provider who fulfilled the demand.
            error_message: Error message (if failed).

        Returns:
            The updated TaskContext if found, None otherwise.
        """
        task_ctx = self.get_task(demand_id)
        if task_ctx is None:
            return None

        task_ctx.status = status

        if result_file:
            task_ctx.result_file = result_file

        if provider_id:
            task_ctx.provider_id = provider_id

        if error_message:
            task_ctx.error_message = error_message

        if status == "completed" or status == "failed":
            task_ctx.completed_at = datetime.utcnow().isoformat()

        # Write back to cache
        cache_file = self._cache_dir / f"{demand_id}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(task_ctx.to_dict(), f, indent=2, ensure_ascii=False)

        return task_ctx

    def list_tasks(self, status: Optional[str] = None, user_id: Optional[str] = None) -> list[TaskContext]:
        """
        List all tasks in the cache.

        Args:
            status: Filter by status. If None, returns all tasks.
            user_id: Filter by user_id. If None, returns all users.

        Returns:
            List of TaskContext instances.
        """
        tasks = []

        for cache_file in self._cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                task_ctx = TaskContext.from_dict(data)

                if status is not None and task_ctx.status != status:
                    continue
                if user_id is not None and task_ctx.user_id != user_id:
                    continue

                tasks.append(task_ctx)
            except (json.JSONDecodeError, KeyError):
                continue

        # Sort by creation time (newest first)
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return tasks

    def delete_task(self, demand_id: str, update_index: bool = True) -> bool:
        """
        Delete a task from the cache.

        Args:
            demand_id: Unique identifier for the demand.
            update_index: Whether to update memory index (default True).

        Returns:
            True if deleted, False if not found.
        """
        # 1. 删文件
        cache_file = self._cache_dir / f"{demand_id}.json"

        if not cache_file.exists():
            return False

        cache_file.unlink()

        # 2. 删内存索引
        if update_index:
            for uid in self._user_task_index:
                self._user_task_index[uid] = [
                    t for t in self._user_task_index[uid] if t[0] != demand_id
                ]

        return True

    def clear_completed(self, older_than_hours: int = 24) -> int:
        """
        Clear completed tasks older than the specified time.

        Args:
            older_than_hours: Delete tasks completed more than this many hours ago.

        Returns:
            Number of tasks deleted.
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        deleted = 0

        for task_ctx in self.list_tasks(status="completed"):
            if task_ctx.completed_at:
                completed_time = datetime.fromisoformat(task_ctx.completed_at)
                if completed_time < cutoff:
                    if self.delete_task(task_ctx.demand_id):
                        deleted += 1

        return deleted


__all__ = ["TaskContext", "TaskCache"]
