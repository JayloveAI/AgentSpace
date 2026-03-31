from typing import List, Optional
from datetime import datetime
from .lite_repository import get_repository, PendingDemand


def add_pending_demand(payload: dict, demand_vector: List[float]) -> PendingDemand:
    """添加悬赏需求（含向量）"""
    demand = PendingDemand(
        demand_id=payload.get("demand_id"),
        resource_type=payload.get("resource_type", "resource"),
        description=payload.get("description", ""),
        tags=payload.get("tags", []) or [],
        demand_vector=demand_vector,  # 👈 传入向量
        seeker_id=payload.get("seeker_id"),
        seeker_webhook_url=payload.get("seeker_webhook_url", ""),  # 👈 [新增] 必须映射！否则写不进数据库
        created_at=payload.get("created_at") or datetime.utcnow().isoformat(),  # ✅ 默认时间
        status="pending",
    )
    repo = get_repository()
    return repo.add_demand(demand)


def match_on_status_update(
    agent_id: str,
    node_status: str,
    live_broadcast: str,
    new_tags: List[str],
    new_vector: List[float]
) -> List[PendingDemand]:
    """
    反向撞库：触发 NumPy 引擎进行向量匹配

    Args:
        agent_id: Provider 的 Agent ID
        node_status: 节点状态（必须是 active 才触发）
        live_broadcast: 实时广播内容
        new_tags: Provider 的新标签列表
        new_vector: Provider 的向量表示
    """
    if node_status != "active" or not live_broadcast:
        return []

    repo = get_repository()
    # 👈 调用底层 NumPy 匹配引擎
    matched_demands = repo.find_matches(new_tags=new_tags, new_vector=new_vector)

    for demand in matched_demands:
        repo.mark_matched(demand.demand_id, agent_id)
        # 这里后续可以加上通知 Seeker 的 Webhook 代码

    return matched_demands


def list_pending_demands() -> List[PendingDemand]:
    """获取所有待处理需求（委托给 Repository）"""
    repo = get_repository()
    return repo.get_all_pending()
