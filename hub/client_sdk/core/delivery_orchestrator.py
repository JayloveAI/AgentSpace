"""Delivery Orchestrator - Coordinate file delivery to matched seekers."""
import asyncio
from pathlib import Path
from typing import List, Dict
from ..webhook.sender import P2PSender


class DeliveryOrchestrator:
    """Orchestrate file delivery to multiple matched seekers."""

    def __init__(self, agent_id: str, supply_dir: Path):
        self.agent_id = agent_id
        self.supply_dir = supply_dir
        self.sender = P2PSender()
        self._failed_deliveries = {}

    async def deliver_to_matched_seekers(
        self,
        file_path: str,
        matched_demands: List[Dict]
    ) -> Dict[str, bool]:
        """
        并发投递文件到所有匹配的 Seeker

        ⚠️ 修正：使用 asyncio.gather 实现真正的并发投递
        """
        results = {}
        tasks = []
        valid_demands = []

        for demand in matched_demands:
            # 验证文件类型匹配
            resource_type = demand.get("resource_type", "")
            file_suffix = Path(file_path).suffix[1:]

            if resource_type and resource_type != file_suffix:
                print(f"[SKIP] File type mismatch: {file_suffix} != {resource_type}")
                results[demand["demand_id"]] = False
                continue

            valid_demands.append(demand)
            coro = self._deliver_single_file_with_timeout(file_path, demand)
            tasks.append(coro)

        if not tasks:
            return results

        # ⚠️ 关键修正：并发执行所有投递任务
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)

        for demand, res in zip(valid_demands, completed_results):
            demand_id = demand["demand_id"]
            if isinstance(res, Exception):
                results[demand_id] = False
            else:
                results[demand_id] = res

        return results

    async def _deliver_single_file_with_timeout(self, file_path: str, demand: Dict) -> bool:
        """单个文件投递（带超时）"""
        try:
            return await asyncio.wait_for(
                self._deliver_single_file(file_path, demand),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            print(f"[TIMEOUT] Delivery timed out for {demand['demand_id']}")
            return False

    async def _deliver_single_file(self, file_path: str, demand: Dict) -> bool:
        """投递文件到单个 Seeker（带重试）"""
        demand_id = demand["demand_id"]
        max_retries = 3

        for attempt in range(max_retries):
            try:
                success = await self.sender.send_file_to_seeker(
                    matched_demand=demand,
                    file_path=file_path,
                    provider_id=self.agent_id
                )

                if success:
                    print(f"[OK] File delivered for demand {demand_id}")
                    self._failed_deliveries.pop(demand_id, None)
                    return True

            except Exception as e:
                print(f"[ERROR] Delivery attempt {attempt + 1} failed: {e}")

            # 指数退避
            await asyncio.sleep(2 ** attempt)

        # 记录失败
        self._failed_deliveries[demand_id] = {
            "file_path": file_path,
            "demand": demand
        }

        return False
