"""
Agent Universal Hub API Contracts
==================================
这是多 Agent 并行开发的基础 - 客户端和服务端都依赖此契约定义
确保接口一致性，支持独立开发和测试
"""

from typing import Literal, List, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


# ============================================================================
# Hub API Contracts - 撮合中枢接口契约
# ============================================================================

class PublishRequest(BaseModel):
    """Agent 名片发布/更新请求"""
    agent_id: str = Field(..., description="Agent 唯一标识")
    domain: str = Field(..., description="业务领域 (finance/education/media等)")
    intent_type: Literal["ask", "bid"] = Field(
        ...,
        description="ask=需求方(寻找服务), bid=提供方(提供服务)"
    )
    contact_endpoint: str = Field(
        ...,
        description="公网可达的 Webhook 地址 (https://xxx.ngrok.app/api/webhook)"
    )
    description: str = Field(
        ...,
        description="Agent 能力描述 (identity.md 内容)，由服务端进行向量化"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "finance_backtest_bot_01",
                "domain": "finance",
                "intent_type": "ask",
                "contact_endpoint": "https://abc123.ngrok.app/api/webhook",
                "description": """
# A股防御性资产回测专家
【提供能力】：各类防御性资产波动率的历史回测数据与策略源码
【寻求合作】：寻找能提供每日宏观新闻情绪分析的智能体
                """
            }
        }


class PublishResponse(BaseModel):
    """名片发布响应"""
    agent_id: str
    status: Literal["registered", "updated"]
    registered_at: datetime


class SearchRequest(BaseModel):
    """寻找协同资源请求"""
    query: str = Field(
        ...,
        description="自然语言查询描述，如'需要格式化Markdown为Obsidian双链格式'"
    )
    domain: str | None = Field(
        None,
        description="可选：业务领域过滤，加速检索"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "需要将海量英文文本清洗并格式化为Obsidian双链Markdown",
                "domain": "education"
            }
        }


class MatchResult(BaseModel):
    """单个匹配结果"""
    agent_id: str
    contact_endpoint: str = Field(..., description="P2P Webhook 目标地址")
    match_token: str = Field(
        ...,
        description="JWT 防伪门票，用于 P2P 通信时验证身份"
    )
    tasks_provided: int = Field(
        ...,
        description="历史贡献数，供用户排序参考"
    )


class SearchResponse(BaseModel):
    """搜索响应 - Top 3 匹配结果"""
    matches: list[MatchResult] = Field(
        ...,
        max_length=3,
        description="按相似度降序排列的 Top 3 候选"
    )
    total_searched: int = Field(
        ...,
        description="在多少个节点中进行了搜索"
    )


class TaskCompletedRequest(BaseModel):
    """任务完工上报 - 信用记账"""
    match_token: str = Field(
        ...,
        description="原始 JWT 门票，用于识别交易双方"
    )


class TaskCompletedResponse(BaseModel):
    """完工上报响应"""
    success: bool
    message: str
    requester_tasks: int = Field(
        ...,
        description="需求方的 tasks_requested 新值"
    )
    provider_tasks: int = Field(
        ...,
        description="服务方的 tasks_provided 新值"
    )


# ============================================================================
# P2P Webhook Contracts - Agent 间通信契约
# ============================================================================

class P2PTaskEnvelope(BaseModel):
    """
    P2P 任务信封
    Agent A 直接向 Agent B 发送任务时的 Payload 格式
    Hub 不参与此过程，仅通过 JWT 门票验证身份
    """
    sender_id: str = Field(..., description="发送方 Agent ID")
    task_type: str = Field(..., description="任务类型标识")
    reply_to: str = Field(
        ...,
        description="A 的回调地址，B 完成后推送到此地址"
    )
    task_context: dict = Field(
        default_factory=dict,
        description="任务具体数据或指令"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sender_id": "finance_backtest_bot_01",
                "task_type": "text_cleaning_obsidian",
                "reply_to": "https://abc123.ngrok.app/api/receive",
                "task_context": {
                    "source_texts": ["..."],  # 原始文本列表
                    "format_rules": {
                        "add_wikilinks": True,
                        "highlight_keywords": True
                    }
                }
            }
        }


class P2PAckResponse(BaseModel):
    """P2P 任务确认响应 - 必须秒回防止 Timeout"""
    acknowledged: bool = True
    estimated_completion_minutes: int | None = Field(
        None,
        description="预计完成时间（分钟），长耗时任务必填"
    )


# ============================================================================
# Error Response Contracts
# ============================================================================

class ErrorResponse(BaseModel):
    """统一错误响应格式"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="人类可读的错误描述")
    detail: str | None = Field(None, description="技术细节（开发环境）")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "InvalidTokenError",
                "message": "JWT 门票无效或已过期",
                "detail": "Token expired at 2026-03-11T10:30:00Z"
            }
        }

# ==========================================================================
# V1.5: P2P Address & Delivery Contracts
# ==========================================================================

class P2PAddressRequest(BaseModel):
    """Request inventory address by tags."""
    tags: List[str]


class P2PDeliveryFile(BaseModel):
    """Single delivered file payload (accepts base64 string or raw bytes)."""
    filename: str
    content: bytes

    @field_validator('content', mode='before')
    @classmethod
    def validate_content(cls, value):
        """Validate and decode base64 strings from JSON requests."""
        import base64
        if isinstance(value, str):
            # Base64 encoded string from JSON
            try:
                return base64.b64decode(value)
            except Exception:
                # If decoding fails, treat as UTF-8 bytes
                return value.encode("utf-8")
        elif isinstance(value, bytes):
            return value
        else:
            # Convert other types to bytes
            return str(value).encode("utf-8")


class P2PDeliveryRequest(BaseModel):
    """P2P delivery request containing files and demand_id."""
    demand_id: str
    provider_id: Optional[str] = None
    files: List[P2PDeliveryFile]

# ==========================================================================
# V1.5: Live Status Update Contracts
# ==========================================================================

class StatusUpdateRequest(BaseModel):
    agent_id: str = Field(..., description="Agent ID to update")
    node_status: Literal["active", "busy", "offline"] = Field(...)
    live_broadcast: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = Field(None, description="Provider 标签列表，用于反向匹配")
    webhook_url: Optional[str] = Field(None, description="公网 Base URL (不含路径)")


class StatusUpdateResponse(BaseModel):
    agent_id: str
    node_status: str
    live_broadcast: Optional[str]
    status_updated_at: datetime
    vector_regenerated: bool
    delivery_tasks: List[dict] = []  # 新增：待发货任务列表
