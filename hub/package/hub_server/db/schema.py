"""
Database schema for AgentHub (PostgreSQL + pgvector).
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, Index, Enum
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(255), unique=True, nullable=False, index=True)
    domain = Column(String(50), nullable=False, index=True)
    intent_type = Column(String(20), nullable=False, index=True)
    contact_endpoint = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)

    description_vector = Column(String, nullable=True)

    tasks_requested = Column(Integer, default=0, nullable=False)
    tasks_provided = Column(Integer, default=0, nullable=False)

    last_active = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    node_status = Column(
        Enum("active", "busy", "offline", name="node_status_enum"),
        nullable=False,
        default="offline",
        index=True,
    )
    live_broadcast = Column(String(500), nullable=True)
    status_updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_agent_profiles_domain_intent", "domain", "intent_type"),
        Index("ix_agent_profiles_domain_status", "domain", "node_status"),
    )


def create_vector_extension_sql():
    return [
        "CREATE EXTENSION IF NOT EXISTS vector;",
        """
        ALTER TABLE agent_profiles
        ADD COLUMN IF NOT EXISTS description_vector VECTOR(1536);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_agent_profiles_description_vector_hnsw
        ON agent_profiles
        USING hnsw (description_vector vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
        """,
    ]
