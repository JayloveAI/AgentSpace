from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .entity_extractor import EntityExtractor


class WorkspaceWatchdog(FileSystemEventHandler):
    """
    Workspace file listener.

    Responsibilities:
    1. Detect new files in supply_provided/ and extract tags.
    2. Update inventory_map.json (local ledger).
    3. Report status to Hub (tags only, no files).

    V1.6.3 新增：
    - 启动时全量同步（sync_on_start）
    - 删除文件时更新 inventory
    - 重新提取已有文件的 tags（使用优化后的 extractor）
    """

    def __init__(
        self,
        workspace_path: Path,
        hub_connector: Optional[object] = None,
        agent_id: Optional[str] = None,
        on_file_callback: Optional[callable] = None
    ):
        self.workspace = Path(workspace_path).expanduser()
        self.supply_dir = self.workspace / "supply_provided"
        self.inventory_file = self.workspace / "inventory_map.json"
        self.hub = hub_connector
        self.agent_id = agent_id
        self.on_file_callback = on_file_callback
        self.extractor = EntityExtractor()
        self._observer = Observer()

        self.workspace.mkdir(parents=True, exist_ok=True)
        self.supply_dir.mkdir(parents=True, exist_ok=True)
        if not self.inventory_file.exists():
            self._write_inventory({"files": []})

    def start(self) -> Observer:
        """Start watchdog observer for the supply directory."""
        print(f"[DEBUG-WATCHDOG] ========== Starting WorkspaceWatchdog ==========")
        print(f"[DEBUG-WATCHDOG] workspace: {self.workspace}")
        print(f"[DEBUG-WATCHDOG] supply_dir: {self.supply_dir}")
        print(f"[DEBUG-WATCHDOG] supply_dir exists: {self.supply_dir.exists()}")
        print(f"[DEBUG-WATCHDOG] agent_id: {self.agent_id}")
        print(f"[DEBUG-WATCHDOG] on_file_callback: {self.on_file_callback is not None}")

        # V1.6.3: 启动时全量同步
        self._sync_inventory_on_start()

        self._observer.schedule(self, str(self.supply_dir), recursive=False)
        self._observer.start()
        print(f"[DEBUG-WATCHDOG] Observer started and watching: {self.supply_dir}")
        print(f"[DEBUG-WATCHDOG] ================================================")
        return self._observer

    def stop(self) -> None:
        """Stop watchdog observer."""
        self._observer.stop()
        self._observer.join()

    def _sync_inventory_on_start(self) -> dict:
        """
        V1.6.3: 启动时全量同步 inventory

        功能：
        1. 扫描 supply_provided/ 中所有文件
        2. 对比 inventory_map.json
        3. 添加缺失的文件，删除不存在的记录
        4. 可选：重新提取 tags（使用优化后的 extractor）

        Returns:
            同步结果统计 {"added": int, "removed": int, "updated": int}
        """
        print(f"[DEBUG-WATCHDOG] >>> Starting inventory sync...")

        # 获取实际文件列表
        actual_files = set()
        for f in self.supply_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                actual_files.add(f.name)

        # 获取 inventory 中的文件列表
        inventory = self._load_inventory()
        inventory_files = {f["filename"]: f for f in inventory.get("files", [])}

        stats = {"added": 0, "removed": 0, "updated": 0}

        # 1. 找出需要添加的文件（实际存在但 inventory 没有）
        files_to_add = actual_files - set(inventory_files.keys())
        for filename in files_to_add:
            file_path = self.supply_dir / filename
            tags = self.extractor.extract_tags(filename)

            # 尝试读取内容预览
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    preview = f.read(100)
                    tags.extend(self.extractor.extract_tags("", preview))
            except Exception:
                pass

            # 去重
            tags = list(set(tags))

            self._add_to_inventory(file_path, tags)
            stats["added"] += 1
            print(f"[DEBUG-WATCHDOG]   + Added: {filename} (tags: {tags[:5]}...)")

        # 2. 找出需要删除的记录（inventory 有但实际不存在）
        files_to_remove = set(inventory_files.keys()) - actual_files
        if files_to_remove:
            inventory["files"] = [
                f for f in inventory["files"]
                if f["filename"] not in files_to_remove
            ]
            stats["removed"] = len(files_to_remove)
            for filename in files_to_remove:
                print(f"[DEBUG-WATCHDOG]   - Removed: {filename}")

        # 3. 更新 inventory
        if stats["added"] > 0 or stats["removed"] > 0:
            self._write_inventory(inventory)

        print(f"[DEBUG-WATCHDOG] <<< Sync complete: added={stats['added']}, removed={stats['removed']}")
        return stats

    def _add_to_inventory(self, file_path: Path, tags: list[str]) -> None:
        """添加文件到 inventory（不重复添加）"""
        inventory = self._load_inventory()

        # 检查是否已存在
        for f in inventory["files"]:
            if f["filename"] == file_path.name:
                return  # 已存在，不重复添加

        static_url = self._generate_static_url(file_path)

        inventory["files"].append({
            "filename": file_path.name,
            "local_path": str(file_path),
            "static_url": static_url,
            "entity_tags": tags,
            "file_type": file_path.suffix,
            "size_bytes": file_path.stat().st_size,
            "created_at": datetime.utcnow().isoformat()
        })

        self._write_inventory(inventory)

    def on_created(self, event):
        print(f"[DEBUG-WATCHDOG] ========== File Event ==========")
        print(f"[DEBUG-WATCHDOG] event type: {event.event_type}")
        print(f"[DEBUG-WATCHDOG] event.src_path: {event.src_path}")
        print(f"[DEBUG-WATCHDOG] event.is_directory: {event.is_directory}")

        if event.is_directory:
            print(f"[DEBUG-WATCHDOG] Ignoring directory event")
            return

        src_path = Path(event.src_path)
        print(f"[DEBUG-WATCHDOG] src_path: {src_path}")
        print(f"[DEBUG-WATCHDOG] src_path.parent: {src_path.parent}")
        print(f"[DEBUG-WATCHDOG] self.supply_dir: {self.supply_dir}")
        print(f"[DEBUG-WATCHDOG] Parent check: {src_path.parent} == {self.supply_dir} -> {src_path.parent == self.supply_dir}")

        if src_path.parent != self.supply_dir:
            print(f"[DEBUG-WATCHDOG] Parent directory mismatch, ignoring")
            return

        import time

        print(f"[DEBUG-WATCHDOG] ✓ Parent directory matched, processing file...")
        # ⚠️ 防抖：等待文件写入完成
        initial_size = -1
        while True:
            current_size = src_path.stat().st_size
            if current_size == initial_size and current_size > 0:
                break
            initial_size = current_size
            time.sleep(0.5)

        # 此时文件已写入完成，继续处理
        filename = src_path.name
        print(f"[DEBUG-WATCHDOG] File write complete: {filename}")

        tags = self.extractor.extract_tags(filename)
        print(f"[DEBUG-WATCHDOG] Tags extracted from filename: {tags}")

        # 内容预览
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                preview = f.read(100)
                tags.extend(self.extractor.extract_tags("", preview))
        except Exception:
            pass

        # 去重
        tags = list(set(tags))

        # 更新 inventory
        self._add_to_inventory(src_path, tags)
        print(f"[DEBUG-WATCHDOG] Inventory updated")

        # 触发回调（用于文件投递）
        if self.on_file_callback:
            print(f"[DEBUG-WATCHDOG] Triggering on_file_callback...")
            file_info = {
                "filename": filename,
                "local_path": str(src_path),
                "static_url": self._generate_static_url(src_path),
                "file_type": src_path.suffix,
                "size_bytes": src_path.stat().st_size
            }
            print(f"[DEBUG-WATCHDOG] file_info: {file_info}")
            print(f"[DEBUG-WATCHDOG] Calling callback with {len(tags)} tags...")
            self.on_file_callback(file_info, tags)
            print(f"[DEBUG-WATCHDOG] Callback completed")
        else:
            print(f"[DEBUG-WATCHDOG] ⚠️ No on_file_callback set!")
        print(f"[DEBUG-WATCHDOG] =======================================")

    def on_deleted(self, event):
        """V1.6.3: 文件删除时更新 inventory"""
        if event.is_directory:
            return

        src_path = Path(event.src_path)
        if src_path.parent != self.supply_dir:
            return

        filename = src_path.name
        print(f"[DEBUG-WATCHDOG] File deleted: {filename}")

        # 从 inventory 中移除
        inventory = self._load_inventory()
        original_count = len(inventory["files"])
        inventory["files"] = [
            f for f in inventory["files"]
            if f["filename"] != filename
        ]

        if len(inventory["files"]) < original_count:
            self._write_inventory(inventory)
            print(f"[DEBUG-WATCHDOG] Removed from inventory: {filename}")

    def _update_inventory(self, file_path: Path, tags: list[str]) -> None:
        """更新 inventory（已废弃，使用 _add_to_inventory）"""
        self._add_to_inventory(file_path, tags)

    def _load_inventory(self) -> dict:
        if not self.inventory_file.exists():
            return {"files": []}
        try:
            return json.loads(self.inventory_file.read_text(encoding="utf-8"))
        except Exception:
            return {"files": []}

    def _write_inventory(self, inventory: dict) -> None:
        self.inventory_file.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _generate_static_url(self, file_path: Path) -> str:
        base_url = os.getenv("CLAWHUB_STATIC_BASE_URL") or os.getenv("STATIC_FILE_BASE_URL")
        if base_url:
            return f"{base_url.rstrip('/')}/{file_path.name}"
        return file_path.resolve().as_uri()

    def _trigger_report(self, tags: list[str]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._report_to_hub(tags))
        else:
            loop.create_task(self._report_to_hub(tags))

    async def _report_to_hub(self, tags: list[str]) -> None:
        if not self.hub or not hasattr(self.hub, "update_status"):
            return
        await self.hub.update_status(
            node_status="active",
            live_broadcast=f"新增资源: {', '.join(tags[:5])}"
        )
