"""
数据库模型定义
使用 PostgreSQL + pgvector
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, Index, literal_column, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# 注意：实际向量列需要通过原始 SQL 或 Alembic 迁移创建
# 这里使用字符串类型占位，pgvector 会自动处理

Base = declarative_base()


class AgentProfile(Base):
    """
    Agent 名片表
    对应文档中的 agent_profiles 表结构
    """
    __tablename__ = "agent_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(255), unique=True, nullable=False, index=True)
    domain = Column(String(50), nullable=False, index=True)
    intent_type = Column(String(20), nullable=False, index=True)  # 'ask' 或 'bid'
    contact_endpoint = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)

    # 向量列 - 需要原始 SQL 创建: description_vector VECTOR(1536)
    # 这里用 String 占位，实际通过 migration 创建
    description_vector = Column(String, nullable=True)

    # 信用账本
    tasks_requested = Column(Integer, default=0, nullable=False)
    tasks_provided = Column(Integer, default=0, nullable=False)

    # 活跃时间
    last_active = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # V1.5: Live Status Fields (Separation of concerns)
    # node_status: Machine state for SQL filtering (active/busy/offline)
    # When Agent is 'busy', Hub's first-layer funnel filters it out
    node_status = Column(
        Enum('active', 'busy', 'offline', name='node_status_enum'),
        nullable=False,
        default='offline',
        index=True
    )

    # live_broadcast: Human-readable status message (e.g., "Just finished A股 data cleaning")
    # This participates in vector embedding for semantic search
    live_broadcast = Column(String(500), nullable=True)

    # status_updated_at: Timestamp for last status update
    status_updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # 复合索引优化查询性能
        Index('ix_agent_profiles_domain_intent', 'domain', 'intent_type'),
        # V1.5: Composite index for hybrid search (domain + node_status)
        Index('ix_agent_profiles_domain_status', 'domain', 'node_status'),
    )


def create_vector_extension_sql():
    """返回创建 pgvector 扩展和向量列的 SQL"""
    return [
        # 创建 pgvector 扩展
        "CREATE EXTENSION IF NOT EXISTS vector;",

        # 添加向量列（如果不存在）
        """
        ALTER TABLE agent_profiles
        ADD COLUMN IF NOT EXISTS description_vector VECTOR(1536);
        """,

        # 创建 HNSW 索加速向量相似度搜索
        """
        CREATE INDEX IF NOT EXISTS idx_agent_profiles_description_vector_hnsw
        ON agent_profiles
        USING hnsw (description_vector vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
        """
    ]
