-- Migration 004: Add pending_demands table

CREATE TABLE IF NOT EXISTS pending_demands (
    id SERIAL PRIMARY KEY,
    demand_id VARCHAR(64) UNIQUE NOT NULL,
    seeker_id VARCHAR(255),
    resource_type VARCHAR(100),
    description TEXT,
    tags JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    matched_agent_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_demands_status
ON pending_demands(status);
